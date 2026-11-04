#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage29 task migration ABI regression / NO FLASH
"""Verify guarded RT fields, task-fork initialization and vendor ABI preservation."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "exp76-rt-stage29-migration-abi.py"
SCHED = (
    "\tint\t\t\t\tnr_cpus_allowed;\n"
    "\tcpumask_t\t\t\tcpus_allowed;\n"
    "\tcpumask_t\t\t\tcpus_requested;\n"
)
CORE = (
    "int __migrate_disabled(struct task_struct *p)\n"
    "{\n\treturn p->migrate_disable;\n}\n"
    "static void __sched_fork(unsigned long clone_flags, struct task_struct *p)\n"
    "{\n\tp->on_rq\t\t\t= 0;\n}\n"
)
REJ = (
    "diff a/include/linux/sched.h b/include/linux/sched.h (rejected hunks)\n"
    "@@ -664,7 +672,22 @@ struct task_struct {\n"
    "+#if defined(CONFIG_SMP) && defined(CONFIG_PREEMPT_RT_BASE)\n"
    "+\tint\t\t\t\tmigrate_disable;\n"
    "+\tbool\t\t\t\tmigrate_disable_scheduled;\n"
    "+# ifdef CONFIG_SCHED_DEBUG\n"
    "+\tint\t\t\t\tpinned_on_cpu;\n"
    "+# endif\n"
    "+#endif\n"
)


def put(root: Path, path: str, value: str) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(value, encoding="utf-8")


def tree(root: Path) -> None:
    put(root, "include/linux/sched.h", SCHED)
    put(root, "kernel/sched/core.c", CORE)
    put(root, "include/linux/sched.h.rej", REJ)
    put(root, "kernel/sched/cpupri.c.rej", "pending\n")
    for i in range(62):
        put(root, f"pending/{i:02d}.rej", "pending\n")


def run(root: Path, mode: str = "apply") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--tree", str(root), "--report",
         str(root / "report"), "--mode", mode],
        capture_output=True, text=True,
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        good = root / "good"
        tree(good)
        verified = run(good, "verify")
        assert verified.returncode == 0, verified.stderr
        assert (good / "include/linux/sched.h").read_text() == SCHED
        assert (good / "kernel/sched/core.c").read_text() == CORE

        result = run(good)
        assert result.returncode == 0, result.stderr
        sched = (good / "include/linux/sched.h").read_text()
        core = (good / "kernel/sched/core.c").read_text()
        assert SCHED in sched
        assert sched.count("int\t\t\t\tmigrate_disable;") == 1
        assert "bool\t\t\t\tmigrate_disable_scheduled;" in sched
        assert "#if defined(CONFIG_SMP) && defined(CONFIG_PREEMPT_RT_BASE)" in sched
        assert "p->migrate_disable = 0;" in core
        assert "p->migrate_disable_scheduled = false;" in core
        assert "p->pinned_on_cpu = -1;" in core
        assert core.index("p->migrate_disable = 0;") < core.index("p->on_rq")
        report = json.loads((good / "report/stage29-status.json").read_text())
        assert report["remaining_rejected_files"] == 64
        assert report["migration_disable_enable_runtime_implemented"] is False
        assert report["kernel_built"] is False and report["flash_ready"] is False

        duplicated = root / "duplicated"
        tree(duplicated)
        put(duplicated, "include/linux/sched.h", SCHED + "int migrate_disable;\n")
        assert run(duplicated).returncode != 0
        assert (duplicated / "kernel/sched/core.c").read_text() == CORE

        incomplete = root / "missing-hunk"
        tree(incomplete)
        put(incomplete, "include/linux/sched.h.rej", REJ.replace("migrate_disable_scheduled;", "migrate_disable_pending;"))
        assert run(incomplete).returncode != 0

        wrong_abi = root / "wrong-abi"
        tree(wrong_abi)
        put(wrong_abi, "include/linux/sched.h", SCHED.replace("cpus_allowed;", "cpus_mask;"))
        assert run(wrong_abi).returncode != 0

        no_init = root / "no-init"
        tree(no_init)
        put(no_init, "kernel/sched/core.c", CORE.replace("__sched_fork", "__custom_sched_fork"))
        assert run(no_init).returncode != 0

    print("EXP76_STAGE29_RT_MIGRATION_ABI_TESTS=6_PASS; FLASH_READY=false")


if __name__ == "__main__":
    main()
