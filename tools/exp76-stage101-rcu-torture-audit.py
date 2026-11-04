#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage101 RCU torture legacy flavor rejected-hunk audit / NO FLASH
"""Classify two legacy RT rcutorture.c flavor hunks without applying them.

The original RT patch carries a CONFIG_PREEMPT_RT_FULL guard for RCU-BH
torture operations, while E404 uses unified RCU. Provenance and source
presence do not prove correctness of the runtime torture or grace periods.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

STAGE = "EXP76_STAGE101_RCU_TORTURE_LEGACY_FLAVOR_REJECT_NONFLASH"
STAGE82 = "EXP76_STAGE82_OUTSTANDING_RT_REJECT_HUNK_INVENTORY_NONFLASH"
STAGE93 = "EXP76_STAGE93_UNIFIED_RCU_RT_LINK_AND_API_CONTRACT_NONFLASH"
STAGE95 = "EXP76_STAGE95_RCU_INTERNAL_HEADER_GENERATION_AUDIT_NONFLASH"
STAGE100 = "EXP76_STAGE100_RCU_EXPEDITED_CPU_SELECTION_REJECT_NONFLASH"
SOURCE = "kernel/rcu/rcutorture.c"
REJECT = SOURCE + ".rej"
REJECT_SHA = "67f0c43c90faf4829393035b1ba7abe8d8946e401bf0ff6af9b0cb24715200d8"
EXPECTED_HUNKS = 2
HEADERS = (
    "@@ -434,6 +434,7 @@ static struct rcu_torture_ops rcu_ops = {",
    "@@ -475,6 +476,12 @@ static struct rcu_torture_ops rcu_bh_ops = {",
)
REJECT_MARKERS = (
    "+#ifndef CONFIG_PREEMPT_RT_FULL",
    "+#else",
    "+static struct rcu_torture_ops rcu_bh_ops = {",
    "+\t.ttype\t\t= INVALID_RCU_FLAVOR,",
)
SOURCE_MARKERS = ("struct rcu_torture_ops", "rcu_ops")
HEADER_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")
REPORT = "stage101-status.json"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def prior(path: Path, expected_stage: str) -> dict:
    if not path.is_file():
        raise ValueError("Stage101 prerequisite report missing: " + str(path))
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("stage") != expected_stage:
        raise ValueError("Stage101 prerequisite identity mismatch: " + expected_stage)
    return obj

def execute(tree: Path, inventory: Path, stage93_path: Path,
            stage95_path: Path, stage100_path: Path, report: Path) -> dict:
    if not (tree / ".git").is_dir():
        raise ValueError("Stage101 isolated E404 checkout required")
    if (len(list(tree.rglob("*.rej"))) != 64
            or not (tree / "kernel/sched/cpupri.c.rej").is_file()):
        raise ValueError("Stage101 original 64 RT rejects must remain")
    target, rej = tree / SOURCE, tree / REJECT
    if not target.is_file() or not rej.is_file():
        raise ValueError("Stage101 RCU torture source/rejection absent")
    original_sha = sha(rej)
    if original_sha != REJECT_SHA:
        raise ValueError("Stage101 pinned RCU torture reject SHA256 drift")
    index = prior(inventory, STAGE82)
    entries = [e for e in index.get("entries", []) if e.get("source") == SOURCE]
    if not (
        index.get("remaining_rejected_files") == 64
        and index.get("source_modified") is False
        and index.get("rejects_deleted") is False
        and len(entries) == 1
        and entries[0].get("source_exists") is True
        and entries[0].get("review_category") == "rcu"
        and entries[0].get("reject_sha256") == REJECT_SHA
        and entries[0].get("hunk_count") == EXPECTED_HUNKS
        and entries[0].get("parse_issues") == []
    ):
        raise ValueError("Stage101 Stage82 RCU torture reject provenance invalid")
    lines = rej.read_text(encoding="utf-8").splitlines()
    headers = [line for line in lines if line.startswith("@@ ")]
    index_hunks = entries[0].get("hunks")
    if not (
        len(headers) == EXPECTED_HUNKS
        and isinstance(index_hunks, list)
        and len(index_hunks) == EXPECTED_HUNKS
        and all(HEADER_RE.match(header) and header == item.get("header")
                for header, item in zip(headers, index_hunks))
        and all(header.startswith(prefix)
                for header, prefix in zip(headers, HEADERS))
    ):
        raise ValueError("Stage101 original RCU torture hunk headers drift")
    for marker in REJECT_MARKERS:
        if lines.count(marker) != 1:
            raise ValueError("Stage101 old RT RCU-BH torture marker drift: " + marker)
    stage93 = prior(stage93_path, STAGE93)
    if not (
        stage93.get("rt_config_verified") is True
        and stage93.get("linked_rcu_exports_present") == [
            "synchronize_rcu", "rcu_barrier",
            "__rcu_read_lock", "__rcu_read_unlock",
        ]
        and stage93.get("linked_rcu_exports_missing") == []
        and stage93.get("verification_scope") == "SOURCE_AND_LINK_ONLY"
        and stage93.get("original_rejected_files_remaining") == 64
        and stage93.get("rt_rcu_runtime_semantics_verified") is False
    ):
        raise ValueError("Stage101 Stage93 linked unified RCU baseline invalid")
    stage95 = prior(stage95_path, STAGE95)
    if not (
        stage95.get("obsolete_legacy_rcu_flavor_api_absent") is True
        and stage95.get("vendor_unified_gp_api_declared") is True
        and stage95.get("original_rejected_files_remaining") == 64
        and stage95.get("source_modified") is False
        and stage95.get("rt_rcu_runtime_semantics_verified") is False
    ):
        raise ValueError("Stage101 Stage95 unified RCU header ABI invalid")
    stage100 = prior(stage100_path, STAGE100)
    if not (
        stage100.get("stage82_reject_inventory_verified") is True
        and stage100.get("stage93_linked_rcu_tree_verified") is True
        and stage100.get("original_exp_rcu_rejected_hunks_pending") == 2
        and stage100.get("original_rejected_files_remaining") == 64
        and stage100.get("source_modified") is False
        and stage100.get("rt_rcu_runtime_semantics_verified") is False
        and stage100.get("flash_ready") is False
    ):
        raise ValueError("Stage101 Stage100 expedited RCU provenance invalid")
    text = target.read_text(encoding="utf-8")
    for marker in SOURCE_MARKERS:
        if marker not in text:
            raise ValueError("Stage101 current RCU torture source marker missing: " + marker)
    result = {
        "stage": STAGE,
        "verification_scope": "SOURCE_AND_REJECT_PROVENANCE_ONLY",
        "original_rcutorture_reject_sha256": original_sha,
        "original_rcutorture_rejected_hunks_pending": EXPECTED_HUNKS,
        "original_rcutorture_hunk_headers": headers,
        "original_rt_bh_torture_markers": list(REJECT_MARKERS),
        "e404_rcutorture_source_sha256": sha(target),
        "e404_rcu_bh_torture_ops_present":
            bool(re.search(r"\bstruct\s+rcu_torture_ops\s+rcu_bh_ops\b", text)),
        "stage82_reject_inventory_verified": True,
        "stage93_unified_rcu_link_verified": True,
        "stage95_unified_rcu_headers_verified": True,
        "stage100_rcu_exp_provenance_verified": True,
        "classification": "LEGACY_RCU_BH_TORTURE_FLAVOR_REQUIRES_E404_SEMANTIC_REVIEW",
        "original_rejected_files_remaining": 64,
        "source_modified": False,
        "original_rejects_deleted": False,
        "rejected_hunks_semantically_resolved": 0,
        "rcu_torture_runtime_verified": False,
        "rt_rcu_runtime_semantics_verified": False,
        "rcu_grace_period_runtime_verified": False,
        "device_boot_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    if len(list(tree.rglob("*.rej"))) != 64 or sha(rej) != original_sha:
        raise ValueError("Stage101 RT reject files changed during audit")
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
    p.add_argument("--stage100-report", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(execute(
        a.tree.resolve(), a.inventory.resolve(), a.stage93_report.resolve(),
        a.stage95_report.resolve(), a.stage100_report.resolve(),
        a.report.resolve()), indent=2))

if __name__ == "__main__":
    main()
