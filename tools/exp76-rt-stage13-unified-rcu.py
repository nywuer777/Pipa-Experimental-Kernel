#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage13 consolidated RCU API equivalence / NO FLASH
"""Verify E404 unified RCU wrappers already satisfy two old-flavor RT hunks.

E404's rcutree.h does not declare legacy bh symbols; rcupdate.h provides
inline RCU-bh forwarding for both RT and non-RT builds. No kernel source
is modified. The original .rej is archived in the audit artifact.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

TREE = "include/linux/rcutree.h"
WRAPPERS = "include/linux/rcupdate.h"
REJECT_SHA256 = "f247e4e76f87d2b4a922ea9956dbd38d9e681717c1c87a92ee90b920a4f90929"
WRAPPER_DEFINITIONS = {
    "synchronize_rcu_bh": (
        "static inline void synchronize_rcu_bh(void)\n"
        "{\n"
        "\tsynchronize_rcu();\n"
        "}\n"
    ),
    "rcu_barrier_bh": (
        "static inline void rcu_barrier_bh(void)\n"
        "{\n"
        "\trcu_barrier();\n"
        "}\n"
    ),
}


def plan(root: Path):
    tree = root / TREE
    wrappers = root / WRAPPERS
    rejected = root / (TREE + ".rej")
    for file in (tree, wrappers, rejected):
        if not file.is_file():
            raise ValueError("Missing E404 consolidated RCU source or reject: " + str(file))
    raw_reject = rejected.read_bytes()
    digest = hashlib.sha256(raw_reject).hexdigest()
    if digest != REJECT_SHA256:
        raise ValueError("Unexpected rcutree.h reject SHA-256: " + digest)
    rejection = raw_reject.decode("utf-8")
    if len(re.findall(r"(?m)^@@ -\d+", rejection)) != 2:
        raise ValueError("Expected two old RCU-bh declaration hunks")
    for token in (
        "+# define synchronize_rcu_bh\tsynchronize_rcu",
        "+# define rcu_barrier_bh\t\trcu_barrier",
        " void synchronize_rcu_bh(void);",
        " void rcu_barrier_bh(void);",
    ):
        if rejection.count(token) != 1:
            raise ValueError("Old-flavor RT API hunk does not match: " + token)
    current_tree = tree.read_text(encoding="utf-8")
    current_wrappers = wrappers.read_text(encoding="utf-8")
    for name, definition in WRAPPER_DEFINITIONS.items():
        if re.search(r"\b" + name + r"\b", current_tree):
            raise ValueError("E404 rcutree.h reintroduced legacy RCU-bh API: " + name)
        if current_wrappers.count(definition) != 1:
            raise ValueError("E404 unified RCU wrapper missing or duplicated: " + name)
    for symbol in ("void synchronize_rcu(void);", "void rcu_barrier(void);"):
        if current_wrappers.count(symbol) != 1:
            raise ValueError("Unified RCU underlying API missing or duplicated: " + symbol)
    if current_wrappers.count("/* Transitional pre-consolidation compatibility definitions. */") != 1:
        raise ValueError("E404 RCU compatibility API generation changed")
    if "rcu_segcblist" not in (root / "kernel/rcu/tree.c").read_text(encoding="utf-8"):
        raise ValueError("Consolidated E404 RCU architecture not found")
    return rejected, raw_reject


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = parser.parse_args()
    root = args.tree.resolve()
    report = args.report.resolve()
    reject, raw = plan(root)
    report.mkdir(parents=True, exist_ok=True)
    (report / "rcutree-original-reject.diff").write_bytes(raw)
    if args.mode == "apply":
        reject.unlink()
    remaining = len(list(root.rglob("*.rej")))
    result = {
        "stage": "EXP76_RT_STAGE13_CONSOLIDATED_RCU_EQUIVALENCE",
        "synchronize_rcu_bh_already_forwards": True,
        "rcu_barrier_bh_already_forwards": True,
        "source_files_changed": 0,
        "obsolete_hunks_accounted": 2 if args.mode == "apply" else 0,
        "remaining_rejected_files": remaining,
        "kernel_compiled": False,
        "rt_enabled": False,
        "flash_ready": False,
    }
    (report / "stage13-result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    if args.mode == "apply" and remaining != 68:
        raise SystemExit("FAIL_CLOSED: expected exactly 68 unresolved RT reject files")


if __name__ == "__main__":
    main()
