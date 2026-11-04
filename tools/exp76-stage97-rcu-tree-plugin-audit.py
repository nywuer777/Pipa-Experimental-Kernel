#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage97 E404 RCU tree_plugin rejected-hunk provenance / NO FLASH
"""Audit the pinned 11-hunk RT tree_plugin.h reject without applying it.

The E404 unified RCU implementation differs from the older 4.19.325-rt140
patch. This is source/provenance evidence only, not a runtime RCU proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

STAGE = "EXP76_STAGE97_RCU_TREE_PLUGIN_REJECT_PROVENANCE_NONFLASH"
STAGE82 = "EXP76_STAGE82_OUTSTANDING_RT_REJECT_HUNK_INVENTORY_NONFLASH"
STAGE93 = "EXP76_STAGE93_UNIFIED_RCU_RT_LINK_AND_API_CONTRACT_NONFLASH"
STAGE95 = "EXP76_STAGE95_RCU_INTERNAL_HEADER_GENERATION_AUDIT_NONFLASH"
SOURCE = "kernel/rcu/tree_plugin.h"
REJECT = SOURCE + ".rej"
REJECT_SHA = "3e1d7208144072ff906f7986d946147d77e7594be21c816eabfc084af032b236"
REJECT_HUNKS = 11
REPORT = "stage97-status.json"
SOURCE_MARKERS = (
    "void __rcu_read_lock(void)",
    "void __rcu_read_unlock(void)",
    "rcu_preempt_deferred_qs(",
    "rcu_read_unlock_special(",
)
HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_json(path: Path, expected_stage: str) -> dict:
    if not path.is_file():
        raise ValueError("Stage97 required prior evidence missing: " + str(path))
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("stage") != expected_stage:
        raise ValueError("Stage97 prior stage identity mismatch: " + expected_stage)
    return value

def execute(tree: Path, inventory: Path, stage93_path: Path,
            stage95_path: Path, report: Path) -> dict:
    if not (tree / ".git").is_dir():
        raise ValueError("Stage97 requires isolated pinned E404 checkout")
    if (len(list(tree.rglob("*.rej"))) != 64
            or not (tree / "kernel/sched/cpupri.c.rej").is_file()):
        raise ValueError("Stage97 original 64 RT reject files not preserved")
    source_path, reject_path = tree / SOURCE, tree / REJECT
    if not source_path.is_file() or not reject_path.is_file():
        raise ValueError("Stage97 RCU plugin source/reject missing")
    if sha(reject_path) != REJECT_SHA:
        raise ValueError("Stage97 original RCU plugin rejection SHA256 drift")
    index = read_json(inventory, STAGE82)
    entries = [
        item for item in index.get("entries", [])
        if item.get("source") == SOURCE
    ]
    if not (
        index.get("remaining_rejected_files") == 64
        and index.get("source_modified") is False
        and index.get("rejects_deleted") is False
        and len(entries) == 1
        and entries[0].get("reject_sha256") == REJECT_SHA
        and entries[0].get("hunk_count") == REJECT_HUNKS
    ):
        raise ValueError("Stage97 Stage82 plugin hunk provenance mismatch")
    reject_text = reject_path.read_text(encoding="utf-8")
    headers = [line for line in reject_text.splitlines() if line.startswith("@@ ")]
    if len(headers) != REJECT_HUNKS or any(
        HUNK_HEADER.match(line) is None for line in headers
    ):
        raise ValueError("Stage97 original RCU plugin 11-hunk structure drift")
    stage93 = read_json(stage93_path, STAGE93)
    if not (
        stage93.get("rt_config_verified") is True
        and stage93.get("linked_rcu_exports_missing") == []
        and stage93.get("linked_rcu_exports_present") == [
            "synchronize_rcu", "rcu_barrier",
            "__rcu_read_lock", "__rcu_read_unlock",
        ]
        and stage93.get("original_rejected_files_remaining") == 64
        and stage93.get("verification_scope") == "SOURCE_AND_LINK_ONLY"
        and stage93.get("rt_rcu_runtime_semantics_verified") is False
    ):
        raise ValueError("Stage97 Stage93 linked RCU baseline invalid")
    stage95 = read_json(stage95_path, STAGE95)
    if not (
        stage95.get("stage93_linked_rcu_exports_verified") is True
        and stage95.get("reviewed_original_rcu_header_rejected_hunks") == 5
        and stage95.get("source_modified") is False
        and stage95.get("rt_rcu_runtime_semantics_verified") is False
        and stage95.get("original_rejected_files_remaining") == 64
    ):
        raise ValueError("Stage97 Stage95 RCU header baseline invalid")
    source_digest = sha(source_path)
    if (stage93.get("source_sha256") or {}).get(SOURCE) != source_digest:
        raise ValueError("Stage97 RCU plugin source SHA256 drift from Stage93")
    source_text = source_path.read_text(encoding="utf-8")
    for marker in SOURCE_MARKERS:
        if marker not in source_text:
            raise ValueError("Stage97 unified RCU plugin source marker missing: " + marker)
    if re.search(r"\bstruct\s+rcu_state\s+(?:rcu_bh_state|rcu_sched_state)\b",
                 source_text):
        raise ValueError("Stage97 legacy RCU flavor state reintroduced")
    result = {
        "stage": STAGE,
        "verification_scope": "SOURCE_PROVENANCE_ONLY",
        "original_rcu_plugin_reject_sha256": REJECT_SHA,
        "original_rcu_plugin_rejected_hunks_pending": REJECT_HUNKS,
        "original_rcu_plugin_hunk_headers": headers,
        "rcu_plugin_source_sha256": source_digest,
        "stage82_inventory_proven": True,
        "stage93_linked_exports_proven": True,
        "stage95_unified_headers_proven": True,
        "rcu_plugin_source_matches_stage93": True,
        "unified_rcu_plugin_source_markers": list(SOURCE_MARKERS),
        "unified_rcu_plugin_source_marker_count": len(SOURCE_MARKERS),
        "classification": "LEGACY_RT_RCU_TREE_PLUGIN_REJECT_REQUIRES_SEMANTIC_REVIEW",
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
    if len(list(tree.rglob("*.rej"))) != 64 or sha(reject_path) != REJECT_SHA:
        raise ValueError("Stage97 original RT rejection files changed during audit")
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
    p.add_argument("--stage95-report", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(execute(a.tree.resolve(), a.inventory.resolve(),
                             a.stage93_report.resolve(), a.stage95_report.resolve(),
                             a.report.resolve()), indent=2))

if __name__ == "__main__":
    main()
