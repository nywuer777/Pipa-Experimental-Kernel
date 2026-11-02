#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage42 RT CPU hotplug and optional TLB hook / NO FLASH
"""Port RT pin-drain handshake to E404 cpu.c; preserve optional arch TLB hook.

Repair Stage41 core.o errors with the actual RT hotplug wait/retry protocol:
publish takedown_cpu_task, sleep until nr_pinned reaches zero, retry
-EAGAIN, and clear the pointer on error/success. The target E404 arm64
has no tlb_migrate_finish hook, so call it only when the architecture
actually defines it. Never supply an artificial no-op runtime or pin count.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

CORE = "kernel/sched/core.c"
CPU = "kernel/cpu.c"
ARM64_TLB = "arch/arm64/include/asm/tlb.h"
GENERIC_TLB = "include/asm-generic/tlb.h"
CPU_REJECT = "kernel/sched/core.c.rej"
OTHER_REJECT = "kernel/sched/cpupri.c.rej"

CPU_FUNC = "static int takedown_cpu(unsigned int cpu)\n"
CPU_THREAD_GLOBAL = (
    "#if defined(CONFIG_PREEMPT_RT_BASE) && defined(CONFIG_HOTPLUG_CPU)\n"
    "struct task_struct *takedown_cpu_task;\n"
    "#endif\n\n"
)
HOTPLUG_SETUP = "\tirq_lock_sparse();\n\n"
HOTPLUG_RT_WAIT = (
    "#ifdef CONFIG_PREEMPT_RT_BASE\n"
    "\tWARN_ON_ONCE(READ_ONCE(takedown_cpu_task));\n"
    "\tWRITE_ONCE(takedown_cpu_task, current);\n\n"
    "retry_pinned_cpu:\n"
    "\t/* The stop-machine callback rechecks the counter to close races. */\n"
    "\tfor (;;) {\n"
    "\t\tint nr_pinned;\n\n"
    "\t\tset_current_state(TASK_UNINTERRUPTIBLE);\n"
    "\t\tnr_pinned = cpu_nr_pinned(cpu);\n"
    "\t\tif (!nr_pinned)\n"
    "\t\t\tbreak;\n"
    "\t\tschedule();\n"
    "\t}\n"
    "\t__set_current_state(TASK_RUNNING);\n"
    "#endif\n\n"
)
STOP_CALL = "\terr = stop_machine_cpuslocked(take_cpu_down, NULL, cpumask_of(cpu));\n"
STOP_RETRY = (
    "#ifdef CONFIG_PREEMPT_RT_BASE\n"
    "\tif (err == -EAGAIN)\n"
    "\t\tgoto retry_pinned_cpu;\n"
    "#endif\n"
)
FAIL_ANCHOR = (
    "\tif (err) {\n"
    "\t\t/* CPU refused to die */\n"
    "\t\tirq_unlock_sparse();"
)
FAIL_REPLACEMENT = (
    "\tif (err) {\n"
    "#ifdef CONFIG_PREEMPT_RT_BASE\n"
    "\t\tWRITE_ONCE(takedown_cpu_task, NULL);\n"
    "#endif\n"
    "\t\t/* CPU refused to die */\n"
    "\t\tirq_unlock_sparse();"
)
SUCCESS_ANCHOR = (
    "\twait_for_ap_thread(st, false);\n"
    "\tBUG_ON(st->state != CPUHP_AP_IDLE_DEAD);\n\n"
    "\t/* Interrupts are moved away from the dying cpu, reenable alloc/free */"
)
SUCCESS_REPLACEMENT = (
    "\twait_for_ap_thread(st, false);\n"
    "\tBUG_ON(st->state != CPUHP_AP_IDLE_DEAD);\n"
    "#ifdef CONFIG_PREEMPT_RT_BASE\n"
    "\tWRITE_ONCE(takedown_cpu_task, NULL);\n"
    "#endif\n\n"
    "\t/* Interrupts are moved away from the dying cpu, reenable alloc/free */"
)
CORE_HOOK = "\t\ttlb_migrate_finish(p->mm);\n"
HOOK_OPTIONAL = (
    "#ifdef tlb_migrate_finish\n"
    "\t\ttlb_migrate_finish(p->mm);\n"
    "#endif\n"
)
CORE_DECL_MARKER = ("#if defined(CONFIG_SMP) && defined(CONFIG_PREEMPT_RT_BASE)\n\n"
                    "static inline void\nupdate_nr_migratory(struct task_struct *p, long delta)\n")
CORE_EXTERN = (
    "#if defined(CONFIG_PREEMPT_RT_BASE) && defined(CONFIG_HOTPLUG_CPU)\n"
    "extern struct task_struct *takedown_cpu_task;\n"
    "#endif\n\n"
)


def one(body: str, text: str, label: str) -> None:
    n = body.count(text)
    if n != 1:
        raise ValueError(f"{label}: expected one {text!r}, found {n}")


def prepare(tree: Path) -> tuple[str, str]:
    files = (CORE, CPU, ARM64_TLB, GENERIC_TLB, CPU_REJECT, OTHER_REJECT)
    for name in files:
        if not (tree / name).is_file():
            raise ValueError("Pinned Stage41 prerequisite missing: " + name)
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage42 requires exactly 64 unresolved RT rejects")
    core = (tree / CORE).read_text(encoding="utf-8")
    cpu = (tree / CPU).read_text(encoding="utf-8")
    arm_tlb = (tree / ARM64_TLB).read_text(encoding="utf-8")
    generic = (tree / GENERIC_TLB).read_text(encoding="utf-8")
    for tag, source in ((ARM64_TLB, arm_tlb), (GENERIC_TLB, generic)):
        if "tlb_migrate_finish" in source:
            raise ValueError(tag + ": unexpected architecture migration hook; review needed")
    one(arm_tlb, "#include <asm-generic/tlb.h>", ARM64_TLB)
    one(core, "#include <asm/tlb.h>", CORE)
    for token in (CORE_HOOK, "wake_up_process(takedown_cpu_task);",
                  "int cpu_nr_pinned(int cpu)", "rq->nr_pinned--;"):
        one(core, token, CORE)
    one(core, CORE_DECL_MARKER, CORE)
    one(cpu, CPU_FUNC, CPU)
    # E404 has irq_lock_sparse() in both bringup and takedown. Only
    # target the takedown function; never alter the CPU bringup path.
    before_takedown, takedown_body = cpu.split(CPU_FUNC, 1)
    one(takedown_body, HOTPLUG_SETUP, CPU + "::takedown_cpu")
    one(cpu, STOP_CALL, CPU)
    # The RT patch has one stopper call before the wait loop, and two
    # total only after its wait loop is applied. Check semantic call sites,
    # not a constant that assumes the source has one particular stage state.
    one(cpu, "if (cpu_nr_pinned(cpu))", CPU)
    if "extern struct task_struct *takedown_cpu_task;" in core:
        raise ValueError("Core hotplug declaration already added")
    if "if (cpu_nr_pinned(cpu))" not in cpu:
        raise ValueError("Stop-machine task pin recheck missing")

    # The official RT CPU hunk may already have applied to E404. Its
    # global wait loop is NOT part of Stage41's rejected core.c hunk.
    # Reuse it if complete; never overwrite it or silently skip drift.
    preexisting = "takedown_cpu_task" in cpu or "retry_pinned_cpu:" in cpu
    if preexisting:
        once_existing = (
            "struct task_struct *takedown_cpu_task;",
            "takedown_cpu_task = current;",
            "set_current_state(TASK_UNINTERRUPTIBLE);",
            "nr_pinned = cpu_nr_pinned(cpu);",
            "schedule();",
            "set_current_state(TASK_RUNNING);",
            "if (err == -EAGAIN)",
            "goto again;",
        )
        for marker in once_existing:
            one(cpu, marker, CPU)
        if cpu.count("cpu_nr_pinned(cpu)") != 2:
            raise ValueError("Complete RT hotplug requires stopper and polling call sites")
        if cpu.count("nr_pinned = cpu_nr_pinned(cpu);") != 1:
            raise ValueError("RT pin-drain loop must poll the tracked runqueue")
        one(cpu, "if (nr_pinned == 0)", CPU)
        if cpu.count("takedown_cpu_task = NULL;") != 2:
            raise ValueError("Upstream RT hotplug task must be cleared on failure and success")
        if "again:" not in cpu:
            raise ValueError("Upstream RT hotplug retry target missing")
        if "#ifdef CONFIG_PREEMPT_RT_BASE" not in cpu:
            raise ValueError("Upstream RT hotplug conditional missing")
        cpu_out = cpu
    else:
        if cpu.count("cpu_nr_pinned(cpu)") != 1:
            raise ValueError("Unported RT hotplug must have only the stopper pin check")
        one(cpu, FAIL_ANCHOR, CPU)
        one(cpu, SUCCESS_ANCHOR, CPU)
        # Modify the one takedown invocation, not the earlier bringup
        # irq_lock_sparse() site (which shares the same two-line text).
        cpu_out = (before_takedown + CPU_THREAD_GLOBAL + CPU_FUNC
                   + takedown_body.replace(
                       HOTPLUG_SETUP, HOTPLUG_SETUP + HOTPLUG_RT_WAIT, 1))
        cpu_out = cpu_out.replace(STOP_CALL, STOP_CALL + STOP_RETRY, 1)
        cpu_out = cpu_out.replace(FAIL_ANCHOR, FAIL_REPLACEMENT, 1)
        cpu_out = cpu_out.replace(SUCCESS_ANCHOR, SUCCESS_REPLACEMENT, 1)
        if cpu_out.count("WRITE_ONCE(takedown_cpu_task, NULL);") != 2:
            raise ValueError("Pin drain cleanup must cover failure and success")
        if cpu_out.count("goto retry_pinned_cpu;") != 1:
            raise ValueError("Missing -EAGAIN retry loop")

    core_out = core.replace(CORE_DECL_MARKER, CORE_EXTERN + CORE_DECL_MARKER, 1)
    core_out = core_out.replace(CORE_HOOK, HOOK_OPTIONAL, 1)
    if core_out.count("tlb_migrate_finish(p->mm);") != 1:
        raise ValueError("Optional arm64 TLB hook was not preserved")
    return core_out, cpu_out


def main() -> None:
    arg = argparse.ArgumentParser()
    arg.add_argument("--tree", required=True, type=Path)
    arg.add_argument("--report", required=True, type=Path)
    arg.add_argument("--mode", required=True, choices=("verify", "apply"))
    a = arg.parse_args()
    root = a.tree.resolve()
    core, cpu = prepare(root)
    if a.mode == "apply":
        (root / CORE).write_text(core, encoding="utf-8")
        (root / CPU).write_text(cpu, encoding="utf-8")
    if len(list(root.rglob("*.rej"))) != 64:
        raise ValueError("RT rejected file count changed")
    status = {
        "stage": "EXP76_STAGE42_RT_CPU_HOTPLUG_PIN_DRAIN_ARM64_TLB",
        "applied": a.mode == "apply",
        "takedown_cpu_task_lifecycle_ported": a.mode == "apply",
        "preexisting_upstream_hotplug_reused": a.mode == "apply" and (
            "WRITE_ONCE(takedown_cpu_task, current);" not in cpu),
        "pinned_task_wait_and_eagain_retry_ported": a.mode == "apply",
        "pin_drain_wakeup_preserved": True,
        "optional_arch_tlb_hook_preserved": True,
        "arm64_tlb_hook_absent_in_pinned_e404": True,
        "remaining_rejected_files": 64,
        "cpu_object_compiled": False,
        "scheduler_core_compiled": False,
        "migration_hotplug_runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    output = a.report.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "stage42-status.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
