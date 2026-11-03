#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage63 RT vendor nandswap spinlock ABI / NO FLASH
"""Reconcile a vendor dynamic spinlock initialization with PREEMPT_RT_FULL.

E404 nandswap assigns __SPIN_LOCK_UNLOCKED(lock) to a heap field. Under RT,
this initializer is not an assignable C expression. Use spin_lock_init()
so the PREEMPT_RT spinlock implementation initializes its internal state.
Only modify the isolated E404 trial source; preserve all 64 RT rejects.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

FILE = "drivers/oplus/nandswap_core.c"
PENDING = "kernel/sched/cpupri.c.rej"
FUNCTION = "static inline struct ns_task_struct *ns_task_insert(pid_t pid, int type)\n{\n"
OLD = (
    "\tntask->state = NS_OUT_STANDBY;\n"
    "\tntask->lock = __SPIN_LOCK_UNLOCKED(lock);\n"
    "\tntask->type = type;\n"
)
NEW = (
    "\tntask->state = NS_OUT_STANDBY;\n"
    "\tspin_lock_init(&ntask->lock);\n"
    "\tntask->type = type;\n"
)


def exactly_once(source: str, needle: str, description: str) -> None:
    count = source.count(needle)
    if count != 1:
        raise ValueError(f"{description}: expected exactly 1 pinned match, saw {count}")


def prepare(tree: Path) -> tuple[str, dict]:
    if not (tree / ".git").is_dir():
        raise ValueError("Stage63 requires isolated E404 trial git checkout")
    if not (tree / FILE).is_file() or not (tree / PENDING).is_file():
        raise ValueError("Stage63 source or outstanding RT rejection is missing")
    rejects = len(list(tree.rglob("*.rej")))
    if rejects != 64:
        raise ValueError(f"Expected 64 outstanding RT rejects, saw {rejects}")

    original = (tree / FILE).read_text(encoding="utf-8")
    exactly_once(original, FUNCTION, "E404 ns_task_insert()")
    exactly_once(original, OLD, "Unmodified vendor nandswap lock initializer")
    start = original.index(FUNCTION)
    end = original.find("\n}\n", start)
    if end <= start:
        raise ValueError("E404 ns_task_insert() closing brace missing")
    fn = original[start:end]
    exactly_once(fn, OLD, "Initializer inside ns_task_insert()")
    exactly_once(fn, "\tntask = kzalloc(sizeof(struct ns_task_struct),\n",
                 "Heap allocation of ns_task_struct")
    exactly_once(fn, "\tif (!ntask)\n\t\tgoto out;\n",
                 "Allocation failure guard")

    updated = original.replace(OLD, NEW, 1)
    exactly_once(updated, NEW, "RT-compatible dynamic spinlock initialization")
    if OLD in updated:
        raise ValueError("Legacy vendor spinlock assignment survived")
    if original[:start] != updated[:start]:
        raise ValueError("Unexpected source modification before ns_task_insert()")

    return updated, {
        "stage": "EXP76_STAGE63_OPLUS_NANDSWAP_RT_SPINLOCK_INIT_NONFLASH",
        "target": FILE,
        "pinned_function": "ns_task_insert",
        "old_assignment_removed": True,
        "dynamic_spinlock_initialized_with_api": True,
        "allocation_failure_guard_preserved": True,
        "outstanding_rt_rejects": 64,
        "full_kernel_link_performed": False,
        "runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
        "original_sha256": hashlib.sha256(original.encode()).hexdigest(),
        "patched_sha256": hashlib.sha256(updated.encode()).hexdigest(),
    }


def execute(tree: Path, report: Path, mode: str) -> dict:
    if mode not in ("verify", "apply"):
        raise ValueError("Stage63 accepts verify/apply only")
    updated, result = prepare(tree)
    if mode == "apply":
        (tree / FILE).write_text(updated, encoding="utf-8")
        if (tree / FILE).read_text(encoding="utf-8") != updated:
            raise ValueError("Stage63 source post-write integrity mismatch")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage63 altered RT rejection evidence")
    result["applied"] = mode == "apply"
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage63-status.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.tree.resolve(), args.report.resolve(), args.mode), indent=2))


if __name__ == "__main__":
    main()
