#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage51 E404-RT neighbour pointer reconciliation / NO FLASH
"""Reconcile the RT hh_cache mutable-reader ABI with E404's skip_cache caller.

The older RT patch converts neigh_hh_output() to accept a mutable hh_cache
because RT seqlocks can require mutable state. E404's vendor neigh_output()
retains a const local and an extra skip_cache parameter, so the upstream
corresponding caller hunk does not land. Change only that local's qualifier.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HEADER = "include/net/neighbour.h"
CALLEE = "static inline int neigh_hh_output(struct hh_cache *hh, struct sk_buff *skb)\n"
CALLER_OLD = (
    "static inline int neigh_output(struct neighbour *n, struct sk_buff *skb,\n"
    "\t\t\t       bool skip_cache)\n"
    "{\n"
    "\tconst struct hh_cache *hh = &n->hh;\n\n"
    "\tif ((n->nud_state & NUD_CONNECTED) && hh->hh_len && !skip_cache)\n"
    "\t\treturn neigh_hh_output(hh, skb);\n"
    "\telse\n"
    "\t\treturn n->output(n, skb);\n"
    "}\n"
)
CALLER_NEW = CALLER_OLD.replace(
    "\tconst struct hh_cache *hh = &n->hh;\n",
    "\tstruct hh_cache *hh = &n->hh;\n",
)


def one(contents: str, fragment: str, label: str) -> None:
    n = contents.count(fragment)
    if n != 1:
        raise ValueError(f"{label}: expected exactly one match, got {n}")


def prepare(tree: Path) -> tuple[str, dict]:
    if not (tree / ".git").is_dir():
        raise ValueError("Expected isolated E404 git checkout")
    src = tree / HEADER
    if not src.is_file():
        raise ValueError("Missing pinned E404 networking header")
    rejects = len(list(tree.rglob("*.rej")))
    if rejects != 64 or not (tree / "kernel/sched/cpupri.c.rej").is_file():
        raise ValueError(f"Expected 64 unresolved RT rejects and cpupri.c.rej, got {rejects}")
    before = src.read_text(encoding="utf-8")
    one(before, CALLEE, "RT mutable neigh_hh_output ABI")
    one(before, CALLER_OLD, "E404 neigh_output vendor skip_cache caller")
    if CALLER_NEW in before:
        raise ValueError("neigh_output caller already ported; review instead of reapplying")
    after = before.replace(CALLER_OLD, CALLER_NEW, 1)
    if after == before or CALLER_OLD in after:
        raise ValueError("E404 neighbour pointer qualifier was not reconciled")
    one(after, CALLER_NEW, "Reconciled neighbour caller")
    one(after, CALLEE, "Preserved RT callee signature")
    return after, {
        "stage": "EXP76_STAGE51_NEIGH_HH_RT_MUTABLE_POINTER_NONFLASH",
        "source": HEADER,
        "original_sha256": hashlib.sha256(before.encode()).hexdigest(),
        "patched_sha256": hashlib.sha256(after.encode()).hexdigest(),
        "rt_neigh_hh_output_requires_mutable_pointer": True,
        "e404_skip_cache_signature_preserved": True,
        "changed_only_neigh_output_local_const_qualifier": True,
        "remaining_rejected_files": rejects,
        "kernel_built": False,
        "flash_ready": False,
    }


def execute(tree: Path, report: Path, mode: str) -> dict:
    if mode not in ("verify", "apply"):
        raise ValueError("Unsupported Stage51 mode")
    after, status = prepare(tree)
    if mode == "apply":
        (tree / HEADER).write_text(after, encoding="utf-8")
        if (tree / HEADER).read_text(encoding="utf-8") != after:
            raise ValueError("Stage51 source write verification failed")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage51 changed unresolved RT reject count")
    status["applied"] = mode == "apply"
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage51-status.json").write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8"
    )
    return status


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.tree.resolve(), args.report.resolve(), args.mode), indent=2))


if __name__ == "__main__":
    main()
