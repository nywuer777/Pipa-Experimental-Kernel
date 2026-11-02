#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage27 E404 core affinity ABI port / NO FLASH
"""Reconcile only RT patch cpus_ptr/cpus_mask usages to E404's embedded mask.

This intentionally does not touch __migrate_disabled, migrate_disabled_sched,
saved_state, check_task_state, sleeping_lock, or RT locking semantics.
The goal is a measurable compiler delta, not a bootable kernel.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SOURCE = "kernel/sched/core.c"
SCHED = "include/linux/sched.h"
ARM64 = "arch/arm64/kernel/process.c"
FORK = "kernel/fork.c"
REJECT = "kernel/sched/cpupri.c.rej"

# Each tuple: RT fragment, vendor E404 fragment, expected RT count.
FRAGMENTS = (
    (
        "if (!cpumask_test_cpu(cpu, p->cpus_ptr))",
        "if (!cpumask_test_cpu(cpu, &p->cpus_allowed))",
        1,
    ),
    (
        "\tcpumask_copy(&p->cpus_mask, new_mask);\n"
        "\tif (p->cpus_ptr == &p->cpus_mask)\n"
        "\t\tp->nr_cpus_allowed = cpumask_weight(new_mask);",
        "\tcpumask_copy(&p->cpus_allowed, new_mask);\n"
        "\tp->nr_cpus_allowed = cpumask_weight(new_mask);",
        1,
    ),
    (
        "cpumask_test_cpu(arg->dst_cpu, arg->src_task->cpus_ptr)",
        "cpumask_test_cpu(arg->dst_cpu, &arg->src_task->cpus_allowed)",
        1,
    ),
    (
        "cpumask_test_cpu(arg->src_cpu, arg->dst_task->cpus_ptr)",
        "cpumask_test_cpu(arg->src_cpu, &arg->dst_task->cpus_allowed)",
        1,
    ),
    (
        "cpumask_test_cpu(arg.dst_cpu, arg.src_task->cpus_ptr)",
        "cpumask_test_cpu(arg.dst_cpu, &arg.src_task->cpus_allowed)",
        1,
    ),
    (
        "cpumask_test_cpu(arg.src_cpu, arg.dst_task->cpus_ptr)",
        "cpumask_test_cpu(arg.src_cpu, &arg.dst_task->cpus_allowed)",
        1,
    ),
    (
        "cpumask_subset(span, p->cpus_ptr)",
        "cpumask_subset(span, &p->cpus_allowed)",
        1,
    ),
    (
        "cpumask_test_cpu(target_cpu, p->cpus_ptr)",
        "cpumask_test_cpu(target_cpu, &p->cpus_allowed)",
        1,
    ),
    (
        " * ->cpus_ptr is protected by both rq->lock and p->pi_lock",
        " * ->cpus_allowed is protected by both rq->lock and p->pi_lock",
        1,
    ),
)
VENDOR_FIELDS = (
    "\tcpumask_t\t\t\tcpus_allowed;",
    "\tcpumask_t\t\t\tcpus_requested;",
)


def exactly(body: str, fragment: str, expected: int, path: str) -> None:
    actual = body.count(fragment)
    if actual != expected:
        raise ValueError(f"{path}: expected {expected} occurrence(s) of {fragment!r}; saw {actual}")


def prepare(root: Path) -> tuple[str, int]:
    for rel in (SOURCE, SCHED, ARM64, FORK, REJECT):
        if not (root / rel).is_file():
            raise ValueError("Stage26 source prerequisite missing: " + rel)
    count = len(list(root.rglob("*.rej")))
    if count != 64:
        raise ValueError(f"Stage27 requires 64 pending RT rejects; found {count}")
    sched = (root / SCHED).read_text(encoding="utf-8")
    for field in VENDOR_FIELDS:
        exactly(sched, field, 1, SCHED)
    if re.search(r"\bcpumask(?:_var)?_t\s+cpus_(?:ptr|mask)\s*;", sched):
        raise ValueError("task affinity ABI changed; refuse vendor restoration")
    arch = (root / ARM64).read_text(encoding="utf-8")
    exactly(arch, "int arch_dup_task_struct(struct task_struct *dst, struct task_struct *src)", 1, ARM64)
    exactly(arch, "\t*dst = *src;", 1, ARM64)
    fork = (root / FORK).read_text(encoding="utf-8")
    if "orig->cpus_ptr" in fork or "tsk->cpus_ptr" in fork:
        raise ValueError("Stage26 fork affinity correction is absent")
    core = (root / SOURCE).read_text(encoding="utf-8")
    exactly(core, "int __migrate_disabled(struct task_struct *p)", 1, SOURCE)
    exactly(core, "check_task_state(p, match_state)", 1, SOURCE)
    for rt, vendor, expected in FRAGMENTS:
        exactly(core, rt, expected, SOURCE)
        if vendor in core:
            raise ValueError("Already contains E404 fragment in addition to RT fragment: " + vendor)
        core = core.replace(rt, vendor, expected)
    if re.search(r"->cpus_ptr\b|->cpus_mask\b", core):
        raise ValueError("Unexpected remaining RT pointer affinity expression in core.c")
    if "return p->migrate_disable;" not in core:
        raise ValueError("RT migrate_disable blocker unexpectedly changed")
    return core, count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = parser.parse_args()
    root = args.tree.resolve()
    updated, count = prepare(root)
    if args.mode == "apply":
        (root / SOURCE).write_text(updated, encoding="utf-8")
    after = len(list(root.rglob("*.rej")))
    if after != count:
        raise ValueError("Stage27 changed rejected file count unexpectedly")
    result = {
        "stage": "EXP76_STAGE27_E404_CORE_AFFINITY_MASK_RECONCILIATION",
        "applied": args.mode == "apply",
        "vendor_embedded_cpus_allowed_preserved": True,
        "replaced_rt_affinity_sites": sum(n for _, _, n in FRAGMENTS) - 1,
        "remaining_rejected_files": after,
        "migrate_disable_runtime_semantics_pending": True,
        "check_task_state_runtime_semantics_pending": True,
        "scheduler_core_object_compiled": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    report = args.report.resolve()
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage27-status.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
