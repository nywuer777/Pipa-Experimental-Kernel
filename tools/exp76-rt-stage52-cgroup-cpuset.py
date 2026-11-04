#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage52 E404-RT cgroup and cpuset integration / NO FLASH
"""Restore E404 cgroup declarations and reconcile vendor cpuset RT locking.

Official 4.19.325-rt140 patch replaces blk-cgroup.h's cgroup.h include
with kthread.h; the E404 vendor code still requires complete cgroup types
and task_css(). E404 already includes kthread.h elsewhere in that header.
The RT patch also converts callback_lock to a raw spinlock and changes
cpuset_fork() to the absent cpus_ptr ABI, while two vendor lock pairs stay
typed as ordinary spinlocks. Fix only these compiler-proven mismatches.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

BLK = "include/linux/blk-cgroup.h"
CPUSET = "kernel/cgroup/cpuset.c"
BLK_ORIGINAL = "#include <linux/kthread.h>\n#include <linux/percpu_counter.h>\n"
BLK_RESTORED = "#include <linux/cgroup.h>\n#include <linux/percpu_counter.h>\n"
LOCK_DECL = "static DEFINE_RAW_SPINLOCK(callback_lock);\n"
CPU_MASK_OLD = (
    "\tspin_lock_irq(&callback_lock);\n"
    "\tcpumask_copy(cs->cpus_allowed, trialcs->cpus_allowed);\n"
    "\tcpumask_copy(cs->cpus_requested, trialcs->cpus_requested);\n"
    "\tspin_unlock_irq(&callback_lock);\n"
)
PARENT_MASK_OLD = (
    "\tspin_lock_irq(&callback_lock);\n"
    "\tcs->mems_allowed = parent->mems_allowed;\n"
    "\tcs->effective_mems = parent->mems_allowed;\n"
    "\tcpumask_copy(cs->cpus_allowed, parent->cpus_allowed);\n"
    "\tcpumask_copy(cs->cpus_requested, parent->cpus_requested);\n"
    "\tcpumask_copy(cs->effective_cpus, parent->cpus_allowed);\n"
    "\tspin_unlock_irq(&callback_lock);\n"
)
FORK_OLD = "\tset_cpus_allowed_ptr(task, current->cpus_ptr);\n"
FORK_NEW = "\tset_cpus_allowed_ptr(task, &current->cpus_allowed);\n"
LEFTOVER = re.compile(
    r"(?<!raw_)\bspin_(?:lock_irq|unlock_irq|lock_irqsave|unlock_irqrestore)"
    r"\s*\(\s*&callback_lock\s*[,)]"
)


def one(text: str, marker: str, label: str) -> None:
    count = text.count(marker)
    if count != 1:
        raise ValueError(f"{label}: expected exactly one pinned fragment, got {count}")


def prepare(tree: Path) -> tuple[dict[str, str], dict]:
    if not (tree / ".git").is_dir():
        raise ValueError("Expected isolated E404 git checkout")
    for name in (BLK, CPUSET, "kernel/sched/cpupri.c.rej"):
        if not (tree / name).is_file():
            raise ValueError("Missing E404 trial source or RT reject: " + name)
    rejects = len(list(tree.rglob("*.rej")))
    if rejects != 64:
        raise ValueError(f"Expected 64 RT rejects, found {rejects}")
    blk = (tree / BLK).read_text(encoding="utf-8")
    cpuset = (tree / CPUSET).read_text(encoding="utf-8")

    one(blk, BLK_ORIGINAL, "RT blk-cgroup initial kthread include")
    if blk.count("#include <linux/kthread.h>\n") != 2:
        raise ValueError("E404 blk-cgroup kthread include layout changed")
    if "#include <linux/cgroup.h>\n" in blk:
        raise ValueError("blk-cgroup cgroup include already present")
    one(blk, "struct cgroup_subsys_state\tcss;", "E404 cgroup CSS field")
    one(blk, "return css_to_blkcg(task_css(current, io_cgrp_id));",
        "E404 task_css API")
    updated_blk = blk.replace(BLK_ORIGINAL, BLK_RESTORED, 1)
    if updated_blk.count("#include <linux/kthread.h>\n") != 1:
        raise ValueError("kthread.h required by vendor functions was lost")

    one(cpuset, LOCK_DECL, "RT callback_lock raw spinlock")
    one(cpuset, CPU_MASK_OLD, "Vendor cpus_requested callback lock pair")
    one(cpuset, PARENT_MASK_OLD, "Vendor parent mask callback lock pair")
    one(cpuset, FORK_OLD, "Upstream cpus_ptr incompatible E404 task ABI")
    unexpected = LEFTOVER.findall(cpuset)
    if len(unexpected) != 4:
        raise ValueError(f"Unexpected unconverted callback_lock uses: {len(unexpected)}")
    new_cpuset = (
        cpuset.replace(
            CPU_MASK_OLD,
            CPU_MASK_OLD.replace("spin_lock_irq(", "raw_spin_lock_irq(")
            .replace("spin_unlock_irq(", "raw_spin_unlock_irq("), 1,
        ).replace(
            PARENT_MASK_OLD,
            PARENT_MASK_OLD.replace("spin_lock_irq(", "raw_spin_lock_irq(")
            .replace("spin_unlock_irq(", "raw_spin_unlock_irq("), 1,
        ).replace(FORK_OLD, FORK_NEW, 1)
    )
    if LEFTOVER.search(new_cpuset):
        raise ValueError("Unconverted non-raw callback_lock operation remains")
    one(new_cpuset, LOCK_DECL, "Preserved RT raw callback_lock definition")
    one(new_cpuset, FORK_NEW, "Preserved E404 task cpus_allowed ABI")
    return {BLK: updated_blk, CPUSET: new_cpuset}, {
        "stage": "EXP76_STAGE52_CGROUP_HEADER_CPUSET_RAW_LOCK_NONFLASH",
        "original_sha256": {
            BLK: hashlib.sha256(blk.encode()).hexdigest(),
            CPUSET: hashlib.sha256(cpuset.encode()).hexdigest(),
        },
        "patched_sha256": {
            BLK: hashlib.sha256(updated_blk.encode()).hexdigest(),
            CPUSET: hashlib.sha256(new_cpuset.encode()).hexdigest(),
        },
        "cgroup_header_restored": True,
        "kthread_header_preserved": True,
        "callback_lock_remains_raw": True,
        "vendor_raw_lock_pairs_reconciled": 2,
        "e404_task_cpus_allowed_abi_restored": True,
        "remaining_rejected_files": 64,
        "rt_runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }


def execute(tree: Path, report: Path, mode: str) -> dict:
    if mode not in ("verify", "apply"):
        raise ValueError("Unsupported Stage52 mode")
    edits, status = prepare(tree)
    if mode == "apply":
        for name, value in edits.items():
            (tree / name).write_text(value, encoding="utf-8")
        for name, value in edits.items():
            if (tree / name).read_text(encoding="utf-8") != value:
                raise ValueError("Stage52 source write verification failed: " + name)
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage52 changed the RT reject count")
    status["applied"] = mode == "apply"
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage52-status.json").write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8"
    )
    return status


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--mode", choices=("apply", "verify"), required=True)
    args = p.parse_args()
    print(json.dumps(execute(args.tree.resolve(), args.report.resolve(), args.mode), indent=2))


if __name__ == "__main__":
    main()
