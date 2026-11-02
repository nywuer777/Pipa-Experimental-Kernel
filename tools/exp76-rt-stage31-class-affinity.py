#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage31 vendor scheduler affinity ABI / NO FLASH
"""Port PREEMPT_RT cpus_ptr references in rt/fair/deadline to E404 cpus_allowed.

These nine exact text changes (eight C expressions and one documentation
comment) restore the vendor's embedded task_struct cpumask ABI, as already
validated for sched/core.c in Stage27. No migration policy/lock changes.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SCHED = "include/linux/sched.h"
PENDING = "kernel/sched/cpupri.c.rej"
BASELINE_FIELDS = (
    "\tint\t\t\t\tnr_cpus_allowed;\n"
    "\tcpumask_t\t\t\tcpus_allowed;\n"
    "\tcpumask_t\t\t\tcpus_requested;\n"
)
# Each (expected POST-RT fragment, vendor E404 equivalent) must occur once.
REPLACEMENTS: dict[str, tuple[tuple[str, str], ...]] = {
    "kernel/sched/rt.c": (
        ("cpumask_test_cpu(cpu, p->cpus_ptr)",
         "cpumask_test_cpu(cpu, &p->cpus_allowed)"),
        ("cpumask_test_cpu(lowest_rq->cpu, task->cpus_ptr)",
         "cpumask_test_cpu(lowest_rq->cpu, &task->cpus_allowed)"),
    ),
    "kernel/sched/fair.c": (
        ("cpumask_test_cpu(env->src_cpu, cur->cpus_ptr)",
         "cpumask_test_cpu(env->src_cpu, &cur->cpus_allowed)"),
        ("cpumask_test_cpu(cpu, env->p->cpus_ptr)",
         "cpumask_test_cpu(cpu, &env->p->cpus_allowed)"),
        ("cpumask_intersects(sched_domain_span(sd), p->cpus_ptr)",
         "cpumask_intersects(sched_domain_span(sd), &p->cpus_allowed)"),
        (" * groups is inadequate due to ->cpus_ptr constraints.",
         " * groups is inadequate due to ->cpus_allowed constraints."),
    ),
    "kernel/sched/deadline.c": (
        ("cpumask_any_and(cpu_active_mask, p->cpus_ptr)",
         "cpumask_any_and(cpu_active_mask, &p->cpus_allowed)"),
        ("cpumask_test_cpu(cpu, p->cpus_ptr)",
         "cpumask_test_cpu(cpu, &p->cpus_allowed)"),
        ("cpumask_test_cpu(later_rq->cpu, task->cpus_ptr)",
         "cpumask_test_cpu(later_rq->cpu, &task->cpus_allowed)"),
    ),
}
EXPECTED = sum(len(parts) for parts in REPLACEMENTS.values())


def once(contents: str, needle: str, path: str) -> None:
    count = contents.count(needle)
    if count != 1:
        raise ValueError(f"{path}: expected one {needle!r}, found {count}")


def prepare(root: Path) -> dict[str, str]:
    for path in (SCHED, PENDING, *REPLACEMENTS):
        if not (root / path).is_file():
            raise ValueError("Missing Stage30 E404 trial source: " + path)
    count = len(list(root.rglob("*.rej")))
    if count != 64:
        raise ValueError(f"Stage31 requires 64 prior RT rejects; found {count}")
    sched = (root / SCHED).read_text(encoding="utf-8")
    once(sched, BASELINE_FIELDS, SCHED)
    if re.search(r"\bcpumask(?:_var)?_t\s+cpus_(?:ptr|mask)\s*;", sched):
        raise ValueError("task_struct affinity ABI changed: refusing Stage31")

    replacements = {}
    for path, parts in REPLACEMENTS.items():
        source = (root / path).read_text(encoding="utf-8")
        updated = source
        for rt, vendor in parts:
            once(updated, rt, path)
            if vendor in updated:
                raise ValueError(f"{path}: RT and vendor fragments both present")
            updated = updated.replace(rt, vendor, 1)
        if re.search(r"->cpus_ptr\b|->cpus_mask\b", updated):
            raise ValueError(f"{path}: unrecognized remaining RT affinity reference")
        replacements[path] = updated
    return replacements


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = parser.parse_args()
    root = args.tree.resolve()
    replacements = prepare(root)
    if args.mode == "apply":
        for path, updated in replacements.items():
            (root / path).write_text(updated, encoding="utf-8")
    remaining = len(list(root.rglob("*.rej")))
    if remaining != 64:
        raise ValueError("Stage31 unexpectedly changed rejected RT file count")
    result = {
        "stage": "EXP76_STAGE31_E404_RT_FAIR_DL_CLASS_AFFINITY",
        "applied": args.mode == "apply",
        "replaced_fragments": EXPECTED,
        "stage32_fair_numa_affinity_reconciled": True,
        "updated_source_paths": sorted(replacements),
        "vendor_embedded_cpus_allowed_preserved": True,
        "remaining_rejected_files": remaining,
        "migration_runtime_implemented": False,
        "rt_locking_semantics_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    report = args.report.resolve()
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage31-status.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
