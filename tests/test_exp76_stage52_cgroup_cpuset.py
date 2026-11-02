#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage52 E404-RT cgroup cpuset regression / NO FLASH
"""Reject ambiguous or drifted RT source; verify only the scoped ABI fixes."""
from __future__ import annotations
import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT / "tools/exp76-rt-stage52-cgroup-cpuset.py"),
                   run_name="exp76_stage52_unit")
prepare, execute = M["prepare"], M["execute"]


def fixture(root: Path) -> Path:
    tree = root / "trial"
    (tree / ".git").mkdir(parents=True)
    blk = tree / M["BLK"]
    blk.parent.mkdir(parents=True)
    blk.write_text(
        "/* E404 blk-cgroup RT patched */\n"
        + M["BLK_ORIGINAL"]
        + "#include <linux/kthread.h>\n"
        + "struct blkcg {\nstruct cgroup_subsys_state\tcss;\n};\n"
        + "return css_to_blkcg(task_css(current, io_cgrp_id));\n",
        encoding="utf-8",
    )
    cpuset = tree / M["CPUSET"]
    cpuset.parent.mkdir(parents=True)
    cpuset.write_text(
        "/* RT patched cpuset */\n" + M["LOCK_DECL"]
        + M["CPU_MASK_OLD"] + M["PARENT_MASK_OLD"] + M["FORK_OLD"]
        + "\traw_spin_lock_irq(&callback_lock);\n"
        + "\traw_spin_unlock_irq(&callback_lock);\n",
        encoding="utf-8",
    )
    rej = tree / "kernel/sched"
    rej.mkdir(parents=True)
    (rej / "cpupri.c.rej").write_text("pending\n")
    for i in range(63):
        (rej / f"pending-{i:02d}.rej").write_text("pending\n")
    return tree


def expect_failure(fn, marker: str) -> None:
    try:
        fn()
    except ValueError as exc:
        assert marker in str(exc), str(exc)
    else:
        raise AssertionError("Expected Stage52 reject: " + marker)


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        tree = fixture(root / "good")
        blk, cpuset = tree / M["BLK"], tree / M["CPUSET"]
        before = {p: p.read_text() for p in (blk, cpuset)}
        status = execute(tree, root / "verify", "verify")
        assert not status["applied"]
        assert all(p.read_text() == before[p] for p in before)
        status = execute(tree, root / "apply", "apply")
        assert status["applied"] and status["remaining_rejected_files"] == 64
        assert "#include <linux/cgroup.h>\n" in blk.read_text()
        assert blk.read_text().count("#include <linux/kthread.h>\n") == 1
        assert M["LEFTOVER"].search(cpuset.read_text()) is None
        assert cpuset.read_text().count("raw_spin_lock_irq(&callback_lock)") == 3
        assert M["FORK_NEW"] in cpuset.read_text()
        assert status["kernel_built"] is False and status["flash_ready"] is False
        assert json.loads((root / "apply/stage52-status.json").read_text()) == status

        no_css = fixture(root / "no-css")
        path = no_css / M["BLK"]
        path.write_text(path.read_text().replace("struct cgroup_subsys_state\tcss;", "int css;"))
        expect_failure(lambda: prepare(no_css), "E404 cgroup CSS field")

        no_task_css = fixture(root / "no-task-css")
        path = no_task_css / M["BLK"]
        path.write_text(path.read_text().replace("task_css(current, io_cgrp_id)", "task_css(current, bad_id)"))
        expect_failure(lambda: prepare(no_task_css), "E404 task_css API")

        double_kthread = fixture(root / "extra-kthread")
        path = double_kthread / M["BLK"]
        path.write_text(path.read_text() + "#include <linux/kthread.h>\n")
        expect_failure(lambda: prepare(double_kthread), "kthread include layout")

        wrong_lock_type = fixture(root / "legacy-lock")
        path = wrong_lock_type / M["CPUSET"]
        path.write_text(path.read_text().replace(M["LOCK_DECL"], "static DEFINE_SPINLOCK(callback_lock);\n"))
        expect_failure(lambda: prepare(wrong_lock_type), "raw spinlock")

        missing_pair = fixture(root / "missing-pair")
        path = missing_pair / M["CPUSET"]
        path.write_text(path.read_text().replace(M["CPU_MASK_OLD"], "/* stripped */\n"))
        expect_failure(lambda: prepare(missing_pair), "Vendor cpus_requested")

        unexpected_pair = fixture(root / "extra-legacy")
        path = unexpected_pair / M["CPUSET"]
        path.write_text(path.read_text() + "\tspin_lock_irq(&callback_lock);\n")
        expect_failure(lambda: prepare(unexpected_pair), "Unexpected unconverted")

        missing_pointer = fixture(root / "missing-cpus-ptr")
        path = missing_pointer / M["CPUSET"]
        path.write_text(path.read_text().replace(M["FORK_OLD"], M["FORK_NEW"]))
        expect_failure(lambda: prepare(missing_pointer), "cpus_ptr incompatible")

        lost_reject = fixture(root / "reject-lost")
        (lost_reject / "kernel/sched/pending-00.rej").unlink()
        expect_failure(lambda: prepare(lost_reject), "64 RT rejects")

        old_git = fixture(root / "no-git")
        (old_git / ".git").rmdir()
        expect_failure(lambda: prepare(old_git), "isolated E404")

        unsupported = fixture(root / "bad-mode")
        expect_failure(lambda: execute(unsupported, root / "flash", "flash"), "Unsupported Stage52 mode")
    print("EXP76_STAGE52_CGROUP_CPUSET_REGRESSIONS=10_PASS; KERNEL_BUILT=false; FLASH_READY=false")


if __name__ == "__main__":
    main()
