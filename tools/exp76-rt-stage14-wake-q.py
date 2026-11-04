#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage14 RT wake-queue ABI port / NO FLASH
"""Reconcile E404 wake_q header with already-transformed scheduler symbols.

The RT patch changed scheduler definitions to __wake_q_add/__wake_up_q
and supplies sleeper-aware wake queues; the old E404 public declarations
must be replaced by matching inline wrappers, after prerequisites verify.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

TARGET = "include/linux/sched/wake_q.h"
REJECT_SHA256 = "2b090ffb89ce9d08eb6e4f17e0db78fc382f107eaec09d51d19900f7e2d0042d"
ORIGINAL = (
    "extern void wake_q_add(struct wake_q_head *head,\n"
    "\t\t       struct task_struct *task);\n"
    "extern void wake_up_q(struct wake_q_head *head);\n"
)
REPLACEMENT = (
    "extern void __wake_q_add(struct wake_q_head *head,\n"
    "\t\t\t struct task_struct *task, bool sleeper);\n"
    "static inline void wake_q_add(struct wake_q_head *head,\n"
    "\t\t\t      struct task_struct *task)\n"
    "{\n"
    "\t__wake_q_add(head, task, false);\n"
    "}\n\n"
    "static inline void wake_q_add_sleeper(struct wake_q_head *head,\n"
    "\t\t\t\t      struct task_struct *task)\n"
    "{\n"
    "\t__wake_q_add(head, task, true);\n"
    "}\n\n"
    "extern void __wake_up_q(struct wake_q_head *head, bool sleeper);\n"
    "static inline void wake_up_q(struct wake_q_head *head)\n"
    "{\n"
    "\t__wake_up_q(head, false);\n"
    "}\n\n"
    "static inline void wake_up_q_sleeper(struct wake_q_head *head)\n"
    "{\n"
    "\t__wake_up_q(head, true);\n"
    "}\n"
)


def plan(root: Path):
    header = root / TARGET
    reject = root / (TARGET + ".rej")
    core = root / "kernel/sched/core.c"
    sched_header = root / "include/linux/sched.h"
    for file in (header, reject, core, sched_header):
        if not file.is_file():
            raise ValueError("Wake queue RT dependency missing: " + str(file))
    digest = hashlib.sha256(reject.read_bytes()).hexdigest()
    if digest != REJECT_SHA256:
        raise ValueError("Unexpected wake queue rejected hunk: " + digest)
    rej = reject.read_text(encoding="utf-8")
    if len(re.findall(r"(?m)^@@ -\d+", rej)) != 1:
        raise ValueError("Expected one complete wake queue API hunk")
    for token in (
        "+extern void __wake_q_add(",
        "+static inline void wake_q_add_sleeper(",
        "+extern void __wake_up_q(",
        "+static inline void wake_up_q_sleeper(",
    ):
        if rej.count(token) != 1:
            raise ValueError("Unexpected upstream RT wake queue API: " + token)

    before = header.read_text(encoding="utf-8")
    if before.count(ORIGINAL) != 1:
        raise ValueError("E404 legacy wake queue declarations not unique")
    if "__wake_q_add(" in before or "__wake_up_q(" in before:
        raise ValueError("RT wake queue declarations already changed")
    core_text = core.read_text(encoding="utf-8")
    definitions = (
        r"\bvoid __wake_q_add\(struct wake_q_head \*head,\s*"
        r"struct task_struct \*task,\s*bool sleeper\)",
        r"\bvoid __wake_up_q\(struct wake_q_head \*head,\s*bool sleeper\)",
    )
    for token in definitions:
        if len(re.findall(token, core_text)) != 1:
            raise ValueError("RT core.c implementation not found exactly once: " + token)
    if re.search(r"(?m)^void wake_q_add\(", core_text) or re.search(
        r"(?m)^void wake_up_q\(", core_text
    ):
        raise ValueError("Old wake_q symbol still defined in scheduler core")
    sched_text = sched_header.read_text(encoding="utf-8")
    if sched_text.count("wake_q_sleeper") < 1:
        raise ValueError("task_struct lacks the RT sleeper wake queue node")
    if sched_text.count("wake_up_lock_sleeper") < 1:
        raise ValueError("RT lock sleeper wake-up API not declared")
    if "wake_up_lock_sleeper(task);" not in core_text:
        raise ValueError("Scheduler cannot wake sleeper nodes")
    patched = before.replace(ORIGINAL, REPLACEMENT, 1)
    for symbol in ("wake_q_add(", "wake_up_q(", "wake_q_add_sleeper(",
                   "wake_up_q_sleeper(", "__wake_q_add(", "__wake_up_q("):
        if patched.count(symbol) < 1:
            raise ValueError("Missing wake queue API in output: " + symbol)
    return header, reject, patched


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tree", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--mode", choices=("verify", "apply"), required=True)
    a = p.parse_args()
    root = a.tree.resolve()
    header, reject, patched = plan(root)
    if a.mode == "apply":
        header.write_text(patched, encoding="utf-8")
        reject.unlink()
    remaining = len(list(root.rglob("*.rej")))
    status = {
        "stage": "EXP76_RT_STAGE14_WAKE_Q_ABI",
        "applied": a.mode == "apply",
        "scheduler_core_uses_rt_internal_wake_queue": True,
        "task_struct_wake_q_sleeper_verified": True,
        "public_wrappers_match_core": a.mode == "apply",
        "remaining_rejected_files": remaining,
        "kernel_compiled": False,
        "rt_enabled": False,
        "flash_ready": False,
    }
    a.report.mkdir(parents=True, exist_ok=True)
    (a.report / "stage14-result.json").write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(status, indent=2))
    if a.mode == "apply" and remaining != 67:
        raise SystemExit("FAIL_CLOSED: expected 67 remaining rejected files")


if __name__ == "__main__":
    main()
