#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage35 RT kernel might_sleep no-state-check port / NO FLASH
"""Restore the exact PREEMPT_RT might_sleep_no_state_check rejected definitions.

This is the kernel.h RT reject's debug and non-debug implementation, NOT
an empty shim or a replacement for __might_sleep. Both definitions preserve
might_resched(); the debug branch uses ___might_sleep() deliberately so it
does not check the task's sleep state.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

HEADER = "include/linux/kernel.h"
REJECT = "include/linux/kernel.h.rej"
RTMUTEX = "kernel/locking/rtmutex.c"
PENDING = "kernel/sched/cpupri.c.rej"
DEBUG_ANCHOR = (
    "# define might_sleep() \\\n"
    "\tdo { __might_sleep(__FILE__, __LINE__, 0); might_resched(); } while (0)\n"
)
DEBUG_DEFINE = (
    "# define might_sleep_no_state_check() \\\n"
    "\tdo { ___might_sleep(__FILE__, __LINE__, 0); might_resched(); } while (0)\n"
)
NORMAL_ANCHOR = "# define might_sleep() do { might_resched(); } while (0)\n"
NORMAL_DEFINE = "# define might_sleep_no_state_check() do { might_resched(); } while (0)\n"
REJECT_DEBUG = (
    "+# define might_sleep_no_state_check() \\\n"
    "+\tdo { ___might_sleep(__FILE__, __LINE__, 0); might_resched(); } while (0)"
)
REJECT_NORMAL = "+# define might_sleep_no_state_check() do { might_resched(); } while (0)"


def once(data: str, pattern: str, where: str) -> None:
    seen = data.count(pattern)
    if seen != 1:
        raise ValueError(f"{where}: expected one {pattern!r}, found {seen}")


def prepare(root: Path) -> str:
    for path in (HEADER, REJECT, RTMUTEX, PENDING):
        if not (root / path).is_file():
            raise ValueError("Missing pinned Stage34 RT prerequisite: " + path)
    count = len(list(root.rglob("*.rej")))
    if count != 64:
        raise ValueError(f"Stage35 expects 64 RT rejects, saw {count}")
    reject = (root / REJECT).read_text(encoding="utf-8")
    once(reject, REJECT_DEBUG, REJECT)
    once(reject, REJECT_NORMAL, REJECT)
    mutex = (root / RTMUTEX).read_text(encoding="utf-8")
    once(mutex, "might_sleep_no_state_check();", RTMUTEX)
    header = (root / HEADER).read_text(encoding="utf-8")
    once(header, DEBUG_ANCHOR, HEADER)
    once(header, NORMAL_ANCHOR, HEADER)
    once(header, "extern void ___might_sleep(const char *file, int line, int preempt_offset);", HEADER)
    once(header, "static inline void ___might_sleep(const char *file, int line,", HEADER)
    if "# define might_sleep_no_state_check()" in header:
        raise ValueError("RT might_sleep_no_state_check already declared in kernel.h")
    result = header.replace(DEBUG_ANCHOR, DEBUG_ANCHOR + DEBUG_DEFINE, 1)
    result = result.replace(NORMAL_ANCHOR, NORMAL_ANCHOR + NORMAL_DEFINE, 1)
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    p.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = p.parse_args()
    root = args.tree.resolve()
    updated = prepare(root)
    if args.mode == "apply":
        (root / HEADER).write_text(updated, encoding="utf-8")
    count = len(list(root.rglob("*.rej")))
    if count != 64:
        raise ValueError("Stage35 changed the number of RT rejects")
    status = {
        "stage": "EXP76_STAGE35_RT_MIGHT_SLEEP_NO_STATE_CHECK",
        "applied": args.mode == "apply",
        "debug_branch_uses_triple_underscore_might_sleep": True,
        "nondebug_branch_preserves_might_resched": True,
        "rtmutex_call_site_verified": True,
        "remaining_rejected_files": count,
        "rtmutex_object_compiled": False,
        "rt_mutex_runtime_semantics_verified": False,
        "migration_runtime_implemented": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    report = args.report.resolve()
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage35-status.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
