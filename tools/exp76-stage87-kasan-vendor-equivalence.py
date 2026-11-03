#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage87 KASAN RT equivalence / NO FLASH
"""Verify that six rejected KASAN quarantine raw-spinlock hunks are vendor-equivalent.

The E404 vendor quarantine.c already uses raw_spinlock for this subsystem.
Check the exact SHA-pinned 4.19.325-rt140 rejected file and every +/- line
against the E404 source. This is *not* a generic RT equivalence heuristic.
Retain the original .rej file and all 64 rejects for audit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

STAGE = "EXP76_STAGE87_KASAN_RAW_SPINLOCK_VENDOR_EQUIVALENCE_NONFLASH"
SOURCE = "mm/kasan/quarantine.c"
REJECT = SOURCE + ".rej"
REJECT_SHA = "0fdc912c253d78ffb8b032276f07721fc81d71854a8c60bb82375c74adec506e"
STAGE82 = "EXP76_STAGE82_OUTSTANDING_RT_REJECT_HUNK_INVENTORY_NONFLASH"
REPORT = "stage87-status.json"
HEADERS = (
    "@@ -103,7 +103,7 @@",
    "@@ -190,7 +190,7 @@",
    "@@ -203,7 +203,7 @@",
    "@@ -230,7 +230,7 @@",
    "@@ -254,7 +254,7 @@",
    "@@ -310,17 +310,17 @@",
)


def parse_changes(contents: str) -> tuple[list[str], list[str], list[str]]:
    headings: list[str] = []
    removed: list[str] = []
    added: list[str] = []
    in_hunk = False
    for line in contents.splitlines():
        if line.startswith("@@ "):
            if not re.match(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@", line):
                raise ValueError("Stage87 unparseable rejected hunk header")
            headings.append(line)
            in_hunk = True
        elif line.startswith("diff --git "):
            in_hunk = False
        elif in_hunk:
            if line.startswith("-") and not line.startswith("---"):
                removed.append(line[1:])
            elif line.startswith("+") and not line.startswith("+++"):
                added.append(line[1:])
    return headings, removed, added


def to_raw_spinlock(line: str) -> str:
    if "DEFINE_SPINLOCK(quarantine_lock)" in line:
        return line.replace(
            "DEFINE_SPINLOCK(quarantine_lock)",
            "DEFINE_RAW_SPINLOCK(quarantine_lock)",
            1,
        )
    pattern = r"(?<!raw_)spin_(lock(?:_irqsave)?|unlock(?:_irqrestore)?)\("
    matches = list(re.finditer(pattern, line))
    if len(matches) != 1:
        raise ValueError("Stage87 non-spinlock KASAN RT change found: " + line[:120])
    match = matches[0]
    return line[:match.start()] + "raw_" + line[match.start():]


def execute(tree: Path, inventory: Path, report: Path) -> dict:
    if not (tree / ".git").is_dir():
        raise ValueError("Stage87 requires isolated pinned E404 trial Git tree")
    source = tree / SOURCE
    reject = tree / REJECT
    if not source.is_file() or not reject.is_file():
        raise ValueError("Stage87 requires KASAN quarantine source and RT reject")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage87 requires exactly 64 retained PREEMPT_RT rejects")
    if hashlib.sha256(reject.read_bytes()).hexdigest() != REJECT_SHA:
        raise ValueError("Stage87 KASAN rejected-hunk SHA256 mismatch")
    if not inventory.is_file():
        raise ValueError("Stage87 requires Stage82 immutable source inventory")
    index = json.loads(inventory.read_text(encoding="utf-8"))
    entries = [e for e in (index.get("entries") or []) if e.get("source") == SOURCE]
    if (index.get("stage") != STAGE82
            or index.get("remaining_rejected_files") != 64
            or index.get("source_modified") is not False
            or index.get("rejects_deleted") is not False
            or len(entries) != 1
            or entries[0].get("reject_sha256") != REJECT_SHA
            or entries[0].get("hunk_count") != 6):
        raise ValueError("Stage87 Stage82 KASAN inventory provenance drift")
    headings, removed, added = parse_changes(reject.read_text(encoding="utf-8"))
    if len(headings) != 6 or not all(
        heading.startswith(expected)
        for heading, expected in zip(headings, HEADERS)
    ):
        raise ValueError("Stage87 rejected KASAN six-hunk structure drift")
    if len(removed) != 9 or len(added) != 9:
        raise ValueError("Stage87 rejected KASAN +/- line counts drift")
    expected_added = [to_raw_spinlock(line) for line in removed]
    if Counter(expected_added) != Counter(added):
        raise ValueError("Stage87 KASAN rejected hunks contain non-raw-spinlock edits")
    vendor = source.read_text(encoding="utf-8")
    vendor_lines = Counter(vendor.splitlines())
    missing_new = {
        line: amount - vendor_lines[line]
        for line, amount in Counter(added).items()
        if vendor_lines[line] < amount
    }
    old_still_present = {
        line: vendor_lines[line]
        for line in set(removed)
        if vendor_lines[line] > 0
    }
    if missing_new or old_still_present:
        raise ValueError(
            "Stage87 vendor KASAN not equivalent: " +
            json.dumps({
                "missing_raw_lines": missing_new,
                "remaining_nonraw_lines": old_still_present,
            }, sort_keys=True)[:1000]
        )
    result = {
        "stage": STAGE,
        "target": SOURCE,
        "original_reject_sha256": REJECT_SHA,
        "vendor_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "reviewed_rejected_hunks": 6,
        "reviewed_added_lines": len(added),
        "reviewed_removed_lines": len(removed),
        "all_added_raw_spinlock_lines_present": True,
        "all_obsolete_spinlock_lines_absent": True,
        "vendor_equivalent_hunks": 6,
        "vendor_equivalent_files": 1,
        "source_changed": False,
        "rejects_deleted": False,
        "rejected_files_remaining": 64,
        "semantic_scope": "KASAN quarantine raw-spinlock substitutions only",
        "all_rt_semantics_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    report.mkdir(parents=True, exist_ok=True)
    (report / REPORT).write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage87 modified original RT rejection evidence")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    a = parser.parse_args()
    result = execute(a.tree.resolve(), a.inventory.resolve(), a.report.resolve())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
