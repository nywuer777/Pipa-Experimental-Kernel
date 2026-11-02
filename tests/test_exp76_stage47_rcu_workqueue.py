#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage47 RCU/worker RT rejection regressions / NO FLASH
"""Reject misplaced RCU closers, unexpected conditionals and global lock rewrites."""
from __future__ import annotations

import json
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/exp76-rt-stage47-rcu-workqueue.py"
M = runpy.run_path(str(TOOL), run_name="stage47_fixture")
UPDATE = (
    "#ifdef CONFIG_DEBUG_LOCK_ALLOC\n"
    "static struct lockdep_map rcu_lock_map;\n"
    "#ifdef CONFIG_PREEMPT_RT_FULL\n"
    "int rcu_read_lock_bh_held(void) { return 1; }\n"
    + M["UPDATE_END"] +
    "int rcu_read_lock_any_held(void) { return 1; }\n"
    "#endif /* CONFIG_DEBUG_LOCK_ALLOC */\n"
)
PLUGIN = (
    "#if !defined(CONFIG_RCU_FAST_NO_HZ)\n"
    "int rcu_needs_cpu(u64 basemono, u64 *nextevt)\n"
    "{\n"
    "    *nextevt = KTIME_MAX;\n"
    "    return 0;\n"
    "}\n"
    "#else\n"
    "#ifndef CONFIG_PREEMPT_RT_FULL\n"
    "int rcu_needs_cpu(u64 basemono, u64 *nextevt)\n"
    "{\n"
    "    int dj = 1;\n"
    + M["PLUGIN_END"] +
    " to sense whether nohz is enabled.\n"
    " */\n"
    "static void rcu_prepare_for_idle(void) {}\n"
    "#endif /* CONFIG_RCU_FAST_NO_HZ */\n"
)
WORK = (
    "struct worker_pool {\n"
    "\traw_spinlock_t\t\tlock;\n"
    "};\n"
    "void wq_worker_sleeping(struct task_struct *task)\n"
    "{\n"
    "\tstruct worker *worker;\n"
    "\tstruct worker *next;\n"
    "\tif (worker->flags & WORKER_NOT_RUNNING)\n"
    "\t\treturn;\n"
    + M["WORK_LOCK"] +
    "\tif (!list_empty(&pool->worklist)) {\n"
    "\t\tnext = first_idle_worker(pool);\n"
    + M["WORK_UNLOCK"] +
    "}\n"
    "void unrelated_workqueue_function(void) {\n"
    "\tspin_lock_irq(&pool->lock);\n"
    "\tspin_unlock_irq(&pool->lock);\n"
    "}\n"
)
UPDATE_REJ = (
    "@@ -314,6 +318,7 @@ int rcu_read_lock_bh_held(void)\n"
    " EXPORT_SYMBOL_GPL(rcu_read_lock_bh_held);\n"
    "+#endif\n"
)
PLUGIN_REJ = (
    "@@ -1559,6 +1448,7 @@ int rcu_needs_cpu(u64 basemono, u64 *nextevt)\n"
    "+#endif /* #ifndef CONFIG_PREEMPT_RT_FULL */\n"
)
WORK_REJ = (
    "@@ -888,13 +879,15 @@ void wq_worker_sleeping(struct task_struct *task)\n"
    "+\traw_spin_lock_irq(&pool->lock);\n"
    "+\traw_spin_unlock_irq(&pool->lock);\n"
)


def put(root: Path, path: str, content: str) -> None:
    location = root / path
    location.parent.mkdir(parents=True, exist_ok=True)
    location.write_text(content, encoding="utf-8")


def seed(root: Path) -> None:
    for name, content in (
        (M["UPDATE"], UPDATE),
        (M["PLUGIN"], PLUGIN),
        (M["WORK"], WORK),
        (M["UPDATE_REJ"], UPDATE_REJ),
        (M["PLUGIN_REJ"], PLUGIN_REJ),
        (M["WORK_REJ"], WORK_REJ),
        (M["OTHER_REJ"], "pending\n"),
    ):
        put(root, name, content)
    for index in range(60):
        put(root, f"pending/{index:02d}.rej", "pending\n")


