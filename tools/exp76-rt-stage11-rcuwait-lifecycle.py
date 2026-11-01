#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage11 rcuwait lifecycle close-out / NO FLASH
"""Finish the two remaining RT rcuwait header hunks after checking linked APIs.

This is a source-only port. Verify the already-applied RT implementation of
finish_rcuwait() and int rcuwait_wake_up() before changing any header data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

HEADER = "include/linux/rcuwait.h"
PENDING_REJECT_SHA256 = "a3eebeb86080548ebad293a0c041b480b3b929981654445a8138e4b43dffeacf"
COMMENT_OLD = " * such that writes to @task are properly serialized."
COMMENT_NEW = (
    " * and [prepare_to/finish]_rcuwait() such that writes to @task are\n"
    " * properly serialized."
)
MACRO = "#define rcuwait_wait_event(w, condition, state)"
INJECTION = (
    "static inline void prepare_to_rcuwait(struct rcuwait *w)\n"
    "{\n"
    "\trcu_assign_pointer(w->task, current);\n"
    "}\n\n"
    "extern void finish_rcuwait(struct rcuwait *w);\n\n"
)
UPDATE_IMPL = (
    "void finish_rcuwait(struct rcuwait *w)\n"
    "{\n"
    "\trcu_assign_pointer(w->task, NULL);\n"
    "\t__set_current_state(TASK_RUNNING);\n"
    "}\n"
    "EXPORT_SYMBOL_GPL(finish_rcuwait);"
)
REPLACEMENTS = {
    "rcu_assign_pointer((w)->task, current);": "prepare_to_rcuwait(w);",
    "WRITE_ONCE((w)->task, NULL);": "finish_rcuwait(w);",
}
REJECT_HEADER = "diff a/include/linux/rcuwait.h b/include/linux/rcuwait.h\t(rejected hunks)\n"


def plan(tree: Path):
    file = tree / HEADER
    reject = tree / (HEADER + ".rej")
    exit_file = tree / "kernel/exit.c"
    update_file = tree / "kernel/rcu/update.c"
    for path in (file, reject, exit_file, update_file):
        if not path.is_file():
            raise ValueError("Missing required rcuwait source/reject: " + str(path))

    raw = reject.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != PENDING_REJECT_SHA256:
        raise ValueError("Unrecognized rcuwait pending reject SHA-256: " + digest)
    rej_text = raw.decode("utf-8")
    if not rej_text.startswith(REJECT_HEADER):
        raise ValueError("Rejected patch file header does not match E404")
    hunks = re.findall(r"(?m)^@@ -\d+", rej_text)
    if len(hunks) != 2:
        raise ValueError(f"Expected 2 pending rcuwait hunks, got {len(hunks)}")
    for must in (
        "+static inline void prepare_to_rcuwait(struct rcuwait *w)",
        "+extern void finish_rcuwait(struct rcuwait *w);",
        "+\tprepare_to_rcuwait(w);",
        "+\tfinish_rcuwait(w);",
    ):
        if rej_text.count(must) != 1:
            raise ValueError("Upstream RT lifecycle change unexpectedly absent: " + must)

    header = file.read_text(encoding="utf-8")
    if header.count("extern int rcuwait_wake_up(struct rcuwait *w);") != 1:
        raise ValueError("Stage10 int rcuwait wakeup declaration missing")
    if header.count("static inline int rcuwait_active(struct rcuwait *w)") != 1:
        raise ValueError("Stage10 rcuwait_active missing")
    if header.count(MACRO) != 1:
        raise ValueError("E404 three-argument wait macro missing")
    if header.count(COMMENT_OLD) != 1 or "finish_rcuwait(" in header:
        raise ValueError("Unexpected rcuwait lifecycle state")
    if header.count("signal_pending_state(state, current)") != 1:
        raise ValueError("Missing E404 signal-aware wait")
    if header.count("__ret = -EINTR;") != 1:
        raise ValueError("Missing EINTR propagation")
    for before in REPLACEMENTS:
        if header.count(before) != 1:
            raise ValueError("Missing or duplicate old wait primitive: " + before)
    if header.count("__set_current_state(TASK_RUNNING);") != 1:
        raise ValueError("Missing exact old task-state restore")
    if header.count("__ret;") != 1:
        raise ValueError("Missing wait macro result expression")

    exit_body = exit_file.read_text(encoding="utf-8")
    if exit_body.count("int rcuwait_wake_up(struct rcuwait *w)") != 1:
        raise ValueError("Post-RT kernel/exit.c wakeup must return int")
    match = re.search(
        r"int rcuwait_wake_up\(struct rcuwait \*w\)\s*\{(?P<body>.*?)\n\}",
        exit_body, re.DOTALL
    )
    if not match or "return ret;" not in match.group("body"):
        raise ValueError("Post-RT int wakeup implementation lacks return")
    update_body = update_file.read_text(encoding="utf-8")
    if update_body.count(UPDATE_IMPL) != 1:
        raise ValueError("finish_rcuwait() implementation or GPL export diverged")

    updated = header.replace(COMMENT_OLD, COMMENT_NEW, 1)
    updated = updated.replace(MACRO, INJECTION + MACRO, 1)
    for old, new in REPLACEMENTS.items():
        updated = updated.replace(old, new, 1)
    old_restore = "__set_current_state(TASK_RUNNING);"
    if updated.count(old_restore) != 1:
        raise ValueError("Cannot relocate task-state restoration exactly once")
    updated = updated.replace(old_restore, "", 1)
    # Clean the now-empty macro continuation line that precedes __ret.
    if not all(updated.count(x) == 1 for x in (
        "static inline void prepare_to_rcuwait(struct rcuwait *w)",
        "extern void finish_rcuwait(struct rcuwait *w);",
        "prepare_to_rcuwait(w);",
        "finish_rcuwait(w);",
    )):
        raise ValueError("Generated lifecycle helper references not unique")
    if "WRITE_ONCE((w)->task, NULL);" in updated or "rcu_assign_pointer((w)->task, current);" in updated:
        raise ValueError("Legacy wait lifecycle remains after conversion")
    return file, reject, updated


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = parser.parse_args()
    root = args.tree.resolve()
    file, reject, updated = plan(root)
    if args.mode == "apply":
        file.write_text(updated, encoding="utf-8")
        reject.unlink()
    remaining = len(list(root.rglob("*.rej")))
    summary = {
        "stage": "EXP76_RT_STAGE11_RCUWAIT_LIFECYCLE",
        "applied": args.mode == "apply",
        "prepare_to_rcuwait": args.mode == "apply",
        "finish_rcuwait_definition_already_in_rt_update_c": True,
        "wakeup_return_type": "int",
        "wait_signal_behavior_preserved": True,
        "remaining_rcuwait_reject_hunks": 0 if args.mode == "apply" else 2,
        "remaining_rejected_files": remaining,
        "kernel_compiled": False,
        "rt_enabled": False,
        "flash_ready": False,
    }
    args.report.mkdir(parents=True, exist_ok=True)
    (args.report / "stage11-status.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    if args.mode == "apply" and remaining != 70:
        raise SystemExit("FAIL_CLOSED: expected 70 remaining rejected files")


if __name__ == "__main__":
    main()
