#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage17 wake flag ABI source port / NO FLASH
"""Resolve wake-queue sleeper wake flag without colliding with E404 WF_TTWU.

Upstream RT used WF_LOCK_SLEEPER=0x08, but E404 already uses 0x08
for WF_TTWU. Allocate 0x100 after E404's 0x80 WF_RQ_SELECTED, with
an exact conflict check. Keep the unrelated nr_pinned hunk pending.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

HEADER = "kernel/sched/sched.h"
REJECT_SHA = "2e7e8006d37cb7742259dd1c798c3ebb780b8fcbbb914f0dc4e877459d04bd6f"
REJECT_HEADER = "diff a/kernel/sched/sched.h b/kernel/sched/sched.h\t(rejected hunks)\n"
HUNK = re.compile(r"(?m)(?=^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@)")
ANCHOR = "#define WF_RQ_SELECTED\t\t0x80 /* ->select_task_rq() was called */\n"
DEFINE = "#define WF_LOCK_SLEEPER 0x100 /* Wakeup from a sleeping RT lock */\n"
TARGET = 0x100


def plan(root: Path):
    source = root / HEADER
    reject = root / (HEADER + ".rej")
    core = root / "kernel/sched/core.c"
    for path in (source, reject, core):
        if not path.is_file():
            raise ValueError("Missing post-RT scheduler input: " + str(path))
    sha = hashlib.sha256(reject.read_bytes()).hexdigest()
    if sha != REJECT_SHA:
        raise ValueError("Unrecognized scheduler rejected patch SHA: " + sha)
    patch = reject.read_text(encoding="utf-8")
    if not patch.startswith(REJECT_HEADER):
        raise ValueError("Unknown rejected hunk header")
    pieces = HUNK.split(patch)
    if len(pieces) != 3 or pieces[0] != REJECT_HEADER:
        raise ValueError("Expected two rejected sched.h hunks")
    pinned, sleeper = pieces[1:]
    if pinned.count("+\tint\t\t\tnr_pinned;") != 1:
        raise ValueError("First rejected hunk is not the upstream nr_pinned field")
    if "#if defined(CONFIG_PREEMPT_RT_BASE) && defined(CONFIG_SMP)" not in pinned:
        raise ValueError("Missing upstream nr_pinned conditional")
    if sleeper.count("+\t#define WF_LOCK_SLEEPER") != 0:
        raise ValueError("Unexpected upstream sleeper macro location")
    if len([s for s in sleeper.splitlines() if s.startswith("+")]) != 1:
        raise ValueError("Unexpected additions in wakeup flag rejected hunk")
    if not any(line.startswith("+") and
               "#define WF_LOCK_SLEEPER" in line and "0x08" in line
               for line in sleeper.splitlines()):
        raise ValueError("Expected old RT-140 WF_LOCK_SLEEPER=0x08 addition")
    existing = source.read_text(encoding="utf-8")
    if existing.count(ANCHOR) != 1:
        raise ValueError("E404 wake flag anchor changed")
    if "WF_LOCK_SLEEPER" in existing:
        raise ValueError("Wake lock flag already defined")
    flags = {}
    for name, value in re.findall(
        r"(?m)^#define (WF_[A-Z_0-9]+)\s+(0x[0-9a-fA-F]+)\b",
        existing,
    ):
        if name in flags:
            raise ValueError("Duplicate wake flag definition: " + name)
        flags[name] = int(value, 16)
    required = {
        "WF_EXEC": 0x02, "WF_FORK": 0x04, "WF_TTWU": 0x08,
        "WF_SYNC": 0x10, "WF_MIGRATED": 0x20,
        "WF_ON_CPU": 0x40, "WF_RQ_SELECTED": 0x80,
    }
    if any(flags.get(name) != value for name, value in required.items()):
        raise ValueError("Unexpected vendor wake-flag ABI; do not port")
    if any(value & TARGET for value in flags.values()):
        raise ValueError("New WF_LOCK_SLEEPER bit collides with another wake flag")
    body = core.read_text(encoding="utf-8")
    if body.count(
        "return try_to_wake_up(p, TASK_UNINTERRUPTIBLE, WF_LOCK_SLEEPER);"
    ) != 1:
        raise ValueError("Post-RT wake_up_lock_sleeper call not unique")
    if body.count("int wake_up_lock_sleeper(struct task_struct *p)") != 1:
        raise ValueError("Post-RT wake sleeper function missing")
    if len(list(root.rglob("*.rej"))) != 66:
        raise ValueError("Unexpected number of RT rejects before Stage17")

    updated = existing.replace(ANCHOR, ANCHOR + DEFINE, 1)
    if updated.count(DEFINE) != 1:
        raise ValueError("WF_LOCK_SLEEPER insertion is not unique")
    remainder = REJECT_HEADER + pinned
    if len(HUNK.split(remainder)) != 2:
        raise ValueError("Unexpected pending nr_pinned reject hunk count")
    return source, reject, updated, remainder, flags


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = parser.parse_args()
    root = args.tree.resolve()
    source, reject, updated, remainder, previous = plan(root)
    report = args.report.resolve()
    report.mkdir(parents=True, exist_ok=True)
    (report / "pending-nr-pinned.rej").write_text(remainder, encoding="utf-8")
    if args.mode == "apply":
        source.write_text(updated, encoding="utf-8")
        reject.write_text(remainder, encoding="utf-8")
    remaining = len(list(root.rglob("*.rej")))
    status = {
        "stage": "EXP76_RT_STAGE17_WAKE_FLAGS",
        "applied": args.mode == "apply",
        "e404_wf_ttwu": hex(previous["WF_TTWU"]),
        "rt140_original_wf_lock_sleeper": "0x08 (collides with E404 WF_TTWU)",
        "ported_wf_lock_sleeper": hex(TARGET),
        "wake_flag_collision": False,
        "nr_pinned_hunk_retained": True,
        "sched_h_rejected_hunks_remaining": 1,
        "remaining_rejected_files": remaining,
        "scheduler_affinity_abi_blocked": True,
        "kernel_compiled": False,
        "rt_enabled": False,
        "flash_ready": False,
    }
    (report / "stage17-result.json").write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(status, indent=2))
    if args.mode == "apply" and remaining != 66:
        raise SystemExit("FAIL_CLOSED: expected 66 rejected files after Stage17")


if __name__ == "__main__":
    main()
