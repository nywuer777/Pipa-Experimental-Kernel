#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage8 RCU equivalence audit / NO FLASH
"""Account for two upstream RCU rejects already satisfied by E404.

Remove only two verified hunks from the temporary .rej; kernel/rcu/tree.c
is not modified. The remaining 18 RCU hunks continue to block integration.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

TARGET = "kernel/rcu/tree.c"
REJECT_SHA256 = "af6142fea7219367bfdcf13db46ab291558234dd3db486462371c95845012242"
HEADER = "diff a/kernel/rcu/tree.c b/kernel/rcu/tree.c\t(rejected hunks)\n"
INCLUDES = (
    "#include <linux/delay.h>",
    "#include <linux/gfp.h>",
    "#include <linux/oom.h>",
    "#include <linux/smpboot.h>",
    "#include <linux/jiffies.h>",
    "#include <linux/sched/isolation.h>",
    '#include "../time/tick-internal.h"',
)
IRQ_INIT = (
    "\t\t\tinit_irq_work(&rdp->rcu_iw, rcu_iw_handler);\n"
    "\t\t\tatomic_set(&rdp->rcu_iw.flags, IRQ_WORK_HARD_IRQ);\n"
    "\t\t\trdp->rcu_iw_pending = true;\n"
)
UPSTREAM_ASSIGNMENT = "+\t\t\trdp->rcu_iw.flags = IRQ_WORK_HARD_IRQ;"
HUNK_SPLIT = re.compile(r"(?m)(?=^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@)")


def analyze(tree: Path) -> tuple[Path, bytes, str, dict]:
    source_file = tree / TARGET
    rej_file = tree / (TARGET + ".rej")
    irq_header = tree / "include/linux/irq_work.h"
    if not all(p.is_file() for p in (source_file, rej_file, irq_header)):
        raise ValueError("Missing RCU source, reject or IRQ_WORK declaration")
    raw = rej_file.read_bytes()
    if hashlib.sha256(raw).hexdigest() != REJECT_SHA256:
        raise ValueError("RCU reject SHA-256 mismatch: source drift")
    original = raw.decode("utf-8")
    if not original.startswith(HEADER):
        raise ValueError("Unrecognized RCU reject header")
    pieces = HUNK_SPLIT.split(original)
    if len(pieces) != 21 or pieces[0] != HEADER:
        raise ValueError("Expected exactly 20 original RCU rejected hunks")
    hunks = pieces[1:]
    if any(not p.startswith("@@ -") for p in hunks):
        raise ValueError("Malformed original reject hunk")
    first = [x for x in hunks if all("+" + inc in x for inc in INCLUDES)]
    irq = [x for x in hunks if UPSTREAM_ASSIGNMENT in x]
    if len(first) != 1 or len(irq) != 1 or first[0] == irq[0]:
        raise ValueError("Missing or duplicated equivalent RT hunks")
    if any(line.startswith("+") and not line.startswith("++")
           and line[1:] not in INCLUDES
           for line in first[0].splitlines()):
        raise ValueError("Unexpected additions in include-only hunk")
    if [line for line in irq[0].splitlines() if line.startswith("+")] != [UPSTREAM_ASSIGNMENT]:
        raise ValueError("Unexpected additions in IRQ flag hunk")
    source = source_file.read_text(encoding="utf-8")
    for inc in INCLUDES:
        if source.count(inc + "\n") != 1:
            raise ValueError("Missing or duplicated vendor include " + inc)
    if source.count(IRQ_INIT) != 1:
        raise ValueError("Vendor IRQ flag initialization not unique")
    declarations = irq_header.read_text(encoding="utf-8")
    if declarations.count("atomic_t flags;") != 1 or declarations.count("#define IRQ_WORK_HARD_IRQ\tBIT(3)") != 1:
        raise ValueError("IRQ flags type or bit changed")
    if "rdp->rcu_iw.flags = IRQ_WORK_HARD_IRQ" in source:
        raise ValueError("Invalid scalar write to atomic_t flags found in E404")
    remaining = [h for h in hunks if h not in first and h not in irq]
    if len(remaining) != 18:
        raise ValueError("Unexpected number of surviving RCU hunks")
    transformed = HEADER + "".join(remaining)
    if len(HUNK_SPLIT.split(transformed)) != 19:
        raise ValueError("RCU reject accounting inconsistent")
    detail = {
        "stage": "EXP76_RT_STAGE8_RCU_VENDOR_EQUIVALENCE",
        "input_reject_sha256": REJECT_SHA256,
        "original_rcu_hunks": 20,
        "resolved_equivalent_hunks": 2,
        "remaining_rcu_hunks": 18,
        "vendor_include_hunk_preexisting": True,
        "vendor_rcu_irqwork_atomic_set_preexisting": True,
        "rcu_source_modified": False,
        "flash_ready": False,
        "kernel_compiled": False,
        "rt_config_enabled": False,
    }
    return rej_file, raw, transformed, detail


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = ap.parse_args()
    tree = args.tree.resolve()
    report = args.report.resolve()
    reject, original, next_reject, detail = analyze(tree)
    report.mkdir(parents=True, exist_ok=True)
    (report / "rcu-original-reject-sha256.txt").write_text(
        hashlib.sha256(original).hexdigest() + "\n", encoding="utf-8"
    )
    (report / "rcu-remaining-reject-preview.diff").write_text(next_reject, encoding="utf-8")
    if args.mode == "apply":
        reject.write_text(next_reject, encoding="utf-8")
    detail["applied_to_reject_manifest"] = args.mode == "apply"
    detail["remaining_rejected_files"] = len(list(tree.rglob("*.rej")))
    if args.mode == "apply" and detail["remaining_rejected_files"] != 71:
        raise SystemExit("FAIL_CLOSED: expected 71 remaining rejected files")
    (report / "stage8-status.json").write_text(
        json.dumps(detail, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(detail, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
