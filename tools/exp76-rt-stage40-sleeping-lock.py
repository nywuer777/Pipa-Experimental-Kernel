#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage40 RT sleeping_lock task ABI / NO FLASH
"""Restore the RT-only task_struct sleeping_lock field and fork initialization.

The PREEMPT_RT softirq runner checks sleeping_lock under task pi_lock.
The original pinned sched.h.rej carries this field. Unlike a compiler-only
stub, this ports the exact ABI field and initializes each forked task;
the locking lifecycle and full RT runtime are explicitly NOT verified.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SCHED = "include/linux/sched.h"
REJECT = "include/linux/sched.h.rej"
CORE = "kernel/sched/core.c"
SOFTIRQ = "kernel/softirq.c"
CPU_PRI_REJECT = "kernel/sched/cpupri.c.rej"
UPSTREAM = (
    "+#ifdef CONFIG_PREEMPT_RT_FULL\n"
    "+\tint\t\t\t\tsleeping_lock;\n"
    "+#endif"
)
SCHED_ANCHOR = (
    "#if defined(CONFIG_SMP) && defined(CONFIG_PREEMPT_RT_BASE)\n"
    "\tint\t\t\t\tmigrate_disable;\n"
    "\tbool\t\t\t\tmigrate_disable_scheduled;\n"
    "#ifdef CONFIG_SCHED_DEBUG\n"
    "\tint\t\t\t\tpinned_on_cpu;\n"
    "#endif\n"
    "#endif\n"
    "\n"
    "#ifdef CONFIG_PREEMPT_RCU"
)
SCHED_REPLACEMENT = (
    SCHED_ANCHOR.replace(
        "\n#ifdef CONFIG_PREEMPT_RCU",
        "\n#ifdef CONFIG_PREEMPT_RT_FULL\n"
        "\tint\t\t\t\tsleeping_lock;\n"
        "#endif\n\n#ifdef CONFIG_PREEMPT_RCU",
    )
)
CORE_ANCHOR = (
    "#if defined(CONFIG_SMP) && defined(CONFIG_PREEMPT_RT_BASE)\n"
    "\tp->migrate_disable = 0;\n"
    "\tp->migrate_disable_scheduled = false;\n"
    "#ifdef CONFIG_SCHED_DEBUG\n"
    "\tp->pinned_on_cpu = -1;\n"
    "#endif\n"
    "#endif\n"
    "\tp->on_rq"
)
CORE_REPLACEMENT = CORE_ANCHOR.replace(
    "\n\tp->on_rq",
    "\n#ifdef CONFIG_PREEMPT_RT_FULL\n"
    "\tp->sleeping_lock = 0;\n"
    "#endif\n"
    "\tp->on_rq",
)


def one(value: str, marker: str, path: str) -> None:
    found = value.count(marker)
    if found != 1:
        raise ValueError(f"{path}: expected 1 {marker!r}, observed {found}")


def prepare(root: Path) -> tuple[str, str]:
    for path in (SCHED, REJECT, CORE, SOFTIRQ, CPU_PRI_REJECT):
        if not (root / path).is_file():
            raise ValueError("Stage40 pinned source missing: " + path)
    rejects = len(list(root.rglob("*.rej")))
    if rejects != 64:
        raise ValueError(f"Stage40 requires 64 unresolved rejects, got {rejects}")
    reject = (root / REJECT).read_text(encoding="utf-8")
    one(reject, UPSTREAM, REJECT)
    sched = (root / SCHED).read_text(encoding="utf-8")
    core = (root / CORE).read_text(encoding="utf-8")
    softirq = (root / SOFTIRQ).read_text(encoding="utf-8")
    one(sched, SCHED_ANCHOR, SCHED)
    one(core, CORE_ANCHOR, CORE)
    one(softirq, "tsk->sleeping_lock", SOFTIRQ)
    if re.search(r"\bint\s+sleeping_lock\s*;", sched):
        raise ValueError("task_struct sleeping_lock already defined")
    if "p->sleeping_lock = 0;" in core:
        raise ValueError("scheduler fork already initializes sleeping_lock")
    if re.search(r"\bcpus_ptr\s*;", sched) or re.search(r"\bcpus_mask\s*;", sched):
        raise ValueError("Incompatible upstream RT cpumask ABI")
    return (
        sched.replace(SCHED_ANCHOR, SCHED_REPLACEMENT, 1),
        core.replace(CORE_ANCHOR, CORE_REPLACEMENT, 1),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = parser.parse_args()
    tree = args.tree.resolve()
    sched, core = prepare(tree)
    if args.mode == "apply":
        (tree / SCHED).write_text(sched, encoding="utf-8")
        (tree / CORE).write_text(core, encoding="utf-8")
    rejects = len(list(tree.rglob("*.rej")))
    if rejects != 64:
        raise ValueError("Unexpected RT reject count after Stage40")
    status = {
        "stage": "EXP76_STAGE40_RT_SLEEPING_LOCK_TASK_ABI",
        "applied": args.mode == "apply",
        "original_rt_reject_sleeping_lock_verified": True,
        "rt_softirq_runner_sleeping_lock_reference_verified": True,
        "task_field_and_fork_initialization_ported": args.mode == "apply",
        "vendor_embedded_cpus_allowed_preserved": True,
        "remaining_rejected_files": rejects,
        "sleeping_lock_runtime_lifecycle_verified": False,
        "softirq_object_compiled": False,
        "migration_runtime_implemented": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    report = args.report.resolve()
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage40-status.json").write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
