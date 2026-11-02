#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage29 E404 RT migration task ABI / NO FLASH
"""Restore only the upstream task_struct RT migration fields and fork initialization.

The real 4.19.325-rt140 sched.h reject contains migrate_disable and
migrate_disable_scheduled alongside an incompatible cpus_ptr/cpus_mask
conversion. This step ports the fields to E404's embedded cpus_allowed ABI.

This is an ABI prerequisite, NOT the migrate_disable() runtime implementation.
The original RT migration lifecycle, rq->nr_pinned, hotplug interactions,
sleeping_lock and remaining rejects require separate ports and tests.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SCHED = "include/linux/sched.h"
CORE = "kernel/sched/core.c"
REJECT = "include/linux/sched.h.rej"
CPU_PRI_REJECT = "kernel/sched/cpupri.c.rej"
FIELDS_ANCHOR = (
    "\tint\t\t\t\tnr_cpus_allowed;\n"
    "\tcpumask_t\t\t\tcpus_allowed;\n"
    "\tcpumask_t\t\t\tcpus_requested;\n"
)
FIELDS_RT = """#if defined(CONFIG_SMP) && defined(CONFIG_PREEMPT_RT_BASE)
	int				migrate_disable;
	bool				migrate_disable_scheduled;
#ifdef CONFIG_SCHED_DEBUG
	int				pinned_on_cpu;
#endif
#endif
"""
FORK_ANCHOR = (
    "static void __sched_fork(unsigned long clone_flags, struct task_struct *p)\n"
    "{\n"
    "\tp->on_rq"
)
FORK_RT_INIT = """#if defined(CONFIG_SMP) && defined(CONFIG_PREEMPT_RT_BASE)
	p->migrate_disable = 0;
	p->migrate_disable_scheduled = false;
#ifdef CONFIG_SCHED_DEBUG
	p->pinned_on_cpu = -1;
#endif
#endif
"""
RT_CORE = "return p->migrate_disable;"
UPSTREAM_REJECT_MARKER = ("+#if defined(CONFIG_SMP) && defined(CONFIG_PREEMPT_RT_BASE)\n"
                          "+\tint\t\t\t\tmigrate_disable;\n"
                          "+\tbool\t\t\t\tmigrate_disable_scheduled;")


def once(body: str, needle: str, label: str) -> None:
    actual = body.count(needle)
    if actual != 1:
        raise ValueError(f"{label}: expected one {needle!r}; found {actual}")


def prepare(tree: Path) -> tuple[str, str]:
    for name in (SCHED, CORE, REJECT, CPU_PRI_REJECT):
        if not (tree / name).is_file():
            raise ValueError("Missing Stage28 prerequisite: " + name)
    rejects = len(list(tree.rglob("*.rej")))
    if rejects != 64:
        raise ValueError(f"Stage29 requires 64 pending RT rejects; found {rejects}")

    rejected = (tree / REJECT).read_text(encoding="utf-8")
    once(rejected, UPSTREAM_REJECT_MARKER, REJECT)
    sched = (tree / SCHED).read_text(encoding="utf-8")
    once(sched, FIELDS_ANCHOR, SCHED)
    if re.search(r"\b(?:int|bool)\s+(?:migrate_disable|migrate_disable_scheduled|pinned_on_cpu)\s*;", sched):
        raise ValueError("RT migration fields already present: cannot duplicate")
    if "cpus_ptr;" in sched or re.search(r"\bcpus_mask\s*;", sched):
        raise ValueError("Vendor affinity ABI changed; refuse migration port")

    core = (tree / CORE).read_text(encoding="utf-8")
    once(core, RT_CORE, CORE)
    once(core, FORK_ANCHOR, CORE)
    if "p->migrate_disable = 0;" in core:
        raise ValueError("RT migration fork init already present")

    sched_new = sched.replace(FIELDS_ANCHOR, FIELDS_ANCHOR + FIELDS_RT, 1)
    core_new = core.replace(
        FORK_ANCHOR, FORK_ANCHOR.replace("\n{\n\tp->on_rq", "\n{\n" + FORK_RT_INIT + "\tp->on_rq"), 1
    )
    return sched_new, core_new


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    p.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = p.parse_args()
    tree = args.tree.resolve()
    sched, core = prepare(tree)
    if args.mode == "apply":
        (tree / SCHED).write_text(sched, encoding="utf-8")
        (tree / CORE).write_text(core, encoding="utf-8")
    remain = len(list(tree.rglob("*.rej")))
    if remain != 64:
        raise ValueError("Reject count changed unexpectedly")
    result = {
        "stage": "EXP76_STAGE29_E404_RT_MIGRATION_TASK_ABI",
        "applied": args.mode == "apply",
        "vendor_cpus_allowed_preserved": True,
        "rt_task_migrate_disable_added": args.mode == "apply",
        "rt_task_migrate_disable_scheduled_added": args.mode == "apply",
        "task_fork_rt_fields_initialized": args.mode == "apply",
        "remaining_rejected_files": remain,
        "migration_disable_enable_runtime_implemented": False,
        "rq_nr_pinned_hotplug_lifecycle_implemented": False,
        "sleeping_lock_lifecycle_audited": False,
        "scheduler_core_object_compiled": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    report = args.report.resolve()
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage29-status.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
