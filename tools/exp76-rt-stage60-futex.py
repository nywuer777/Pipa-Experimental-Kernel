#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage60 E404 futex RT sleeper and requeue hash bucket / NO FLASH
"""Complete two compiler-proven PREEMPT_RT futex contracts on E404.

The upstream RT hrtimer header changed hrtimer_init_sleeper() from two
arguments to four; E404's consolidated futex_setup_timer() retained its
two-argument call. Use the original RT on-stack four-argument constructor.

The RT requeue code refers to hb2, but E404 rejected the single hunk
that adds its declaration. Restore only that local pointer declaration,
preserving the RT requeue synchronization and error paths unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

FUTEX = "kernel/futex.c"
HRTIMER = "include/linux/hrtimer.h"
REJECT = "kernel/futex.c.rej"
REJECT_HASH = "2c00301ce65c3158e68ff0ce3df0b452d29d365016ce05c00a8f28f026d0be0b"
FUNCTION = "static int futex_wait_requeue_pi("
ROBUST = "/*\n * Support for robust futexes:"
TIMER_OLD = (
    "\thrtimer_init_on_stack(&timeout->timer, (flags & FLAGS_CLOCKRT) ?\n"
    "\t\t\t      CLOCK_REALTIME : CLOCK_MONOTONIC,\n"
    "\t\t\t      HRTIMER_MODE_ABS);\n"
    "\thrtimer_init_sleeper(timeout, current);\n"
)
TIMER_NEW = (
    "\thrtimer_init_sleeper_on_stack(timeout, (flags & FLAGS_CLOCKRT) ?\n"
    "\t\t\t\t      CLOCK_REALTIME : CLOCK_MONOTONIC,\n"
    "\t\t\t\t      HRTIMER_MODE_ABS, current);\n"
)
BUCKET_OLD = (
    "\tstruct hrtimer_sleeper timeout, *to;\n"
    "\tstruct rt_mutex_waiter rt_waiter;\n"
    "\tstruct futex_hash_bucket *hb;\n"
    "\tunion futex_key key2 = FUTEX_KEY_INIT;\n"
)
BUCKET_NEW = BUCKET_OLD.replace(
    "\tstruct futex_hash_bucket *hb;\n",
    "\tstruct futex_hash_bucket *hb, *hb2;\n",
)


def one(text: str, snippet: str, label: str) -> None:
    matches = text.count(snippet)
    if matches != 1:
        raise ValueError(f"{label}: expected exactly one pinned fragment, found {matches}")


def prepare(tree: Path) -> tuple[str, dict]:
    if not (tree / ".git").is_dir():
        raise ValueError("Expected isolated E404 git trial tree")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Expected 64 outstanding RT rejects")
    for name in (FUTEX, HRTIMER, REJECT, "kernel/sched/cpupri.c.rej"):
        if not (tree / name).is_file():
            raise ValueError("Missing source or RT reject: " + name)
    reject = (tree / REJECT).read_bytes()
    if hashlib.sha256(reject).hexdigest() != REJECT_HASH:
        raise ValueError("Pinned futex RT reject SHA256 changed")
    if ("-\\tstruct futex_hash_bucket *hb;\n".replace("\\t", "\t")
        not in reject.decode("utf-8")) or (
        "+\tstruct futex_hash_bucket *hb, *hb2;" not in reject.decode("utf-8")
    ):
        raise ValueError("Original RT hb2 rejected hunk missing")

    source = (tree / FUTEX).read_text(encoding="utf-8")
    header = (tree / HRTIMER).read_text(encoding="utf-8")
    one(header,
        "extern void hrtimer_init_sleeper(struct hrtimer_sleeper *sl, clockid_t clock_id,",
        "RT four-argument sleeper declaration")
    if header.count("hrtimer_init_sleeper_on_stack(") != 2:
        raise ValueError("Expected RT DEBUG and nonDEBUG on-stack sleeper constructors")
    if "enum hrtimer_mode mode,\n\t\t\t\t struct task_struct *task);" not in header:
        raise ValueError("Four-argument RT sleeper ABI changed")
    one(source, TIMER_OLD, "E404 consolidated futex sleeper setup")
    one(source, FUNCTION, "E404 futex requeue PI function")
    one(source, ROBUST, "E404 robust futex function boundary")
    start = source.index(FUNCTION)
    end = source.index(ROBUST)
    if start >= end:
        raise ValueError("Futex requeue function boundary drift")
    scope = source[start:end]
    one(scope, BUCKET_OLD, "Rejected hb2 local pointer declaration")
    one(scope, "hb2 = hash_futex(&key2);", "RT requeue second hash bucket")
    one(scope, "rt_mutex_init_waiter(&rt_waiter, false);",
        "RT waiter initialization")
    if scope.count("hb2") < 6:
        raise ValueError("RT second-bucket synchronization unexpectedly absent")
    if "\tstruct futex_hash_bucket *hb, *hb2;\n" in scope:
        raise ValueError("RT hb2 declaration already present")
    fixed = source.replace(TIMER_OLD, TIMER_NEW, 1)
    fixed = fixed[:fixed.index(FUNCTION)] + fixed[fixed.index(FUNCTION):].replace(
        BUCKET_OLD, BUCKET_NEW, 1)
    one(fixed, TIMER_NEW, "Complete RT futex on-stack sleeper initialization")
    one(fixed[fixed.index(FUNCTION):fixed.index(ROBUST)],
        BUCKET_NEW, "Complete RT futex second hash bucket")
    return fixed, {
        "stage": "EXP76_STAGE60_FUTEX_RT_SLEEPER_HB2_NONFLASH",
        "rt_rejected_futex_hunk_sha256_verified": True,
        "futex_timeout_clock_mode_and_task_preserved": True,
        "on_stack_sleeper_4arg_abi_linked": True,
        "hb2_only_declaration_restored": True,
        "rt_pi_waiter_and_requeue_locking_unchanged": True,
        "remaining_rejected_files": 64,
        "runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
        "original_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "patched_sha256": hashlib.sha256(fixed.encode()).hexdigest(),
    }


def execute(tree: Path, report: Path, mode: str) -> dict:
    if mode not in ("verify", "apply"):
        raise ValueError("Stage60 only accepts verify/apply")
    content, status = prepare(tree)
    if mode == "apply":
        (tree / FUTEX).write_text(content, encoding="utf-8")
        if (tree / FUTEX).read_text(encoding="utf-8") != content:
            raise ValueError("Stage60 postwrite verification failed")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage60 changed RT reject evidence")
    status["applied"] = mode == "apply"
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage60-status.json").write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8"
    )
    return status


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = p.parse_args()
    print(json.dumps(execute(args.tree.resolve(), args.report.resolve(), args.mode), indent=2))


if __name__ == "__main__":
    main()
