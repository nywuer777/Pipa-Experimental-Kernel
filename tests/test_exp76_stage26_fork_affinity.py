#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage26 ARM64 affinity regression / NO FLASH
"""Exercise by-value fork mask port and fail-closed source drift checks."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "exp76-rt-stage26-fork-affinity.py"
SCHED = "\tcpumask_t\t\t\tcpus_allowed;\n\tcpumask_t\t\t\tcpus_requested;\n"
ARM = (
    "int arch_dup_task_struct(struct task_struct *dst, struct task_struct *src)\n"
    "{\n\t*dst = *src;\n\treturn 0;\n}\n"
)
FORK = (
    "static struct task_struct *dup_task_struct(struct task_struct *orig, int node)\n"
    "{\n"
    "\terr = arch_dup_task_struct(tsk, orig);\n"
    "#ifdef CONFIG_STACKPROTECTOR\n"
    "\ttsk->stack_canary = get_random_canary();\n"
    "#endif\n"
    "\tif (orig->cpus_ptr == &orig->cpus_mask)\n"
    "\t\ttsk->cpus_ptr = &tsk->cpus_mask;\n"
    "\ttsk->wake_q_sleeper.next = NULL;\n"
    "}\n"
)


def write(root: Path, rel: str, content: str) -> None:
    dest = root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")


def setup(root: Path) -> None:
    write(root, "include/linux/sched.h", SCHED)
    write(root, "arch/arm64/kernel/process.c", ARM)
    write(root, "kernel/fork.c", FORK)
    write(root, "kernel/sched/cpupri.c.rej", "pending")
    for i in range(63):
        write(root, f"unresolved/r{i:02d}.rej", "pending")


def run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--tree", str(root),
         "--report", str(root / "report"), "--mode", "apply"],
        capture_output=True, text=True,
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        good = base / "good"
        setup(good)
        result = run(good)
        assert result.returncode == 0, result.stderr
        source = (good / "kernel/fork.c").read_text()
        assert "cpus_ptr" not in source
        assert "tsk->wake_q_sleeper.next = NULL;" in source
        assert source == FORK.replace(
            "\tif (orig->cpus_ptr == &orig->cpus_mask)\n"
            "\t\ttsk->cpus_ptr = &tsk->cpus_mask;\n", "", 1
        )
        status = json.loads((good / "report/stage26-status.json").read_text())
        assert status["remaining_rejected_files"] == 64
        assert status["arm64_task_copy_by_value_verified"] is True
        assert status["flash_ready"] is False

        drift = base / "drift"
        setup(drift)
        write(drift, "arch/arm64/kernel/process.c", ARM.replace("*dst = *src;", "copy_task(dst, src);"))
        bad = run(drift)
        assert bad.returncode != 0
        assert (drift / "kernel/fork.c").read_text() == FORK

        altered = base / "altered"
        setup(altered)
        write(altered, "include/linux/sched.h", SCHED.replace("cpus_allowed;", "cpus_mask;"))
        bad = run(altered)
        assert bad.returncode != 0
        assert (altered / "kernel/fork.c").read_text() == FORK

    print("EXP76_STAGE26_FORK_AFFINITY_REGRESSIONS=3_PASS; FLASH_READY=false")


if __name__ == "__main__":
    main()