def invoke(root: Path, mode: str = "apply") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), "--tree", str(root),
         "--report", str(root / "report"), "--mode", mode],
        capture_output=True, text=True,
    )


def fail(root: Path, token: str) -> None:
    result = invoke(root)
    assert result.returncode != 0
    assert token in result.stderr, result.stderr
    assert (root / M["UPDATE"]).read_text() != UPDATE.replace(
        M["UPDATE_END"], M["UPDATE_END"] + M["UPDATE_APPEND"])


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        good = base / "good"
        seed(good)
        dry = invoke(good, "verify")
        assert dry.returncode == 0, dry.stderr
        assert (good / M["UPDATE"]).read_text() == UPDATE
        assert (good / M["PLUGIN"]).read_text() == PLUGIN
        assert (good / M["WORK"]).read_text() == WORK
        applied = invoke(good)
        assert applied.returncode == 0, applied.stderr
        update = (good / M["UPDATE"]).read_text()
        plugin = (good / M["PLUGIN"]).read_text()
        work = (good / M["WORK"]).read_text()
        assert M["unclosed"](update, M["UPDATE"]) == []
        assert M["unclosed"](plugin, M["PLUGIN"]) == []
        assert update.count(M["UPDATE_APPEND"]) == 1
        assert plugin.count(M["PLUGIN_INSERT"]) == 1
        assert work.count(M["WORK_LOCK_RT"]) == 1
        assert work.count(M["WORK_UNLOCK_RT"]) == 1
        assert "void unrelated_workqueue_function(void) {\n"
        assert work.endswith(WORK.split("void unrelated_workqueue_function", 1)[1]
                             .join(["void unrelated_workqueue_function", ""]))
        result = json.loads((good / "report/stage47-status.json").read_text())
        assert result["remaining_rejected_files"] == 64
        assert result["rcu_postpatch_preprocessor_balanced"] is True
        assert result["kernel_built"] is False and result["flash_ready"] is False
        assert invoke(good).returncode != 0

        wrong_rcu = base / "additional-update-conditional"
        seed(wrong_rcu)
        put(wrong_rcu, M["UPDATE"], "#if 1\n" + UPDATE)
        fail(wrong_rcu, "unexpected pending conditional")

        wrong_plugin = base / "additional-plugin-conditional"
        seed(wrong_plugin)
        put(wrong_plugin, M["PLUGIN"], "#if 1\n" + PLUGIN)
        fail(wrong_plugin, "unexpected pending conditional")

        wrong_reject = base / "missing-rt-closer"
        seed(wrong_reject)
        put(wrong_reject, M["PLUGIN_REJ"], "no valid upstream rejected closer\n")
        fail(wrong_reject, "expected one")

        wrong_lock = base / "changed-worker-lock"
        seed(wrong_lock)
        put(wrong_lock, M["WORK"], WORK.replace(
            "raw_spinlock_t\t\tlock;", "spinlock_t\t\tlock;"))
        fail(wrong_lock, "does not use raw_spinlock_t")

        changed_source = base / "missing-worker-context"
        seed(changed_source)
        put(changed_source, M["WORK"], WORK.replace(
            "\tworker->sleeping = 1;", "\tworker->sleeping = 0;"))
        fail(changed_source, "expected one")

        wrong_count = base / "missing-rejected-file"
        seed(wrong_count)
        (wrong_count / "pending/00.rej").unlink()
        fail(wrong_count, "64 unresolved RT rejects")

        changed_plugin = base / "missing-rcu-return-context"
        seed(changed_plugin)
        put(changed_plugin, M["PLUGIN"], PLUGIN.replace(
            "\t*nextevt = basemono + dj * TICK_NSEC;",
            "\t*nextevt = KTIME_MAX;"))
        fail(changed_plugin, "expected one")

    print("EXP76_STAGE47_RCU_WORKQUEUE_REGRESSIONS=9_PASS; FLASH_READY=false")


if __name__ == "__main__":
    main()
