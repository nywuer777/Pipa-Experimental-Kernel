#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage41 RT migration lifecycle E404 port / NO FLASH
"""Port the complete 4.19.325-rt140 rejected migration lifecycle to E404.

The rejected code uses task_struct.cpus_ptr/cpus_mask, which the E404
scheduler does not have. Save the original embedded cpus_allowed mask in
a separate RT-only field while scheduled migrate-disabled; restore it at
the final migrate_enable(). Preserve original nested counters, CPU stopper
migration, hotplug wakeup, and exported entry points. External setaffinity
updates during pinning must modify the saved mask rather than the active
single-CPU mask. Do not claim runtime correctness from object compilation.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

CORE = "kernel/sched/core.c"
REJECT = "kernel/sched/core.c.rej"
SCHED = "include/linux/sched.h"
RQ = "kernel/sched/sched.h"
RQ_REJECT = "kernel/sched/sched.h.rej"
CPU_H = "include/linux/cpu.h"
CPU = "kernel/cpu.c"
PREEMPT = "include/linux/preempt.h"
OTHER_REJECT = "kernel/sched/cpupri.c.rej"

MIGRATION_HUNK = "@@ -7111,3 +7225,171 @@ const u32 sched_prio_to_wmult[40] = {"
CORE_TAIL = "__read_mostly bool sched_predl = 1;\n"
RQ_ANCHOR = (
    "#ifdef CONFIG_CPU_IDLE\n"
    "\t/* Must be inspected within a rcu lock section */\n"
    "\tstruct cpuidle_state\t*idle_state;\n"
    "#endif\n"
    "};"
)
RQ_FIELD = (
    "\n#if defined(CONFIG_PREEMPT_RT_BASE) && defined(CONFIG_SMP)\n"
    "\tint\t\t\tnr_pinned;\n"
    "#endif\n"
)
TASK_ANCHOR = (
    "\tbool\t\t\t\tmigrate_disable_scheduled;\n"
    "#ifdef CONFIG_SCHED_DEBUG\n"
)
TASK_FIELD = "\tcpumask_t\t\t\tmigrate_disable_saved_mask;\n"
CPU_H_ANCHOR = "extern void boot_cpu_hotplug_init(void);\n"
CPU_H_DECL = (
    "#if defined(CONFIG_SMP) && defined(CONFIG_PREEMPT_RT_BASE)\n"
    "extern int cpu_nr_pinned(int cpu);\n"
    "#endif\n"
)
ALLOWED_EQUAL = "if (cpumask_equal(&p->cpus_allowed, new_mask))\n\t\tgoto out;"
ALLOWED_EQUAL_RT = (
    "if (cpumask_equal(&p->cpus_allowed, new_mask)"
    "\n#if defined(CONFIG_PREEMPT_RT_BASE) && defined(CONFIG_SMP)\n"
    "\t    && !p->migrate_disable_scheduled\n"
    "#endif\n"
    "\t   )\n\t\tgoto out;"
)
SET_ALLOWED = (
    "\tdo_set_cpus_allowed(p, new_mask);\n\n"
    "\tif (p->flags & PF_KTHREAD) {"
)
SET_ALLOWED_RT = (
    "#if defined(CONFIG_PREEMPT_RT_BASE) && defined(CONFIG_SMP)\n"
    "\t/* Defer requested affinity while the active mask pins this CPU. */\n"
    "\tif (p->migrate_disable_scheduled) {\n"
    "\t\tcpumask_copy(&p->migrate_disable_saved_mask, new_mask);\n"
    "\t\tgoto out;\n"
    "\t}\n"
    "#endif\n"
    "\tdo_set_cpus_allowed(p, new_mask);\n\n"
    "\tif (p->flags & PF_KTHREAD) {"
)
ORIG_PIN = (
    "\tp->cpus_ptr = cpumask_of(smp_processor_id());\n"
    "\tupdate_nr_migratory(p, -1);\n"
    "\tp->nr_cpus_allowed = 1;"
)
VENDOR_PIN = (
    "\t/* The E404 scheduler consults embedded cpus_allowed everywhere. */\n"
    "\tcpumask_copy(&p->migrate_disable_saved_mask, &p->cpus_allowed);\n"
    "\tupdate_nr_migratory(p, -1);\n"
    "\tcpumask_copy(&p->cpus_allowed, cpumask_of(task_cpu(p)));\n"
    "\tp->nr_cpus_allowed = 1;"
)
ORIG_UNPIN = (
    "\tp->cpus_ptr = &p->cpus_mask;\n"
    "\tp->nr_cpus_allowed = cpumask_weight(&p->cpus_mask);"
)
VENDOR_UNPIN = (
    "\t/* Restore the original or most recently requested affinity. */\n"
    "\tcpumask_copy(&p->cpus_allowed, &p->migrate_disable_saved_mask);\n"
    "\tp->nr_cpus_allowed = cpumask_weight(&p->cpus_allowed);"
)
REQUIRED_MIGRATION = (
    "void migrate_disable(void)",
    "void migrate_enable(void)",
    "static void migrate_disabled_sched(struct task_struct *p)",
    "int cpu_nr_pinned(int cpu)",
    "this_rq()->nr_pinned++;",
    "rq->nr_pinned--;",
    "stop_one_cpu_nowait(task_cpu(p), migration_cpu_stop,",
    "wake_up_process(takedown_cpu_task);",
    "preempt_lazy_disable();",
    "preempt_lazy_enable();",
)


def once(text: str, snippet: str, name: str) -> None:
    occurrences = text.count(snippet)
    if occurrences != 1:
        raise ValueError(f"{name}: expected one {snippet!r}, found {occurrences}")


def extract_rejected_runtime(contents: str) -> str:
    once(contents, MIGRATION_HUNK, REJECT)
    remaining = contents.split(MIGRATION_HUNK, 1)[1]
    if "\n@@ " in remaining:
        raise ValueError("Migration is not the final rejected hunk")
    added = [line[1:] for line in remaining.splitlines() if line.startswith("+")]
    body = "\n".join(added) + "\n"
    if len(added) < 130 or not body.startswith("\n#if defined(CONFIG_SMP)"):
        raise ValueError("Upstream migration hunk is missing or truncated")
    for token in REQUIRED_MIGRATION:
        if token not in body:
            raise ValueError("Pinned RT runtime missing: " + token)
    once(body, ORIG_PIN, REJECT)
    once(body, ORIG_UNPIN, REJECT)
    if body.count("EXPORT_SYMBOL(migrate_disable)") != 2:
        raise ValueError("Missing SMP and UP RT migrate_disable exports")
    if body.count("EXPORT_SYMBOL(migrate_enable)") != 2:
        raise ValueError("Missing SMP and UP RT migrate_enable exports")
    return body.replace(ORIG_PIN, VENDOR_PIN, 1).replace(ORIG_UNPIN, VENDOR_UNPIN, 1)


def prepare(tree: Path) -> dict[str, str]:
    sources = (CORE, REJECT, SCHED, RQ, RQ_REJECT, CPU_H, CPU, PREEMPT, OTHER_REJECT)
    for path in sources:
        if not (tree / path).is_file():
            raise ValueError("Pinned Stage40 source missing: " + path)
    rejects = len(list(tree.rglob("*.rej")))
    if rejects != 64:
        raise ValueError(f"Stage41 requires exactly 64 RT rejects; found {rejects}")
    rejected_rq = (tree / RQ_REJECT).read_text(encoding="utf-8")
    once(rejected_rq, "+\tint\t\t\tnr_pinned;", RQ_REJECT)
    runtime = extract_rejected_runtime((tree / REJECT).read_text(encoding="utf-8"))
    core = (tree / CORE).read_text(encoding="utf-8")
    sched = (tree / SCHED).read_text(encoding="utf-8")
    rq = (tree / RQ).read_text(encoding="utf-8")
    cpu_h = (tree / CPU_H).read_text(encoding="utf-8")
    cpu = (tree / CPU).read_text(encoding="utf-8")
    preempt = (tree / PREEMPT).read_text(encoding="utf-8")
    for path, snippet, body in (
        (CORE, CORE_TAIL, core),
        (CORE, ALLOWED_EQUAL, core),
        (CORE, SET_ALLOWED, core),
        (SCHED, TASK_ANCHOR, sched),
        (RQ, RQ_ANCHOR, rq),
        (CPU_H, CPU_H_ANCHOR, cpu_h),
        (CORE, "static void migrate_disabled_sched(struct task_struct *p);", core),
        (CORE, "return p->migrate_disable;", core),
    ):
        once(body, snippet, path)
    if cpu.count("cpu_nr_pinned(cpu)") != 2:
        raise ValueError("CPU hotplug consumer calls changed")
    if preempt.count("extern void migrate_disable(void);") != 2 or \
            preempt.count("extern void migrate_enable(void);") != 2:
        raise ValueError("Expected PREEMPT_RT migration entry point declarations")
    if re.search(r"\b(?:cpus_ptr|cpus_mask)\s*;", sched):
        raise ValueError("Incompatible task_struct pointer affinity was introduced")
    if TASK_FIELD in sched or RQ_FIELD.strip() in rq or \
            "extern int cpu_nr_pinned(int cpu);" in cpu_h:
        raise ValueError("Migration lifecycle port already present")
    if re.search(r"\bvoid\s+migrate_disable\s*\(\s*void\s*\)\s*\{", core):
        raise ValueError("Migration runtime already present")
    # Retain upstream per-CPU asynchronous migration work. Never silently
    # strip safety checks of arg->done / work->disabled for compiler success.
    for token in ("arg->done", "work->disabled"):
        if token not in runtime:
            raise ValueError("Pinned RT async migration guard lost: " + token)

    return {
        SCHED: sched.replace(TASK_ANCHOR, TASK_ANCHOR.replace(
            "#ifdef CONFIG_SCHED_DEBUG", TASK_FIELD + "#ifdef CONFIG_SCHED_DEBUG"
        ), 1),
        RQ: rq.replace(RQ_ANCHOR, RQ_ANCHOR.replace("};", RQ_FIELD + "};"), 1),
        CPU_H: cpu_h.replace(CPU_H_ANCHOR, CPU_H_ANCHOR + CPU_H_DECL, 1),
        CORE: core.replace(ALLOWED_EQUAL, ALLOWED_EQUAL_RT, 1)
                  .replace(SET_ALLOWED, SET_ALLOWED_RT, 1)
                  .replace(CORE_TAIL, CORE_TAIL + "\n" + runtime, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = parser.parse_args()
    tree = args.tree.resolve()
    changed = prepare(tree)
    if args.mode == "apply":
        for relative, data in changed.items():
            (tree / relative).write_text(data, encoding="utf-8")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Unexpected change in the rejected RT hunks")
    outcome = {
        "stage": "EXP76_STAGE41_RT_MIGRATION_LIFECYCLE_E404",
        "applied": args.mode == "apply",
        "original_rt_migration_hunk_ported": args.mode == "apply",
        "nested_migrate_disable_enable_present": args.mode == "apply",
        "runqueue_nr_pinned_counted": args.mode == "apply",
        "cpu_nr_pinned_reads_accounted_runqueue": args.mode == "apply",
        "saved_vendor_affinity_mask_and_setaffinity_deferral": args.mode == "apply",
        "upstream_async_stopper_safety_checks_preserved": True,
        "cpu_hotplug_caller_unchanged": True,
        "remaining_rejected_files": 64,
        "migration_runtime_semantics_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    target = args.report.resolve()
    target.mkdir(parents=True, exist_ok=True)
    (target / "stage41-status.json").write_text(json.dumps(outcome, indent=2) + "\n")
    print(json.dumps(outcome, indent=2))


if __name__ == "__main__":
    main()
