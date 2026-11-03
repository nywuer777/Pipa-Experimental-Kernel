#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage64 ION secure-heap RT spinlock / NO FLASH
"""Replace a static spinlock initializer assignment on a heap-allocated ION object.

The pinned E404 secure heap assigns __SPIN_LOCK_UNLOCKED(work_lock) to a
runtime field. PREEMPT_RT_FULL changes the spinlock representation; static
initializers must not be assigned to existing objects. spin_lock_init() is
the proper API for this dynamically allocated lock. This tool edits only
the isolated trial tree, never a production kernel or boot partition.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

FILE = "drivers/staging/android/ion/ion_system_secure_heap.c"
PENDING = "kernel/sched/cpupri.c.rej"
FUNCTION = (
    "struct ion_heap *ion_system_secure_heap_create(struct ion_platform_heap *unused)\n"
    "{\n"
)
OLD = (
    "\theap->destroy_heap = false;\n"
    "\theap->work_lock = __SPIN_LOCK_UNLOCKED(heap->work_lock);\n"
    "\tINIT_LIST_HEAD(&heap->prefetch_list);\n"
)
NEW = (
    "\theap->destroy_heap = false;\n"
    "\tspin_lock_init(&heap->work_lock);\n"
    "\tINIT_LIST_HEAD(&heap->prefetch_list);\n"
)


def one(source: str, fragment: str, label: str) -> None:
    seen = source.count(fragment)
    if seen != 1:
        raise ValueError(f"{label}: expected exactly 1 pinned fragment, saw {seen}")


def prepare(tree: Path) -> tuple[str, dict]:
    if not (tree / ".git").is_dir():
        raise ValueError("Stage64 requires isolated E404 trial git checkout")
    if not (tree / FILE).is_file() or not (tree / PENDING).is_file():
        raise ValueError("Stage64 source or RT reject evidence missing")
    rejects = len(list(tree.rglob("*.rej")))
    if rejects != 64:
        raise ValueError(f"Expected 64 outstanding RT reject files, found {rejects}")
    original = (tree / FILE).read_text(encoding="utf-8")
    one(original, FUNCTION, "E404 secure heap creation function")
    one(original, OLD, "E404 static initializer assignment")
    one(original, "\tspinlock_t work_lock;\n", "Secure heap spinlock field")
    begin = original.index(FUNCTION)
    end = original.find("\n}\n", begin)
    if end < begin:
        raise ValueError("E404 secure heap creation body not closed")
    body = original[begin:end]
    one(body, OLD, "Initializer inside secure heap creation")
    one(body, "\theap = kzalloc(sizeof(*heap), GFP_KERNEL);\n",
        "Dynamic secure heap allocation")
    one(body, "\tif (!heap)\n\t\treturn ERR_PTR(-ENOMEM);\n",
        "Secure heap allocation failure guard")
    one(body, "\tINIT_DELAYED_WORK(&heap->prefetch_work,\n",
        "Secure heap delayed work initializer")
    updated = original.replace(OLD, NEW, 1)
    one(updated, NEW, "RT-compatible spinlock initialization")
    if OLD in updated:
        raise ValueError("Legacy ION secure heap lock assignment survived")
    if original[:begin] != updated[:begin]:
        raise ValueError("Unexpected source modification before secure heap creation")
    return updated, {
        "stage": "EXP76_STAGE64_ION_SECURE_HEAP_RT_SPINLOCK_INIT_NONFLASH",
        "target": FILE,
        "pinned_function": "ion_system_secure_heap_create",
        "static_initializer_assignment_removed": True,
        "dynamic_spinlock_initialized_with_api": True,
        "allocation_failure_guard_preserved": True,
        "delayed_work_setup_preserved": True,
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
        raise ValueError("Stage64 accepts verify/apply only")
    updated, status = prepare(tree)
    if mode == "apply":
        (tree / FILE).write_text(updated, encoding="utf-8")
        if (tree / FILE).read_text(encoding="utf-8") != updated:
            raise ValueError("Stage64 post-write source integrity mismatch")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage64 altered outstanding RT rejects")
    status["applied"] = mode == "apply"
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage64-status.json").write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8"
    )
    return status


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.tree.resolve(), args.report.resolve(), args.mode),
                     indent=2))


if __name__ == "__main__":
    main()
