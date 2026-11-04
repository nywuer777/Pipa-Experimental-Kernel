#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 RT stage3 rtmutex WW slowlock API port
"""Reconcile one specific E404/RT rtmutex rejected hunk; source-only, NO FLASH."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

TARGET = "kernel/locking/rtmutex.c"
REJECT_SHA = "e9e65a6d2aa9213e00f05859bc93df5a1d64e7b7100c369caa7aacdf0986f3c5"
START = "int __sched rt_mutex_slowlock_locked("
END = "static int __sched\nrt_mutex_slowlock("
BEFORE = """\tret = task_blocks_on_rt_mutex(lock, &waiter, current, chwalk);

\tif (likely(!ret))
\t\t/* sleep on the mutex */
\t\tret = __rt_mutex_slowlock(lock, state, timeout, &waiter);

\tif (unlikely(ret)) {
\t\t__set_current_state(TASK_RUNNING);
\t\tremove_waiter(lock, &waiter);
\t\trt_mutex_handle_deadlock(ret, chwalk, &waiter);
\t}
"""
AFTER = """\tret = task_blocks_on_rt_mutex(lock, waiter, current, chwalk);

\tif (likely(!ret)) {
\t\t/* sleep on the mutex */
\t\tret = __rt_mutex_slowlock(lock, state, timeout, waiter,
\t\t\t\t\t  ww_ctx);
\t} else if (ww_ctx) {
\t\t/* ww_mutex received EDEADLK, let it become EALREADY */
\t\tret = __mutex_lock_check_stamp(lock, ww_ctx);
\t\tBUG_ON(!ret);
\t}

\tif (unlikely(ret)) {
\t\t__set_current_state(TASK_RUNNING);
\t\tremove_waiter(lock, waiter);
\t\t/* ww_mutex wants to report EDEADLK/EALREADY, let it */
\t\tif (!ww_ctx)
\t\t\trt_mutex_handle_deadlock(ret, chwalk, waiter);
\t} else if (ww_ctx) {
\t\tww_mutex_account_lock(lock, ww_ctx);
\t}
"""


def prepare(tree: Path):
    source = tree / TARGET
    reject = tree / (TARGET + ".rej")
    if not source.is_file() or not reject.is_file():
        raise ValueError("rtmutex source/rejection missing")
    got = hashlib.sha256(reject.read_bytes()).hexdigest()
    if got != REJECT_SHA:
        raise ValueError("Unknown RT rejected hunk: " + got)
    body = source.read_text(encoding="utf-8")
    if body.count(START) != 1 or body.count(END) != 1:
        raise ValueError("Unrecognized rtmutex slowlock functions")
    first = body.index(START)
    last = body.index(END, first)
    method = body[first:last]
    if method.count(BEFORE) != 1 or "ret = __rt_mutex_slowlock(lock, state, timeout, waiter," in method:
        raise ValueError("Expected E404 stale slowlock hunk not found exactly once")
    if "struct rt_mutex_waiter *waiter)" not in method or "struct ww_acquire_ctx *ww_ctx," not in method:
        raise ValueError("RT slowlock_locked signature not verified")
    if not re.search(
        r"static void rt_mutex_handle_deadlock\(int res, int detect_deadlock,\s*"
        r"struct rt_mutex_waiter \*w\)", body
    ):
        raise ValueError("E404 three-argument deadlock handler signature mismatch")
    if not re.search(
        r"__rt_mutex_slowlock\(struct rt_mutex \*lock, int state,\s*"
        r"struct hrtimer_sleeper \*timeout,\s*"
        r"struct rt_mutex_waiter \*waiter,\s*"
        r"struct ww_acquire_ctx \*ww_ctx\)", body
    ):
        raise ValueError("RT __rt_mutex_slowlock five-argument signature mismatch")
    for symbol in ("__mutex_lock_check_stamp(", "ww_mutex_account_lock(", "BUG_ON("):
        if symbol not in body:
            raise ValueError("Missing RT ww_mutex prerequisite: " + symbol)
    updated = method.replace(BEFORE, AFTER, 1)
    if updated.count("rt_mutex_handle_deadlock(ret, chwalk, waiter);") != 1:
        raise ValueError("Unexpected E404 deadlock call")
    if updated.count("ww_mutex_account_lock(lock, ww_ctx);") < 1:
        raise ValueError("WW lock accounting not preserved")
    return source, reject, body[:first] + updated + body[last:]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tree", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--mode", choices=("verify", "apply"), required=True)
    a = p.parse_args()
    tree = a.tree.resolve()
    a.report.mkdir(parents=True, exist_ok=True)
    source, rejected, candidate = prepare(tree)
    if a.mode == "apply":
        source.write_text(candidate, encoding="utf-8")
        rejected.unlink()
    remaining = len(list(tree.rglob("*.rej")))
    status = {
        "stage": "EXP76_RT_STAGE3_SOURCE_ONLY",
        "ported_file": TARGET,
        "source_patched": a.mode == "apply",
        "rtmutex_hunk_sha256": REJECT_SHA,
        "ww_ctx_api_checked": True,
        "e404_deadlock_signature_preserved": True,
        "remaining_rejected_files": remaining,
        "kernel_compiled": False,
        "rt_config_enabled": False,
        "flash_ready": False,
    }
    (a.report / "stage3-result.json").write_text(json.dumps(status, indent=2) + "\n")
    print(json.dumps(status, indent=2))
    if a.mode == "apply" and remaining != 78:
        raise SystemExit("FAIL_CLOSED: expected 78 remaining rejected files")


if __name__ == "__main__":
    main()
