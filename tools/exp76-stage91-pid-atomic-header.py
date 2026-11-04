#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 GitHub Actions / EXP76 Stage91 atomic PID header RT hunk / NO FLASH
"""Port the pinned RT atomic.h dependency into E404 include/linux/pid.h.

A single RT patch hunk adds an explicit atomic API header; E404's struct pid
already uses atomic_t and get_pid() already calls atomic_inc. Import only the
dependency, preserving vendor PID layout, reject evidence and kernel ABI.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

STAGE = "EXP76_STAGE91_PINNED_PID_ATOMIC_HEADER_DEPENDENCY_NONFLASH"
REPORT = "stage91-status.json"
TARGET = "include/linux/pid.h"
REJECT = TARGET + ".rej"
HEADER = "include/linux/atomic.h"
REJECT_SHA = "bc68702b84df9b927e5753d3ea1bece48787733eab2f55b90849d39369a7c403"
INVENTORY_STAGE = "EXP76_STAGE82_OUTSTANDING_RT_REJECT_HUNK_INVENTORY_NONFLASH"
ANCHOR = "#include <linux/rculist.h>\n"
INSERT = "#include <linux/atomic.h>\n"
UPSTREAM_HEADER = "@@ -3,6 +3,7 @@"
PID_ATOMIC_MARKERS = ("atomic_t count;", "atomic_inc(&pid->count);")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def prepare(tree: Path, index_file: Path) -> tuple[str, dict]:
    if not (tree / ".git").is_dir():
        raise ValueError("Stage91 requires pinned E404 isolated Git checkout")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage91 requires original 64 RT rejects")
    target = tree / TARGET
    reject = tree / REJECT
    atomic_header = tree / HEADER
    if not all(x.is_file() for x in (target, reject, atomic_header)):
        raise ValueError("Stage91 pinned PID sources, atomic.h or reject missing")
    if sha256(reject.read_bytes()) != REJECT_SHA:
        raise ValueError("Stage91 pinned PID RT reject SHA256 drift")
    rejected = reject.read_text(encoding="utf-8")
    headings = [line for line in rejected.splitlines() if line.startswith("@@ ")]
    additions = [line for line in rejected.splitlines()
                 if line.startswith("+") and not line.startswith("+++")]
    removals = [line for line in rejected.splitlines()
                if line.startswith("-") and not line.startswith("---")]
    if not (
        len(headings) == 1
        and headings[0].startswith(UPSTREAM_HEADER)
        and additions == ["+" + INSERT.strip()]
        and not removals
    ):
        raise ValueError("Stage91 RT PID atomic header rejected hunk drift")
    if not index_file.is_file():
        raise ValueError("Stage91 original Stage82 rejection inventory missing")
    index = json.loads(index_file.read_text(encoding="utf-8"))
    entries = [x for x in index.get("entries", []) if x.get("source") == TARGET]
    if not (
        index.get("stage") == INVENTORY_STAGE
        and index.get("remaining_rejected_files") == 64
        and index.get("source_modified") is False
        and index.get("rejects_deleted") is False
        and len(entries) == 1
        and entries[0].get("reject_sha256") == REJECT_SHA
        and entries[0].get("hunk_count") == 1
        and entries[0].get("added_lines") == 1
        and entries[0].get("removed_lines") == 0
    ):
        raise ValueError("Stage91 pinned Stage82 PID hunk provenance drift")
    atomic_source = atomic_header.read_text(encoding="utf-8")
    for marker in ("#include <asm/atomic.h>", "atomic_t", "#ifndef _LINUX_ATOMIC_H"):
        if marker not in atomic_source:
            raise ValueError("Stage91 actual vendor atomic.h is incomplete: " + marker)
    original = target.read_text(encoding="utf-8")
    if original.count(ANCHOR) != 1:
        raise ValueError("Stage91 pinned E404 PID include anchor drift")
    if INSERT in original:
        raise ValueError("Stage91 PID atomic.h was already included")
    for marker in PID_ATOMIC_MARKERS:
        if original.count(marker) != 1:
            raise ValueError("Stage91 original PID atomic API usage drift: " + marker)
    for marker in ("#include <linux/wait.h>", "wait_queue_head_t wait_pidfd;"):
        if marker not in original:
            raise ValueError("Stage91 E404 vendor pidfd ABI missing: " + marker)
    modified = original.replace(ANCHOR, INSERT + ANCHOR, 1)
    if modified.replace(INSERT + ANCHOR, ANCHOR, 1) != original:
        raise ValueError("Stage91 changed E404 PID source beyond atomic header")
    return modified, {
        "stage": STAGE,
        "target": TARGET,
        "dependency": "linux/atomic.h",
        "pinned_reject_sha256": REJECT_SHA,
        "original_source_sha256": sha256(original.encode()),
        "patched_source_sha256": sha256(modified.encode()),
        "rejected_hunks_reviewed": 1,
        "header_dependencies_added": 1,
        "pid_atomic_api_usage_preserved": True,
        "vendor_pidfd_abi_preserved": True,
        "original_reject_retained": True,
        "remaining_rejected_files": 64,
        "source_change_only_include": True,
        "scheduler_runtime_review_complete": False,
        "kernel_built": False,
        "flash_ready": False,
    }


def execute(tree: Path, index: Path, report: Path, mode: str) -> dict:
    if mode not in ("verify", "apply"):
        raise ValueError("Stage91 mode must be verify or apply")
    patched, status = prepare(tree, index)
    if mode == "apply":
        (tree / TARGET).write_text(patched, encoding="utf-8")
        if sha256((tree / TARGET).read_bytes()) != status["patched_source_sha256"]:
            raise ValueError("Stage91 PID header source write mismatch")
    if sha256((tree / REJECT).read_bytes()) != REJECT_SHA:
        raise ValueError("Stage91 original rejected RT hunk changed")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage91 original 64 RT rejects altered")
    status["applied"] = mode == "apply"
    report.mkdir(parents=True, exist_ok=True)
    (report / REPORT).write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8"
    )
    return status


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", required=True, type=Path)
    p.add_argument("--index", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    p.add_argument("--mode", choices=("verify", "apply"), required=True)
    a = p.parse_args()
    print(json.dumps(execute(
        a.tree.resolve(), a.index.resolve(), a.report.resolve(), a.mode
    ), indent=2))


if __name__ == "__main__":
    main()
