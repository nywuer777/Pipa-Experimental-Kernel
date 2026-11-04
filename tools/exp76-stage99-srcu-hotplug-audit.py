#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage99 SRCU hotplug rejected-hunk provenance / NO FLASH
"""Read-only audit of six legacy RT srcutree.c rejected hunks on E404.

Pin the original rejected bytes, compare all six hunk headers to Stage82,
and verify the existing SRCU source remains available. No source changes,
runtime claims, patch application, boot packaging, or flashing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

STAGE = "EXP76_STAGE99_SRCU_HOTPLUG_REJECT_PROVENANCE_NONFLASH"
STAGE82 = "EXP76_STAGE82_OUTSTANDING_RT_REJECT_HUNK_INVENTORY_NONFLASH"
STAGE93 = "EXP76_STAGE93_UNIFIED_RCU_RT_LINK_AND_API_CONTRACT_NONFLASH"
STAGE98 = "EXP76_STAGE98_RCU_UPDATE_REJECT_PROVENANCE_NONFLASH"
SOURCE = "kernel/rcu/srcutree.c"
REJECT = SOURCE + ".rej"
REJECT_SHA = "5844d3c558a15107c85741935c58a49133c307f6e08dcb137c6bab162ad29142"
EXPECTED_HUNKS = 6
HUNK_PREFIXES = (
    "@@ -460,21 +462,6 @@ static void srcu_gp_start(struct srcu_struct *sp)",
    "@@ -486,12 +473,12 @@ static bool srcu_queue_delayed_work_on(int cpu, struct workqueue_struct *wq,",
    "@@ -774,6 +761,8 @@ static void srcu_flip(struct srcu_struct *sp)",
)
SOURCE_MARKERS = ("srcu_gp_start(", "srcu_queue_delayed_work_on(", "srcu_flip(")
REJECT_MARKERS = ("-\tpreempt_disable();", "+\tcpus_read_lock();")
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")
REPORT = "stage99-status.json"

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def evidence(path: Path, expected_stage: str) -> dict:
    if not path.is_file():
        raise ValueError("Stage99 prerequisite missing: " + str(path))
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("stage") != expected_stage:
        raise ValueError("Stage99 prerequisite stage mismatch: " + expected_stage)
    return obj

def execute(tree: Path, inventory: Path, stage93_path: Path,
            stage98_path: Path, report: Path) -> dict:
    if not (tree / ".git").is_dir():
        raise ValueError("Stage99 requires isolated pinned E404 checkout")
    if (len(list(tree.rglob("*.rej"))) != 64
            or not (tree / "kernel/sched/cpupri.c.rej").is_file()):
        raise ValueError("Stage99 original 64 RT rejected files not preserved")
    source_path, reject_path = tree / SOURCE, tree / REJECT
    if not source_path.is_file() or not reject_path.is_file():
        raise ValueError("Stage99 SRCU source or reject missing")
    if digest(reject_path) != REJECT_SHA:
        raise ValueError("Stage99 pinned SRCU rejection SHA256 drift")
    stage82 = evidence(inventory, STAGE82)
    entries = [item for item in stage82.get("entries", [])
               if item.get("source") == SOURCE]
    if not (
        stage82.get("remaining_rejected_files") == 64
        and stage82.get("source_modified") is False
        and stage82.get("rejects_deleted") is False
        and len(entries) == 1
        and entries[0].get("source_exists") is True
        and entries[0].get("review_category") == "rcu"
        and entries[0].get("reject_sha256") == REJECT_SHA
        and entries[0].get("hunk_count") == EXPECTED_HUNKS
        and entries[0].get("parse_issues") == []
    ):
        raise ValueError("Stage99 Stage82 SRCU reject provenance mismatch")
    lines = reject_path.read_text(encoding="utf-8").splitlines()
    headers = [line for line in lines if line.startswith("@@ ")]
    indexed_hunks = entries[0].get("hunks")
    if not (
        len(headers) == EXPECTED_HUNKS
        and isinstance(indexed_hunks, list)
        and len(indexed_hunks) == EXPECTED_HUNKS
        and all(HUNK.match(h) and h == index.get("header")
                for h, index in zip(headers, indexed_hunks))
        and all(headers[i].startswith(prefix)
                for i, prefix in enumerate(HUNK_PREFIXES))
    ):
        raise ValueError("Stage99 six SRCU hunk headers changed")
    for marker in REJECT_MARKERS:
        if marker not in lines:
            raise ValueError("Stage99 original SRCU hotplug reject marker missing: " + marker)
    stage93 = evidence(stage93_path, STAGE93)
    if not (
        stage93.get("rt_config_verified") is True
        and stage93.get("linked_rcu_exports_missing") == []
        and stage93.get("verification_scope") == "SOURCE_AND_LINK_ONLY"
        and stage93.get("original_rejected_files_remaining") == 64
        and stage93.get("rt_rcu_runtime_semantics_verified") is False
        and stage93.get("rcu_grace_period_runtime_verified") is False
    ):
        raise ValueError("Stage99 Stage93 linked RCU source contract invalid")
    stage98 = evidence(stage98_path, STAGE98)
    if not (
        stage98.get("stage82_inventory_proven") is True
        and stage98.get("stage93_linked_exports_proven") is True
        and stage98.get("original_rcu_update_rejected_hunks_pending") == 3
        and stage98.get("rcu_update_source_matches_stage93") is True
        and stage98.get("verification_scope") == "SOURCE_PROVENANCE_ONLY"
        and stage98.get("original_rejected_files_remaining") == 64
        and stage98.get("source_modified") is False
        and stage98.get("rt_rcu_runtime_semantics_verified") is False
    ):
        raise ValueError("Stage99 Stage98 RCU update provenance invalid")
    source = source_path.read_text(encoding="utf-8")
    for marker in SOURCE_MARKERS:
        if marker not in source:
            raise ValueError("Stage99 SRCU implementation marker missing: " + marker)
    source_sha = digest(source_path)
    result = {
        "stage": STAGE,
        "verification_scope": "SOURCE_AND_REJECT_PROVENANCE_ONLY",
        "original_srcu_reject_sha256": REJECT_SHA,
        "original_srcu_rejected_hunks_pending": EXPECTED_HUNKS,
        "original_srcu_rejected_hunk_headers": headers,
        "srcu_source_sha256": source_sha,
        "srcu_source_markers_checked": list(SOURCE_MARKERS),
        "original_srcu_hotplug_reject_markers": list(REJECT_MARKERS),
        "stage82_reject_inventory_verified": True,
        "stage93_linked_rcu_contract_verified": True,
        "stage98_rcu_update_provenance_verified": True,
        "classification": "LEGACY_RT_SRCU_HOTPLUG_HUNKS_REQUIRE_E404_SEMANTIC_REVIEW",
        "original_rejected_files_remaining": 64,
        "source_modified": False,
        "original_rejects_deleted": False,
        "rejected_hunks_semantically_resolved": 0,
        "rt_srcu_hotplug_runtime_verified": False,
        "rt_rcu_runtime_semantics_verified": False,
        "rcu_grace_period_runtime_verified": False,
        "device_boot_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    if len(list(tree.rglob("*.rej"))) != 64 or digest(reject_path) != REJECT_SHA:
        raise ValueError("Stage99 SRCU rejection drift during audit")
    report.mkdir(parents=True, exist_ok=True)
    (report / REPORT).write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", type=Path, required=True)
    p.add_argument("--inventory", type=Path, required=True)
    p.add_argument("--stage93-report", type=Path, required=True)
    p.add_argument("--stage98-report", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(execute(
        a.tree.resolve(), a.inventory.resolve(), a.stage93_report.resolve(),
        a.stage98_report.resolve(), a.report.resolve()), indent=2))

if __name__ == "__main__":
    main()
