#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage74 radix-tree locallock include / NO FLASH
"""Restore the missing locallock declaration for RT radix tree preloading.

The pinned 4.19.325-rt140 patch added DEFINE_LOCAL_IRQ_LOCK and local
locking calls in lib/radix-tree.c but the E404 conflict resolution left out
linux/locallock.h. Include that existing RT compatibility header only.
No lock semantics are rewritten and no *.rej files are touched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

FILE = "lib/radix-tree.c"
HEADER = "include/linux/locallock.h"
REJECT = "kernel/sched/cpupri.c.rej"
ORIGINAL_INCLUDE = "#include <linux/percpu.h>\n"
PATCHED_INCLUDE = (
    "#include <linux/percpu.h>\n"
    "#include <linux/locallock.h>\n"
)
RT_DECLARATION = "static DEFINE_LOCAL_IRQ_LOCK(radix_tree_preloads_lock);"
RT_CALLS = (
    "get_locked_var(radix_tree_preloads_lock",
    "put_locked_var(radix_tree_preloads_lock",
    "local_lock(radix_tree_preloads_lock",
    "local_unlock(radix_tree_preloads_lock",
)


def prepare(tree: Path) -> tuple[str, dict]:
    if not (tree / ".git").is_dir():
        raise ValueError("Stage74 requires isolated E404 trial git checkout")
    if not (tree / FILE).is_file() or not (tree / HEADER).is_file():
        raise ValueError("Stage74 requires pinned radix-tree and locallock sources")
    if not (tree / REJECT).is_file():
        raise ValueError("Stage74 requires outstanding RT scheduler reject sentinel")
    remaining = len(list(tree.rglob("*.rej")))
    if remaining != 64:
        raise ValueError("Stage74 requires 64 outstanding RT rejection files")
    current = (tree / FILE).read_text(encoding="utf-8")
    if current.count(ORIGINAL_INCLUDE) != 1:
        raise ValueError("Pinned radix-tree percpu include anchor drift")
    if current.count(RT_DECLARATION) != 1:
        raise ValueError("Pinned RT radix-tree local IRQ lock declaration drift")
    for api in RT_CALLS:
        if api not in current:
            raise ValueError("RT radix-tree preload locking API missing: " + api)
    if "#include <linux/locallock.h>" in current:
        raise ValueError("radix-tree locallock already included")
    locallock = (tree / HEADER).read_text(encoding="utf-8")
    for marker in ("DEFINE_LOCAL_IRQ_LOCK(", "get_locked_var(",
                   "put_locked_var(", "local_lock(", "local_unlock("):
        if marker not in locallock:
            raise ValueError("Pinned RT locallock header missing API: " + marker)
    patched = current.replace(ORIGINAL_INCLUDE, PATCHED_INCLUDE, 1)
    if patched.count("#include <linux/locallock.h>") != 1:
        raise ValueError("Radix-tree locallock include count mismatch")
    if patched.replace(PATCHED_INCLUDE, ORIGINAL_INCLUDE, 1) != current:
        raise ValueError("Unexpected modification outside the RT locallock include")
    result = {
        "stage": "EXP76_STAGE74_RADIX_TREE_LOCALLOCK_INCLUDE_NONFLASH",
        "target": FILE,
        "rt_lock_declaration_preserved": True,
        "rt_lock_calls_preserved": True,
        "existing_locallock_api_verified": True,
        "locallock_header_added": True,
        "remaining_rejected_files": 64,
        "full_kernel_link_performed": False,
        "runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
        "original_sha256": hashlib.sha256(current.encode()).hexdigest(),
        "patched_sha256": hashlib.sha256(patched.encode()).hexdigest(),
    }
    return patched, result


def execute(tree: Path, report: Path, mode: str) -> dict:
    if mode not in ("verify", "apply"):
        raise ValueError("Stage74 accepts verify/apply only")
    patched, status = prepare(tree)
    if mode == "apply":
        (tree / FILE).write_text(patched, encoding="utf-8")
        if (tree / FILE).read_text(encoding="utf-8") != patched:
            raise ValueError("Stage74 post-write source integrity check failed")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage74 changed outstanding RT rejects")
    status["applied"] = mode == "apply"
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage74-status.json").write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8"
    )
    return status


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = parser.parse_args()
    print(json.dumps(execute(
        args.tree.resolve(), args.report.resolve(), args.mode,
    ), indent=2))


if __name__ == "__main__":
    main()
