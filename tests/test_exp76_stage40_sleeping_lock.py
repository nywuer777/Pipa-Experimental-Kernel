#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage40 sleeping_lock ABI tests / NO FLASH
"""Exercise the rejected RT sleeping_lock field and fork-initialization port."""
from __future__ import annotations

import json
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/exp76-rt-stage40-sleeping-lock.py"
M = runpy.run_path(str(TOOL), run_name="exp76_stage40_fixture")
HEADER = (
    "struct task_struct {\n"
    "int nr_cpus_allowed;\n"
    "cpumask_t cpus_allowed;\n"
    "cpumask_t cpus_requested;\n"
    + M["SCHED_ANCHOR"] + "\n"
    "};\n"
)
CORE = (
    "static void __sched_fork(unsigned long flags, struct task_struct *p)\n"
    "{\n"
    + M["CORE_ANCHOR"] + " = 0;\n"
    "}\n"
)
SOFTIRQ = (
    "static bool softirq_check_runner_tsk(struct task_struct *tsk) {\n"
    "    return tsk->sleeping_lock != 0;\n"
    "}\n"
)


def put(root: Path, name: str, contents: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def seed(root: Path) -> None:
    put(root, M["SCHED"], HEADER)
    put(root, M["CORE"], CORE)
    put(root, M["SOFTIRQ"], SOFTIRQ)
    put(root, M["REJECT"], "diff a/include/linux/sched.h b/include/linux/sched.h\n"
        "@@ -664,7 +672,22 @@ struct task_struct {\n" + M["UPSTREAM"] + "\n")
    put(root, M["CPU_PRI_REJECT"], "pending\n")
    for n in range(62):
        put(root, f"pending/{n:02d}.rej", "pending\n")


def invoke(root: Path, mode: str = "apply") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), "--tree", str(root),
         "--report", str(root / "report"), "--mode", mode],
        capture_output=True, text=True,
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        good = base / "good"
        seed(good)
        check = invoke(good, "verify")
        assert check.returncode == 0, check.stderr
        assert (good / M["SCHED"]).read_text() == HEADER
        assert (good / M["CORE"]).read_text() == CORE

        result = invoke(good)
        assert result.returncode == 0, result.stderr
        sched = (good / M["SCHED"]).read_text()
        core = (good / M["CORE"]).read_text()
        assert sched == HEADER.replace(M["SCHED_ANCHOR"], M["SCHED_REPLACEMENT"])
        assert core == CORE.replace(M["CORE_ANCHOR"], M["CORE_REPLACEMENT"])
        assert "#ifdef CONFIG_PREEMPT_RT_FULL\n\tint\t\t\t\tsleeping_lock;" in sched
        assert "#ifdef CONFIG_PREEMPT_RT_FULL\n\tp->sleeping_lock = 0;" in core
        status = json.loads((good / "report/stage40-status.json").read_text())
        assert status["remaining_rejected_files"] == 64
        assert status["task_field_and_fork_initialization_ported"] is True
        assert status["sleeping_lock_runtime_lifecycle_verified"] is False
        assert status["kernel_built"] is False and status["flash_ready"] is False

        reject_changed = base / "reject-changed"
        seed(reject_changed)
        put(reject_changed, M["REJECT"], "rejected hunk no longer matches\n")
        assert invoke(reject_changed).returncode != 0
        assert (reject_changed / M["SCHED"]).read_text() == HEADER

        no_softirq = base / "missing-reader"
        seed(no_softirq)
        put(no_softirq, M["SOFTIRQ"], "void softirq(void) { }\n")
        assert invoke(no_softirq).returncode != 0

        duplicate = base / "already-initialized"
        seed(duplicate)
        put(duplicate, M["CORE"], CORE + "\tp->sleeping_lock = 0;\n")
        assert invoke(duplicate).returncode != 0

        affinity_changed = base / "vendor-affinity"
        seed(affinity_changed)
        put(affinity_changed, M["SCHED"], HEADER + "cpumask_t cpus_mask;\n")
        assert invoke(affinity_changed).returncode != 0

        missing_field_anchor = base / "missing-task-anchor"
        seed(missing_field_anchor)
        put(missing_field_anchor, M["SCHED"], HEADER.replace(
            "migrate_disable_scheduled;", "migrate_disabled_scheduled;"))
        assert invoke(missing_field_anchor).returncode != 0

        wrong_rejects = base / "missing-reject"
        seed(wrong_rejects)
        (wrong_rejects / "pending/00.rej").unlink()
        assert invoke(wrong_rejects).returncode != 0
    print("EXP76_STAGE40_SLEEPING_LOCK_REGRESSIONS=8_PASS; FLASH_READY=false")


if __name__ == "__main__":
    main()
