#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 RT Stage10 rcuwait header partial port / NO FLASH
"""Port rcuwait_active() and mark two already-satisfied rejected hunks.

The remaining rcuwait changes concern wake-up return type and wait lifecycle.
They are intentionally NOT applied until kernel/exit.c and callers are ported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

TARGET = "include/linux/rcuwait.h"
REJECT_SHA256 = "ddbd68a50a46cb0aa1871629b6d50519d9ce97ceba5af83301f538f579a96742"
REJECT_HEADER = "diff a/include/linux/rcuwait.h b/include/linux/rcuwait.h\t(rejected hunks)\n"
HUNK_PATTERN = re.compile(r"(?m)(?=^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@)")
ANCHOR = "extern void rcuwait_wake_up(struct rcuwait *w);\n"
ACTIVE = (
    "\n/* Same serialization requirements as waitqueue_active(). */\n"
    "static inline int rcuwait_active(struct rcuwait *w)\n"
    "{\n"
    "\treturn !!rcu_access_pointer(w->task);\n"
    "}\n"
)


def prepare(tree: Path):
    src = tree / TARGET
    reject = tree / (TARGET + ".rej")
    exit_c = tree / "kernel/exit.c"
    rcu_h = tree / "include/linux/rcupdate.h"
    for p in (src, reject, exit_c, rcu_h):
        if not p.is_file():
            raise ValueError("Required rcuwait implementation missing: " + str(p))
    rejected = reject.read_bytes()
    got = hashlib.sha256(rejected).hexdigest()
    if got != REJECT_SHA256:
        raise ValueError("rcuwait reject SHA mismatch: " + got)
    patch = rejected.decode("utf-8")
    if not patch.startswith(REJECT_HEADER):
        raise ValueError("Unknown rcuwait .rej header")
    parts = HUNK_PATTERN.split(patch)
    if len(parts) != 5 or parts[0] != REJECT_HEADER:
        raise ValueError("Expected four exact rcuwait hunks")
    hunks = parts[1:]
    if any(not h.startswith("@@ -") for h in hunks):
        raise ValueError("Malformed rcuwait rejected hunk")
    h1, h2, h3, h4 = hunks
    if [line for line in h1.splitlines() if line.startswith("+")] != [
        "+#include <linux/sched/signal.h>"
    ]:
        raise ValueError("Unexpected include hunk content")
    if [line for line in h2.splitlines() if line.startswith("+")] != [
        "+\tstruct task_struct __rcu *task;"
    ]:
        raise ValueError("Unexpected RCU-annotated pointer hunk")
    if "+extern int rcuwait_wake_up(struct rcuwait *w);" not in h3:
        raise ValueError("Missing unresolved wake-up signature hunk")
    if "+\tfinish_rcuwait(w);" not in h4:
        raise ValueError("Missing unresolved finish_rcuwait hunk")

    before = src.read_text(encoding="utf-8")
    if before.count("#include <linux/sched/signal.h>\n") != 1:
        raise ValueError("E404 signal include not already present")
    if before.count("struct task_struct __rcu *task;") != 1:
        raise ValueError("E404 RCU pointer annotation not already present")
    if before.count(ANCHOR) != 1 or "rcuwait_active(" in before:
        raise ValueError("Header wakeup contract changed or active helper duplicated")
    if before.count("#define rcuwait_wait_event(w, condition, state)") != 1:
        raise ValueError("E404 3-arg wait macro missing")
    if before.count("signal_pending_state(state, current)") != 1:
        raise ValueError("E404 signal-aware wait path missing")
    if "rcu_access_pointer" not in rcu_h.read_text(encoding="utf-8"):
        raise ValueError("RCU pointer inspection macro missing")
    impl = exit_c.read_text(encoding="utf-8")
    if impl.count("void rcuwait_wake_up(struct rcuwait *w)") != 1:
        signatures = [s.strip() for s in impl.splitlines()
                      if "rcuwait_wake_up" in s or "finish_rcuwait" in s]
        raise ValueError("Post-RT kernel/exit.c wakeup ABI differs: "
                         + json.dumps(signatures[:25]))
    if impl.count("task = rcu_dereference(w->task);") != 1:
        raise ValueError("E404 kernel/exit.c RCU dereference changed")
    after = before.replace(ANCHOR, ANCHOR + ACTIVE, 1)
    remaining = REJECT_HEADER + h3 + h4
    if len(HUNK_PATTERN.split(remaining)) != 3:
        raise ValueError("Expected two remaining rcuwait hunks")
    return src, reject, after, remaining


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = ap.parse_args()
    root = args.tree.resolve()
    src, rej, replacement, remaining = prepare(root)
    if args.mode == "apply":
        src.write_text(replacement, encoding="utf-8")
        rej.write_text(remaining, encoding="utf-8")
    pending = len(list(root.rglob("*.rej")))
    result = {
        "stage": "EXP76_RT_STAGE10_RCUWAIT_PARTIAL",
        "vendor_equivalent_hunks": 2,
        "rcuwait_active_added": args.mode == "apply",
        "rcuwait_remaining_hunks": 2,
        "wakeup_signature_changed": False,
        "wait_lifecycle_changed": False,
        "remaining_rejected_files": pending,
        "kernel_built": False,
        "rt_enabled": False,
        "flash_ready": False,
    }
    args.report.mkdir(parents=True, exist_ok=True)
    (args.report / "stage10-status.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    (args.report / "rcuwait-pending.rej").write_text(remaining, encoding="utf-8")
    print(json.dumps(result, indent=2))
    if args.mode == "apply" and pending != 71:
        raise SystemExit("FAIL_CLOSED: remaining file count changed unexpectedly")


if __name__ == "__main__":
    main()
