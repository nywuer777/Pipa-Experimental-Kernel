#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage21 E404 RCU include reconciliation / NO FLASH
"""Restore E404's rbtree -> rcupdate include, preserving vendor RCU publishing.

The older upstream RT patch introduced rcu_assign_pointer.h via rbtree.h,
which collides with the current E404 rcupdate.h macro. This correction
changes only the include edge; it does not claim that the RCU runtime port,
affinity ABI, or scheduler sleeping locks are complete.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

TREE = "include/linux/rbtree.h"
RCUPDATE = "include/linux/rcupdate.h"
NEW_RCU = "include/linux/rcu_assign_pointer.h"
NEW_RCU_SHA256 = "32bf555037ac9f9506dbd0ceef386f31d5bc3fdc79b75ac9a1184ce95df07e1d"
RT_IMPORT = "#include <linux/rcu_assign_pointer.h>\n"
E404_IMPORT = "#include <linux/rcupdate.h>\n"


def one(body: str, phrase: str, where: str) -> None:
    count = body.count(phrase)
    if count != 1:
        raise ValueError(f"{where}: expected one {phrase!r}, found {count}")


def prepare(root: Path) -> str:
    for path in (TREE, RCUPDATE, NEW_RCU, "kernel/sched/cpupri.c.rej"):
        if not (root / path).is_file():
            raise ValueError("Required Stage20 input not present: " + path)
    if (root / "include/linux/swap.h.rej").exists():
        raise ValueError("Stage20 swap locallock reject is still pending")
    rejects = len(list(root.rglob("*.rej")))
    if rejects != 64:
        raise ValueError(f"Stage21 requires 64 preexisting rejected files, found {rejects}")

    rb = (root / TREE).read_text(encoding="utf-8")
    rcu = (root / RCUPDATE).read_text(encoding="utf-8")
    extra = (root / NEW_RCU).read_bytes()
    sha = hashlib.sha256(extra).hexdigest()
    if sha != NEW_RCU_SHA256:
        raise ValueError("Upstream RT helper source drift: " + sha)
    one(rb, RT_IMPORT, TREE)
    if E404_IMPORT in rb:
        raise ValueError("Vendor include already present alongside RT include")
    one(rb, "rcu_assign_pointer(*rb_link, node);", TREE)
    one(rcu, "#define rcu_assign_pointer(p, v)", RCUPDATE)
    if RT_IMPORT in rcu:
        raise ValueError("Stage19 duplicate import cleanup not applied")
    helper = extra.decode("utf-8")
    one(helper, "#define rcu_assign_pointer(p, v)", NEW_RCU)
    return rb.replace(RT_IMPORT, E404_IMPORT, 1)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    p.add_argument("--mode", required=True, choices=("verify", "apply"))
    a = p.parse_args()
    root = a.tree.resolve()
    output = prepare(root)
    if a.mode == "apply":
        (root / TREE).write_text(output, encoding="utf-8")
    remaining = len(list(root.rglob("*.rej")))
    if remaining != 64:
        raise ValueError("Unexpected reject count change after Stage21: " + str(remaining))
    status = {
        "stage": "EXP76_RT_STAGE21_E404_RCU_INCLUDE_RESTORED",
        "applied": a.mode == "apply",
        "rbtree_vendor_rcupdate_import": a.mode == "apply",
        "rcu_assign_pointer_vendor_macro_preserved": True,
        "upstream_rcu_helper_unreferenced_by_rbtree": a.mode == "apply",
        "rcu_redefinition_warning_clearance_unverified": True,
        "remaining_rejected_files": remaining,
        "scheduler_affinity_abi_pending": True,
        "sleeping_lock_lifecycle_review_required": True,
        "kernel_built": False,
        "flash_ready": False,
    }
    report = a.report.resolve()
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage21-status.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
