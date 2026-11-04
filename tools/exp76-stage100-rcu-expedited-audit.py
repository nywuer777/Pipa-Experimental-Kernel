#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage100 RCU expedited CPU-selection reject audit / NO FLASH
"""Audit two old RT expedited-RCU CPU selection rejects against E404 evidence.

This audit validates provenance and the current tree source, not runtime behavior
or semantic equivalence of the old RT CPU-selection implementation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

STAGE = "EXP76_STAGE100_RCU_EXPEDITED_CPU_SELECTION_REJECT_NONFLASH"
STAGE82 = "EXP76_STAGE82_OUTSTANDING_RT_REJECT_HUNK_INVENTORY_NONFLASH"
STAGE93 = "EXP76_STAGE93_UNIFIED_RCU_RT_LINK_AND_API_CONTRACT_NONFLASH"
STAGE99 = "EXP76_STAGE99_SRCU_HOTPLUG_REJECT_PROVENANCE_NONFLASH"
SOURCE = "kernel/rcu/tree_exp.h"
REJECT = SOURCE + ".rej"
TREE = "kernel/rcu/tree.c"
REJECT_SHA = "0171ff323693a194700c0dbb04ab8694870ea0bc78c2a06706755060e6b70f80"
EXPECTED_HUNKS = 2
HUNK_PREFIXES = (
    "@@ -472,7 +472,6 @@ static void sync_rcu_exp_select_node_cpus(struct work_struct *wp)",
    "@@ -494,13 +493,7 @@ static void sync_rcu_exp_select_cpus(struct rcu_state *rsp,",
)
REJECT_MARKERS = (
    "-\t\tpreempt_disable();",
    "-\t\tcpu = cpumask_next(rnp->grplo - 1, cpu_online_mask);",
    "-\t\t/* If all offline, queue the work on an unbound CPU. */",
)
OLD_SELECTOR_TOKENS = ("sync_rcu_exp_select_node_cpus", "sync_rcu_exp_select_cpus")
HEADER_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")
REPORT = "stage100-status.json"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load(path: Path, stage: str) -> dict:
    if not path.is_file():
        raise ValueError("Stage100 prerequisite missing: " + str(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("stage") != stage:
        raise ValueError("Stage100 prerequisite stage mismatch: " + stage)
    return data

def execute(tree: Path, inventory: Path, stage93_path: Path,
            stage99_path: Path, report: Path) -> dict:
    if not (tree / ".git").is_dir():
        raise ValueError("Stage100 requires isolated pinned E404 checkout")
    if (len(list(tree.rglob("*.rej"))) != 64
            or not (tree / "kernel/sched/cpupri.c.rej").is_file()):
        raise ValueError("Stage100 original 64 RT rejected files not preserved")
    source_path, reject_path = tree / SOURCE, tree / REJECT
    core_path = tree / TREE
    if not source_path.is_file() or not reject_path.is_file() or not core_path.is_file():
        raise ValueError("Stage100 E404 expedited RCU source/reject/core missing")
    if sha(reject_path) != REJECT_SHA:
        raise ValueError("Stage100 original expedited RCU rejection SHA256 drift")
    stage82 = load(inventory, STAGE82)
    entries = [entry for entry in stage82.get("entries", [])
               if entry.get("source") == SOURCE]
    if not (
        stage82.get("remaining_rejected_files") == 64
        and stage82.get("source_modified") is False
        and stage82.get("rejects_deleted") is False
        and len(entries) == 1
        and entries[0].get("reject_sha256") == REJECT_SHA
        and entries[0].get("hunk_count") == EXPECTED_HUNKS
        and entries[0].get("source_exists") is True
        and entries[0].get("review_category") == "rcu"
        and entries[0].get("parse_issues") == []
    ):
        raise ValueError("Stage100 Stage82 expedited RCU reject provenance invalid")
    rejected_lines = reject_path.read_text(encoding="utf-8").splitlines()
    headers = [line for line in rejected_lines if line.startswith("@@ ")]
    inventory_hunks = entries[0].get("hunks")
    if not (
        len(headers) == EXPECTED_HUNKS
        and isinstance(inventory_hunks, list)
        and len(inventory_hunks) == EXPECTED_HUNKS
        and all(HEADER_RE.match(h) and h == entry.get("header")
                for h, entry in zip(headers, inventory_hunks))
        and all(h.startswith(prefix)
                for h, prefix in zip(headers, HUNK_PREFIXES))
    ):
        raise ValueError("Stage100 original expedited RCU hunk headers changed")
    for marker in REJECT_MARKERS:
        if rejected_lines.count(marker) != 1:
            raise ValueError("Stage100 original RT CPU selection diff marker drift: " + marker)
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
        and (stage93.get("source_sha256") or {}).get(TREE) == sha(core_path)
    ):
        raise ValueError("Stage100 Stage93 linked RCU tree baseline invalid")
    stage99 = load(stage99_path, STAGE99)
    if not (
        stage99.get("stage82_reject_inventory_verified") is True
        and stage99.get("stage93_linked_rcu_contract_verified") is True
        and stage99.get("original_srcu_rejected_hunks_pending") == 6
        and stage99.get("verification_scope") == "SOURCE_AND_REJECT_PROVENANCE_ONLY"
        and stage99.get("original_rejected_files_remaining") == 64
        and stage99.get("source_modified") is False
        and stage99.get("rt_srcu_hotplug_runtime_verified") is False
        and stage99.get("flash_ready") is False
    ):
        raise ValueError("Stage100 Stage99 SRCU source provenance invalid")
    vendor_source = source_path.read_text(encoding="utf-8")
    if not vendor_source.strip():
        raise ValueError("Stage100 E404 expedited RCU source empty")
    source_sha = sha(source_path)
    result = {
        "stage": STAGE,
        "verification_scope": "SOURCE_AND_REJECT_PROVENANCE_ONLY",
        "original_exp_rcu_reject_sha256": REJECT_SHA,
        "original_exp_rcu_rejected_hunks_pending": EXPECTED_HUNKS,
        "original_exp_rcu_rejected_hunk_headers": headers,
        "legacy_rt_cpu_selection_markers": list(REJECT_MARKERS),
        "e404_exp_rcu_source_sha256": source_sha,
        "e404_tree_source_sha256": sha(core_path),
        "e404_old_selector_token_presence":
            {name: name in vendor_source for name in OLD_SELECTOR_TOKENS},
        "stage82_reject_inventory_verified": True,
        "stage93_linked_rcu_tree_verified": True,
        "stage99_srcu_provenance_verified": True,
        "classification": "OLD_RT_EXPEDITED_CPU_SELECTION_DIFF_REQUIRES_E404_SEMANTIC_REVIEW",
        "original_rejected_files_remaining": 64,
        "source_modified": False,
        "original_rejects_deleted": False,
        "rejected_hunks_semantically_resolved": 0,
        "rt_exp_rcu_cpu_selection_runtime_verified": False,
        "rcu_grace_period_runtime_verified": False,
        "rt_rcu_runtime_semantics_verified": False,
        "device_boot_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    if len(list(tree.rglob("*.rej"))) != 64 or sha(reject_path) != REJECT_SHA:
        raise ValueError("Stage100 original RT rejects modified during audit")
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
    p.add_argument("--stage99-report", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(execute(
        a.tree.resolve(), a.inventory.resolve(), a.stage93_report.resolve(),
        a.stage99_report.resolve(), a.report.resolve()), indent=2))

if __name__ == "__main__":
    main()
