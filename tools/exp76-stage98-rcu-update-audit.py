#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage98 E404 RT RCU update.c provenance / NO FLASH
"""Classify pinned legacy RT update.c reject hunks versus linked unified E404 RCU.

READONLY: preserve all 64 original RT rejects, compare Stage82/93/97 evidence,
and do not infer grace-period or device runtime correctness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

STAGE = "EXP76_STAGE98_RCU_UPDATE_REJECT_PROVENANCE_NONFLASH"
STAGE82 = "EXP76_STAGE82_OUTSTANDING_RT_REJECT_HUNK_INVENTORY_NONFLASH"
STAGE93 = "EXP76_STAGE93_UNIFIED_RCU_RT_LINK_AND_API_CONTRACT_NONFLASH"
STAGE97 = "EXP76_STAGE97_RCU_TREE_PLUGIN_REJECT_PROVENANCE_NONFLASH"
SOURCE = "kernel/rcu/update.c"
REJECT = SOURCE + ".rej"
REJECT_SHA = "98cce60a248d9540dfdccb316138f6f58154618c36ef20dbfb3a77c03d836ae7"
EXPECTED_HUNKS = 3
REPORT = "stage98-status.json"
HUNK_PREFIXES = (
    "@@ -53,6 +53,7 @@",
    "@@ -68,8 +69,10 @@",
    "@@ -314,6 +318,7 @@",
)
LEGACY_HUNK_MARKERS = (
    "+#include <linux/rcuwait.h>",
    "-static int rcu_normal_after_boot;",
    "+static int rcu_normal_after_boot = IS_ENABLED(CONFIG_PREEMPT_RT_FULL);",
    "+#ifndef CONFIG_PREEMPT_RT_FULL",
)
UNIFIED_SOURCE_MARKERS = (
    "int rcu_read_lock_bh_held(void)",
    "EXPORT_SYMBOL_GPL(rcu_read_lock_bh_held);",
    "#ifndef CONFIG_PREEMPT_RT_FULL",
)
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load(path: Path, expected: str) -> dict:
    if not path.is_file():
        raise ValueError("Stage98 required evidence missing: " + str(path))
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("stage") != expected:
        raise ValueError("Stage98 evidence stage mismatch: " + expected)
    return obj

def execute(tree: Path, inventory: Path, stage93_path: Path,
            stage97_path: Path, report: Path) -> dict:
    if not (tree / ".git").is_dir():
        raise ValueError("Stage98 requires isolated pinned E404 kernel checkout")
    if (len(list(tree.rglob("*.rej"))) != 64
            or not (tree / "kernel/sched/cpupri.c.rej").is_file()):
        raise ValueError("Stage98 original 64 RT reject files not preserved")
    target, rejected = tree / SOURCE, tree / REJECT
    if not target.is_file() or not rejected.is_file():
        raise ValueError("Stage98 RCU update source or reject missing")
    if sha(rejected) != REJECT_SHA:
        raise ValueError("Stage98 original RCU update reject SHA256 drift")
    index = load(inventory, STAGE82)
    entries = [
        item for item in index.get("entries", [])
        if item.get("source") == SOURCE
    ]
    if not (
        index.get("remaining_rejected_files") == 64
        and index.get("source_modified") is False
        and index.get("rejects_deleted") is False
        and len(entries) == 1
        and entries[0].get("hunk_count") == EXPECTED_HUNKS
        and entries[0].get("reject_sha256") == REJECT_SHA
        and entries[0].get("parse_issues") == []
    ):
        raise ValueError("Stage98 Stage82 RT update hunk provenance mismatch")
    rejected_lines = rejected.read_text(encoding="utf-8").splitlines()
    headers = [row for row in rejected_lines if row.startswith("@@ ")]
    if len(headers) != EXPECTED_HUNKS or any(
        not HUNK.match(header) or not header.startswith(prefix)
        for header, prefix in zip(headers, HUNK_PREFIXES)
    ):
        raise ValueError("Stage98 original RCU update three-hunk headers changed")
    for marker in LEGACY_HUNK_MARKERS:
        if rejected_lines.count(marker) != 1:
            raise ValueError("Stage98 pinned legacy RT update reject marker drift: " + marker)
    stage93 = load(stage93_path, STAGE93)
    if not (
        stage93.get("rt_config_verified") is True
        and stage93.get("linked_rcu_exports_missing") == []
        and stage93.get("linked_rcu_exports_present") == [
            "synchronize_rcu", "rcu_barrier",
            "__rcu_read_lock", "__rcu_read_unlock",
        ]
        and stage93.get("verification_scope") == "SOURCE_AND_LINK_ONLY"
        and stage93.get("original_rejected_files_remaining") == 64
        and stage93.get("rt_rcu_runtime_semantics_verified") is False
        and stage93.get("rcu_grace_period_runtime_verified") is False
    ):
        raise ValueError("Stage98 Stage93 linked RCU source baseline invalid")
    stage97 = load(stage97_path, STAGE97)
    if not (
        stage97.get("stage82_inventory_proven") is True
        and stage97.get("stage93_linked_exports_proven") is True
        and stage97.get("original_rcu_plugin_rejected_hunks_pending") == 11
        and stage97.get("original_rejected_files_remaining") == 64
        and stage97.get("rcu_plugin_source_matches_stage93") is True
        and stage97.get("source_modified") is False
        and stage97.get("rt_rcu_runtime_semantics_verified") is False
        and stage97.get("verification_scope") == "SOURCE_PROVENANCE_ONLY"
    ):
        raise ValueError("Stage98 Stage97 RCU plugin provenance invalid")
    source_digest = sha(target)
    if (stage93.get("source_sha256") or {}).get(SOURCE) != source_digest:
        raise ValueError("Stage98 update.c source SHA256 drift versus Stage93")
    source_text = target.read_text(encoding="utf-8")
    for marker in UNIFIED_SOURCE_MARKERS:
        if marker not in source_text:
            raise ValueError("Stage98 E404 unified source marker missing: " + marker)
    if source_text.index("#ifndef CONFIG_PREEMPT_RT_FULL") > source_text.index(
        "int rcu_read_lock_bh_held(void)"
    ):
        raise ValueError("Stage98 E404 RT lockdep conditional location drift")
    result = {
        "stage": STAGE,
        "verification_scope": "SOURCE_PROVENANCE_ONLY",
        "original_rcu_update_reject_sha256": REJECT_SHA,
        "original_rcu_update_rejected_hunks_pending": EXPECTED_HUNKS,
        "original_rcu_update_hunk_headers": headers,
        "original_rcu_update_hunk_markers": list(LEGACY_HUNK_MARKERS),
        "rcu_update_source_sha256": source_digest,
        "unified_source_markers_checked": list(UNIFIED_SOURCE_MARKERS),
        "stage82_inventory_proven": True,
        "stage93_linked_exports_proven": True,
        "stage97_rcu_plugin_proven": True,
        "rcu_update_source_matches_stage93": True,
        "classification": "LEGACY_RT_RCU_UPDATE_HUNKS_REQUIRE_E404_SEMANTIC_REVIEW",
        "original_rejected_files_remaining": 64,
        "source_modified": False,
        "original_rejects_deleted": False,
        "rejected_hunks_semantically_resolved": 0,
        "rt_rcu_runtime_semantics_verified": False,
        "rcu_grace_period_runtime_verified": False,
        "device_boot_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    if len(list(tree.rglob("*.rej"))) != 64 or sha(rejected) != REJECT_SHA:
        raise ValueError("Stage98 RT rejects changed during audit")
    report.mkdir(parents=True, exist_ok=True)
    (report / REPORT).write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", required=True, type=Path)
    p.add_argument("--inventory", required=True, type=Path)
    p.add_argument("--stage93-report", required=True, type=Path)
    p.add_argument("--stage97-report", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(execute(
        a.tree.resolve(), a.inventory.resolve(), a.stage93_report.resolve(),
        a.stage97_report.resolve(), a.report.resolve()
    ), indent=2))

if __name__ == "__main__":
    main()
