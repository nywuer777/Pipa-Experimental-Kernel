#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage28 RT task-state helper port / NO FLASH
"""Restore the RT check_task_state helper omitted by partial E404 patch application.

The helper matches PREEMPT_RT's locked two-state check; unlike an unlocked
test, it covers both task->state and task->saved_state under pi_lock.
This repairs only the compiler's implicit-declaration error; migration
disable, sleeping locks, and full PREEMPT_RT remain explicitly incomplete.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

CORE = "kernel/sched/core.c"
SCHED = "include/linux/sched.h"
REJECT = "kernel/sched/cpupri.c.rej"
ANCHOR = "/*\n * wait_task_inactive - wait for a thread to unschedule.\n"
CALL = "if (match_state && !check_task_state(p, match_state))"
LOCKED_STATE = "if (!match_state || p->state == match_state ||\n\t\t    p->saved_state == match_state)"
HELPER = """static bool check_task_state(struct task_struct *p, long match_state)
{
	bool match = false;

	raw_spin_lock_irq(&p->pi_lock);
	if (p->state == match_state || p->saved_state == match_state)
		match = true;
	raw_spin_unlock_irq(&p->pi_lock);

	return match;
}

"""


def exactly(source: str, fragment: str, expected: int, where: str) -> None:
    count = source.count(fragment)
    if count != expected:
        raise ValueError(f"{where}: expected {expected} {fragment!r}, found {count}")


def prepare(tree: Path) -> str:
    for relative in (CORE, SCHED, REJECT):
        if not (tree / relative).is_file():
            raise ValueError("Stage27 input missing: " + relative)
    rejects = len(list(tree.rglob("*.rej")))
    if rejects != 64:
        raise ValueError(f"Stage28 requires 64 existing RT rejects; found {rejects}")

    sched = (tree / SCHED).read_text(encoding="utf-8")
    exactly(sched, "\tvolatile long\t\t\tsaved_state;", 1, SCHED)
    exactly(sched, "\tvolatile long\t\t\tstate;", 1, SCHED)
    exactly(sched, "\traw_spinlock_t\t\t\tpi_lock;", 1, SCHED)

    core = (tree / CORE).read_text(encoding="utf-8")
    exactly(core, ANCHOR, 1, CORE)
    exactly(core, CALL, 1, CORE)
    exactly(core, LOCKED_STATE, 1, CORE)
    exactly(core, "int __migrate_disabled(struct task_struct *p)", 1, CORE)
    if "static bool check_task_state(" in core:
        raise ValueError("check_task_state implementation already exists; refuse duplicate")
    if "return p->migrate_disable;" not in core:
        raise ValueError("RT migrate_disable unresolved ABI changed; re-audit")
    return core.replace(ANCHOR, HELPER + ANCHOR, 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--mode", required=True, choices=("verify", "apply"))
    args = parser.parse_args()
    root = args.tree.resolve()
    new_core = prepare(root)
    if args.mode == "apply":
        (root / CORE).write_text(new_core, encoding="utf-8")
    rejects = len(list(root.rglob("*.rej")))
    if rejects != 64:
        raise ValueError("Reject count changed unexpectedly")

    data = {
        "stage": "EXP76_STAGE28_RT_TASK_STATE_LOCKED_HELPER_RESTORED",
        "applied": args.mode == "apply",
        "saved_state_verified": True,
        "task_pi_lock_verified": True,
        "check_task_state_uses_raw_spin_lock_irq": True,
        "remaining_rejected_files": rejects,
        "migrate_disable_runtime_abi_pending": True,
        "sleeping_lock_lifecycle_pending": True,
        "scheduler_core_object_compiled": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    report = args.report.resolve()
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage28-status.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
