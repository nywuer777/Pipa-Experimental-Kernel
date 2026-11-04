#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage95 pinned RCU headers ABI audit / NO FLASH
"""Classify two RT internal RCU header rejects against E404 unified RCU.

The older RT patch expects per-flavor RCU-bh declarations, callback kthreads
and RCU_BOOST ifdef.  E404 uses a unified rcu_state, rcu_segcblist and
rcu_cpu_kthread_setup().  Verify original reject content and source API
contracts, without applying inappropriate legacy definitions or claiming
runtime RCU grace-period correctness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

STAGE = "EXP76_STAGE95_RCU_INTERNAL_HEADER_GENERATION_AUDIT_NONFLASH"
REPORT = "stage95-status.json"
INVENTORY_STAGE = "EXP76_STAGE82_OUTSTANDING_RT_REJECT_HUNK_INVENTORY_NONFLASH"
STAGE93 = "EXP76_STAGE93_UNIFIED_RCU_RT_LINK_AND_API_CONTRACT_NONFLASH"
HEADERS = {
    "kernel/rcu/rcu.h": {
        "sha": "e6665ce33fc70064e46b04120eecbebae9e64752ad83d06891f871bdd878c210",
        "hunks": 2,
        "add": 9,
        "remove": 2,
        "headers": (
            "@@ -528,7 +528,6 @@",
            "@@ -536,10 +535,18 @@",
        ),
        "old": (
            "-unsigned long rcu_bh_get_gp_seq(void);",
            "-void rcu_bh_force_quiescent_state(void);",
        ),
        "new": (
            "+#define rcu_bh_get_gp_seq\t\trcu_get_gp_seq",
            "+#define rcu_bh_force_quiescent_state\trcu_force_quiescent_state",
        ),
    },
    "kernel/rcu/tree.h": {
        "sha": "ad8e175a495d38fc5704db7e85f758fadaffc23b65591e4f836f5ffe75b80eb2",
        "hunks": 3,
        "add": 3,
        "remove": 3,
        "headers": (
            "@@ -413,7 +413,9 @@",
            "@@ -421,12 +423,10 @@",
            "@@ -449,8 +449,8 @@",
        ),
        "old": (
            "-#ifdef CONFIG_RCU_BOOST",
            "-#endif /* #ifdef CONFIG_RCU_BOOST */",
            "-static void invoke_rcu_callbacks_kthread(void);",
        ),
        "new": (
            "+#ifndef CONFIG_PREEMPT_RT_FULL",
            "+static void rcu_cpu_kthread_setup(unsigned int cpu);",
        ),
    },
}
TREE = "kernel/rcu/tree.c"
REQUIRED = {
    "rcu.h": (
        "static inline unsigned long rcu_get_gp_seq(void) { return 0; }",
        "static inline void rcu_force_quiescent_state(void) { }",
        "unsigned long rcu_get_gp_seq(void);",
        "void rcu_force_quiescent_state(void);",
    ),
    "tree.h": (
        "static void rcu_cpu_kthread_setup(unsigned int cpu);",
        "static void rcu_prepare_kthreads(int cpu);",
        "static bool rcu_is_callbacks_kthread(void);",
        "static void rcu_preempt_boost_start_gp(struct rcu_node *rnp);",
    ),
    "tree.c": (
        "rcu_segcblist",
        "void rcu_barrier(void)",
        "void synchronize_rcu(void)",
    ),
}
LEGACY = (
    "rcu_bh_get_gp_seq",
    "rcu_bh_force_quiescent_state",
    "invoke_rcu_callbacks_kthread",
    "rcu_bh_state",
    "rcu_sched_state",
    "rcu_struct_flavors",
)


def sha(file: Path) -> str:
    return hashlib.sha256(file.read_bytes()).hexdigest()


def summary(reject: str) -> tuple[int, int, int, list[str]]:
    hunks = [x for x in reject.splitlines() if x.startswith("@@ ")]
    for h in hunks:
        if not re.match(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@", h):
            raise ValueError("Stage95 unparseable original RCU reject hunk")
    adds = sum(x.startswith("+") and not x.startswith("+++") for x in reject.splitlines())
    removes = sum(x.startswith("-") and not x.startswith("---") for x in reject.splitlines())
    return len(hunks), adds, removes, hunks


def execute(tree: Path, inventory: Path, stage93_path: Path, report: Path) -> dict:
    if not (tree / ".git").is_dir():
        raise ValueError("Stage95 requires pinned isolated E404 checkout")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage95 original 64 RT rejects must be preserved")
    if not (tree / "kernel/sched/cpupri.c.rej").is_file():
        raise ValueError("Stage95 scheduler reject provenance missing")
    if not inventory.is_file():
        raise ValueError("Stage95 immutable Stage82 reject inventory required")
    manifest = json.loads(inventory.read_text(encoding="utf-8"))
    if not (
        manifest.get("stage") == INVENTORY_STAGE
        and manifest.get("remaining_rejected_files") == 64
        and manifest.get("source_modified") is False
        and manifest.get("rejects_deleted") is False
    ):
        raise ValueError("Stage95 Stage82 reject manifest drift")
    if not stage93_path.is_file():
        raise ValueError("Stage95 prior Stage93 linked RCU evidence missing")
    stage93 = json.loads(stage93_path.read_text(encoding="utf-8"))
    if not (
        stage93.get("stage") == STAGE93
        and stage93.get("rt_config_verified") is True
        and stage93.get("linked_rcu_exports_missing") == []
        and stage93.get("linked_rcu_exports_present") == [
            "synchronize_rcu", "rcu_barrier",
            "__rcu_read_lock", "__rcu_read_unlock",
        ]
        and stage93.get("original_rcu_tree_rejected_hunks_pending") == 18
        and stage93.get("original_rejected_files_remaining") == 64
        and stage93.get("verification_scope") == "SOURCE_AND_LINK_ONLY"
        and stage93.get("rt_rcu_runtime_semantics_verified") is False
    ):
        raise ValueError("Stage95 Stage93 unified RCU link contract not established")
    source_sha = {}
    reject_sha = {}
    source: dict[str, str] = {}
    reviewed_hunks = 0
    for relative, spec in HEADERS.items():
        target = tree / relative
        rejected = tree / (relative + ".rej")
        if not target.is_file() or not rejected.is_file():
            raise ValueError("Stage95 pinned RCU source or rejected hunk absent: " + relative)
        if sha(rejected) != spec["sha"]:
            raise ValueError("Stage95 original RCU reject SHA256 mismatch: " + relative)
        entries = [
            x for x in manifest.get("entries", []) if x.get("source") == relative
        ]
        if not (
            len(entries) == 1
            and entries[0].get("reject_sha256") == spec["sha"]
            and entries[0].get("hunk_count") == spec["hunks"]
            and entries[0].get("added_lines") == spec["add"]
            and entries[0].get("removed_lines") == spec["remove"]
        ):
            raise ValueError("Stage95 Stage82 RCU header hunk provenance mismatch: " + relative)
        diff = rejected.read_text(encoding="utf-8")
        hunks, added, removed, headers = summary(diff)
        if (hunks, added, removed) != (
            spec["hunks"], spec["add"], spec["remove"]
        ):
            raise ValueError("Stage95 original RCU header reject hunk totals changed")
        for h, prefix in zip(headers, spec["headers"]):
            if not h.startswith(prefix):
                raise ValueError("Stage95 pinned RCU header reject location changed")
        for line in spec["old"] + spec["new"]:
            if diff.splitlines().count(line) != 1:
                raise ValueError("Stage95 pinned legacy RCU reject line changed: " + line)
        source[relative] = target.read_text(encoding="utf-8")
        source_sha[relative] = sha(target)
        reject_sha[relative] = sha(rejected)
        reviewed_hunks += hunks
    core = tree / TREE
    if not core.is_file():
        raise ValueError("Stage95 unified RCU implementation source missing")
    source[TREE] = core.read_text(encoding="utf-8")
    source_sha[TREE] = sha(core)
    for path, markers in (
        ("kernel/rcu/rcu.h", REQUIRED["rcu.h"]),
        ("kernel/rcu/tree.h", REQUIRED["tree.h"]),
        (TREE, REQUIRED["tree.c"]),
    ):
        for marker in markers:
            appearances = source[path].count(marker)
            correct = appearances >= 1 if marker == "rcu_segcblist" else appearances == 1
            if not correct:
                raise ValueError("Stage95 unified E404 RCU source contract drift: " + marker)
    combined = "\n".join(source.values())
    for symbol in LEGACY:
        if re.search(r"\b" + symbol + r"\b", combined):
            raise ValueError("Stage95 old-flavor RCU ABI reintroduced: " + symbol)
    if "#ifdef CONFIG_RCU_BOOST" in source["kernel/rcu/tree.h"]:
        raise ValueError("Stage95 obsolete RCU_BOOST guard unexpectedly reintroduced")
    # E404 has two real CONFIG_TINY_RCU sections: SRCU internals and
    # unified GP/force-QS stubs.  Comments on #else/#endif mention the
    # same token and must never count as opening directives.
    tiny_directives = re.findall(
        r"(?m)^\s*#\s*ifdef\s+CONFIG_TINY_RCU\s*$",
        source["kernel/rcu/rcu.h"],
    )
    if (len(tiny_directives) != 2
            or source["kernel/rcu/tree.h"].count(
                "static void rcu_cpu_kthread_setup(unsigned int cpu);"
            ) != 1):
        raise ValueError("Stage95 E404 RCU tiny/tree API variant drift")
    data = {
        "stage": STAGE,
        "reviewed_original_rcu_header_rejected_files": len(HEADERS),
        "reviewed_original_rcu_header_rejected_hunks": reviewed_hunks,
        "rcu_headers": sorted(HEADERS),
        "original_reject_sha256": reject_sha,
        "source_sha256": source_sha,
        "vendor_unified_gp_api_declared": True,
        "vendor_rcu_kthread_setup_declared": True,
        "obsolete_legacy_rcu_flavor_api_absent": True,
        "tiny_rcu_stub_path_preserved": True,
        "stage93_linked_rcu_exports_verified": True,
        "classification": "OLD_RCU_FLAVOR_API_DIFFERS_FROM_E404_UNIFIED_RCU",
        "source_modified": False,
        "original_rejects_deleted": False,
        "original_rejected_files_remaining": 64,
        "rcu_header_hunks_runtime_semantics_resolved": 0,
        "rt_rcu_runtime_semantics_verified": False,
        "device_boot_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage95 original RT rejected hunks were modified")
    report.mkdir(parents=True, exist_ok=True)
    (report / REPORT).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--stage93-report", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    a = parser.parse_args()
    print(json.dumps(
        execute(
            a.tree.resolve(), a.inventory.resolve(),
            a.stage93_report.resolve(), a.report.resolve(),
        ), indent=2,
    ))


if __name__ == "__main__":
    main()
