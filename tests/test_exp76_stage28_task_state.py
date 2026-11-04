#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage28 task-state regression / NO FLASH
"""Check locked saved_state comparison and reject missing state/lock/RT prerequisites."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "exp76-rt-stage28-task-state.py"
SCHED = (
    "\tvolatile long\t\t\tstate;\n"
    "\tvolatile long\t\t\tsaved_state;\n"
    "\traw_spinlock_t\t\t\tpi_lock;\n"
)
CORE = (
    "int __migrate_disabled(struct task_struct *p)\n"
    "{\n\treturn p->migrate_disable;\n}\n"
    "int core_placeholder(void) { return 0; }\n"
    "/*\n * wait_task_inactive - wait for a thread to unschedule.\n */\n"
    "int example(struct task_struct *p, long match_state) {\n"
    "\tif (match_state && !check_task_state(p, match_state)) return 0;\n"
    "\tif (!match_state || p->state == match_state ||\n"
    "\t\t    p->saved_state == match_state) return 1;\n"
    "\treturn 0;\n}\n"
)


def put(root: Path, path: str, value: str) -> None:
    dest = root / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(value, encoding="utf-8")


def setup(root: Path) -> None:
    put(root, "kernel/sched/core.c", CORE)
    put(root, "include/linux/sched.h", SCHED)
    put(root, "kernel/sched/cpupri.c.rej", "pending\n")
    for n in range(63):
        put(root, f"pending/{n:02d}.rej", "pending\n")


def execute(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--tree", str(root), "--report",
         str(root / "report"), "--mode", "apply"],
        capture_output=True, text=True,
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        good = base / "good"
        setup(good)
        res = execute(good)
        assert res.returncode == 0, res.stderr
        body = (good / "kernel/sched/core.c").read_text()
        assert body.count("static bool check_task_state(") == 1
        assert "raw_spin_lock_irq(&p->pi_lock);" in body
        assert "if (p->state == match_state || p->saved_state == match_state)" in body
        assert body.index("static bool check_task_state(") < body.index("/*\n * wait_task_inactive")
        assert "return p->migrate_disable;" in body
        status = json.loads((good / "report/stage28-status.json").read_text())
        assert status["remaining_rejected_files"] == 64
        assert status["kernel_built"] is False and status["flash_ready"] is False

        no_saved = base / "missing-state"
        setup(no_saved)
        put(no_saved, "include/linux/sched.h", SCHED.replace("\tvolatile long\t\t\tsaved_state;\n", ""))
        assert execute(no_saved).returncode != 0
        assert (no_saved / "kernel/sched/core.c").read_text() == CORE

        no_lock = base / "missing-lock"
        setup(no_lock)
        put(no_lock, "include/linux/sched.h", SCHED.replace("raw_spinlock_t", "spinlock_t"))
        assert execute(no_lock).returncode != 0

        duplicate = base / "duplicate-helper"
        setup(duplicate)
        put(duplicate, "kernel/sched/core.c", "static bool check_task_state(void) { return true; }\n" + CORE)
        assert execute(duplicate).returncode != 0
    print("EXP76_STAGE28_TASK_STATE_TESTS=4_PASS; FLASH_READY=false")


if __name__ == "__main__":
    main()
