#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage27 scheduler mask regression / NO FLASH
"""Exercise exact RT affinity fragment replacement and fail-closed drift."""
from __future__ import annotations

import json
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "exp76-rt-stage27-core-affinity.py"
FRAGMENTS = runpy.run_path(str(SCRIPT), run_name="stage27_fixture")["FRAGMENTS"]


def put(root: Path, rel: str, text: str) -> None:
    dest = root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")


def seed(root: Path) -> tuple[str, str]:
    core = (
        "int __migrate_disabled(struct task_struct *p) {\n"
        "\treturn p->migrate_disable;\n}\n"
        "static bool test_state(struct task_struct *p) {\n"
        "\treturn check_task_state(p, match_state);\n}\n"
    )
    for rt, _, expected in FRAGMENTS:
        core += rt * expected + "\n"
    sched = "\tcpumask_t\t\t\tcpus_allowed;\n\tcpumask_t\t\t\tcpus_requested;\n"
    put(root, "kernel/sched/core.c", core)
    put(root, "include/linux/sched.h", sched)
    put(root, "arch/arm64/kernel/process.c", (
        "int arch_dup_task_struct(struct task_struct *dst, struct task_struct *src)\n"
        "{\n\t*dst = *src;\n\treturn 0;\n}\n"
    ))
    put(root, "kernel/fork.c", "/* Stage26: fork uses vendor embedded affinity mask */\n")
    put(root, "kernel/sched/cpupri.c.rej", "pending\n")
    for i in range(63):
        put(root, f"pending/{i:02d}.rej", "pending\n")
    return core, sched


def execute(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--tree", str(root),
         "--report", str(root / "report"), "--mode", "apply"],
        capture_output=True, text=True,
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        good = base / "good"
        original, sched = seed(good)
        result = execute(good)
        assert result.returncode == 0, result.stderr
        expected = original
        for rt, vendor, count in FRAGMENTS:
            expected = expected.replace(rt, vendor, count)
        assert (good / "kernel/sched/core.c").read_text() == expected
        status = json.loads((good / "report/stage27-status.json").read_text())
        assert status["replaced_rt_affinity_sites"] == 8
        assert status["remaining_rejected_files"] == 64
        assert status["kernel_built"] is False
        assert status["flash_ready"] is False

        missing = base / "missing"
        raw, _ = seed(missing)
        put(missing, "kernel/sched/core.c", raw.replace(FRAGMENTS[0][0], "wrong_signature"))
        assert execute(missing).returncode != 0
        assert (missing / "kernel/sched/core.c").read_text() != expected

        changed_abi = base / "changed_abi"
        seed(changed_abi)
        put(changed_abi, "include/linux/sched.h", sched.replace("cpus_allowed;", "cpus_mask;"))
        assert execute(changed_abi).returncode != 0

        stale_fork = base / "stale_fork"
        seed(stale_fork)
        put(stale_fork, "kernel/fork.c", "orig->cpus_ptr\n")
        assert execute(stale_fork).returncode != 0
    print("EXP76_STAGE27_CORE_AFFINITY_REGRESSION=4_PASS; FLASH_READY=false")


if __name__ == "__main__":
    main()
