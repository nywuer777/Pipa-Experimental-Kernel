#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage89 RT proc swait include / NO FLASH
"""Port the exact rejected linux/swait.h include into E404 fs/proc/base.c.

This does not claim scheduler runtime compatibility. Retain the original
rejected hunk and verify no other proc source changes were introduced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

STAGE = "EXP76_STAGE89_PROC_SWAIT_INCLUDE_RT_REJECT_PORT_NONFLASH"
TARGET = "fs/proc/base.c"
REJECT = TARGET + ".rej"
HEADER = "include/linux/swait.h"
HASH = "417c207cb7d9d129fbbe31fedf0959d6a983d726d524af48cd40fa9e06225719"
STAGE82 = "EXP76_STAGE82_OUTSTANDING_RT_REJECT_HUNK_INVENTORY_NONFLASH"
REPORT = "stage89-status.json"
ANCHOR = "#include <linux/posix-timers.h>\n"
NEW = "#include <linux/swait.h>\n"
UPSTREAM_HEADER = "@@ -95,6 +95,7 @@"


def sha(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def verify(tree: Path, inventory: Path) -> tuple[str, dict]:
    if not (tree / ".git").is_dir():
        raise ValueError("Stage89 requires pinned isolated E404 trial Git tree")
    target = tree / TARGET
    reject = tree / REJECT
    header = tree / HEADER
    if not target.is_file() or not reject.is_file() or not header.is_file():
        raise ValueError("Stage89 requires original proc source, reject and RT swait header")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage89 requires exactly 64 original RT rejects")
    if sha(reject.read_bytes()) != HASH:
        raise ValueError("Stage89 RT proc rejected hunk SHA256 mismatch")
    lines = reject.read_text(encoding="utf-8").splitlines()
    hunks = [x for x in lines if x.startswith("@@ ")]
    added = [x for x in lines if x.startswith("+") and not x.startswith("+++")]
    removed = [x for x in lines if x.startswith("-") and not x.startswith("---")]
    if (
        len(hunks) != 1
        or not hunks[0].startswith(UPSTREAM_HEADER)
        or added != ["+" + NEW.rstrip("\n")]
        or removed
    ):
        raise ValueError("Stage89 rejected upstream swait include hunk changed")
    if not inventory.is_file():
        raise ValueError("Stage89 requires Stage82 immutable reject inventory")
    data = json.loads(inventory.read_text(encoding="utf-8"))
    entries = [x for x in data.get("entries", []) if x.get("source") == TARGET]
    if not (
        data.get("stage") == STAGE82
        and data.get("remaining_rejected_files") == 64
        and data.get("source_modified") is False
        and data.get("rejects_deleted") is False
        and len(entries) == 1
        and entries[0].get("reject_sha256") == HASH
        and entries[0].get("hunk_count") == 1
        and entries[0].get("added_lines") == 1
        and entries[0].get("removed_lines") == 0
    ):
        raise ValueError("Stage89 Stage82 immutable proc hunk provenance mismatch")
    header_text = header.read_text(encoding="utf-8")
    for marker in ("struct swait_queue_head {", "swait_event_interruptible_exclusive("):
        if marker not in header_text:
            raise ValueError("Stage89 actual RT swait header API incomplete: " + marker)
    current = target.read_text(encoding="utf-8")
    if current.count(ANCHOR) != 1:
        raise ValueError("Stage89 vendor proc include anchor mismatch")
    if NEW in current:
        raise ValueError("Stage89 proc swait already included; duplicate prohibited")
    if "CONFIG_E404_ATTRIBUTES" not in current:
        raise ValueError("Stage89 lost E404 vendor proc code")
    updated = current.replace(ANCHOR, ANCHOR + NEW, 1)
    if updated.replace(ANCHOR + NEW, ANCHOR, 1) != current:
        raise ValueError("Stage89 unexpected source change beyond swait include")
    return updated, {
        "stage": STAGE,
        "target": TARGET,
        "source_original_sha256": sha(current.encode()),
        "source_patched_sha256": sha(updated.encode()),
        "rejected_hunk_sha256": HASH,
        "upstream_hunks_reviewed": 1,
        "upstream_includes_added": 1,
        "vendor_e404_code_preserved": True,
        "rt_swait_api_present": True,
        "original_reject_retained": True,
        "remaining_rejected_files": 64,
        "scheduler_semantic_review_complete": False,
        "full_kernel_link_rechecked": False,
        "runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }


def execute(tree: Path, inventory: Path, report: Path, mode: str) -> dict:
    if mode not in ("verify", "apply"):
        raise ValueError("Stage89 mode must be verify or apply")
    updated, status = verify(tree, inventory)
    if mode == "apply":
        (tree / TARGET).write_text(updated, encoding="utf-8")
        if sha((tree / TARGET).read_bytes()) != status["source_patched_sha256"]:
            raise ValueError("Stage89 post-write proc source integrity failed")
    if sha((tree / REJECT).read_bytes()) != HASH:
        raise ValueError("Stage89 modified original RT proc reject")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage89 altered original RT reject evidence")
    status["applied"] = mode == "apply"
    report.mkdir(parents=True, exist_ok=True)
    (report / REPORT).write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8"
    )
    return status


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = parser.parse_args()
    print(json.dumps(
        execute(
            args.tree.resolve(), args.inventory.resolve(),
            args.report.resolve(), args.mode,
        ), indent=2,
    ))


if __name__ == "__main__":
    main()
