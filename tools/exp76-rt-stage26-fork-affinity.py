#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage26 ARM64 fork affinity reconciliation / NO FLASH
"""Remove the RT cpus_ptr rebasing step incompatible with E404 value cpumasks.

The E404 task_struct owns embedded cpus_allowed and cpus_requested masks, not
cpus_ptr/cpus_mask. On ARM64 arch_dup_task_struct() copies the entire struct
by value, so no pointer rebasing is required when duplicating the task.

This does not reconcile scheduler core migration, RT migrate_disable or RCU.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

FORK = "kernel/fork.c"
SCHED = "include/linux/sched.h"
ARM64 = "arch/arm64/kernel/process.c"
PENDING = "kernel/sched/cpupri.c.rej"
RT_REBASE = (
    "\tif (orig->cpus_ptr == &orig->cpus_mask)\n"
    "\t\ttsk->cpus_ptr = &tsk->cpus_mask;\n"
)
FORK_COPY_CALL = "\terr = arch_dup_task_struct(tsk, orig);"
ARM_COPY = "\t*dst = *src;"
FIELDS = (
    "\tcpumask_t\t\t\tcpus_allowed;",
    "\tcpumask_t\t\t\tcpus_requested;",
)


def one(body: str, needle: str, path: str) -> None:
    count = body.count(needle)
    if count != 1:
        raise ValueError(f"{path}: expected exactly one {needle!r}, found {count}")


def prepare(root: Path) -> str:
    for rel in (FORK, SCHED, ARM64, PENDING):
        if not (root / rel).is_file():
            raise ValueError("Missing verified Stage21/ARM64 input: " + rel)
    rejects = len(list(root.rglob("*.rej")))
    if rejects != 64:
        raise ValueError(f"Stage26 requires exactly 64 prior RT rejects, found {rejects}")

    sched = (root / SCHED).read_text(encoding="utf-8")
    for field in FIELDS:
        one(sched, field, SCHED)
    if "cpumask_t\t\t\tcpus_mask;" in sched or "cpumask_var_t\t\tcpus_ptr;" in sched:
        raise ValueError("task_struct has a new affinity ABI: re-audit before port")
    if "\tcpus_ptr;" in sched or "\tcpus_mask;" in sched:
        raise ValueError("unexpected cpus_ptr/cpus_mask task fields")

    arch = (root / ARM64).read_text(encoding="utf-8")
    one(arch, "int arch_dup_task_struct(struct task_struct *dst, struct task_struct *src)", ARM64)
    one(arch, ARM_COPY, ARM64)
    start = arch.index("int arch_dup_task_struct(struct task_struct *dst, struct task_struct *src)")
    end = arch.find("\n}", start)
    if end < 0 or ARM_COPY not in arch[start:end]:
        raise ValueError("ARM64 task copy is not a by-value assignment")

    fork = (root / FORK).read_text(encoding="utf-8")
    one(fork, FORK_COPY_CALL, FORK)
    one(fork, RT_REBASE, FORK)
    one(fork, "tsk->wake_q_sleeper.next = NULL;", FORK)
    anchor = (
        "#ifdef CONFIG_STACKPROTECTOR\n"
        "\ttsk->stack_canary = get_random_canary();\n"
        "#endif\n"
        + RT_REBASE
    )
    one(fork, anchor, FORK)
    return fork.replace(RT_REBASE, "", 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = parser.parse_args()
    root = args.tree.resolve()
    body = prepare(root)
    if args.mode == "apply":
        (root / FORK).write_text(body, encoding="utf-8")
    remaining = len(list(root.rglob("*.rej")))
    if remaining != 64:
        raise ValueError("Stage26 source reject manifest changed unexpectedly")
    status = {
        "stage": "EXP76_STAGE26_E404_ARM64_FORK_VALUE_AFFINITY",
        "applied": args.mode == "apply",
        "arm64_task_copy_by_value_verified": True,
        "vendor_cpus_allowed_mask_preserved": True,
        "rt_cpus_ptr_rebase_removed": args.mode == "apply",
        "remaining_rejected_files": remaining,
        "scheduler_core_migration_and_affinity_pending": True,
        "kernel_fork_object_compiled": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    report = args.report.resolve()
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage26-status.json").write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
