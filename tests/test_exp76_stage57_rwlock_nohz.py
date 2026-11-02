#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 Actions / EXP76 Stage57 RT rwlock and NOHZ regressions / NO FLASH
"""Test exact RT lock and softirq interface integration, reject source drift."""
from __future__ import annotations
import json
import runpy
import tempfile
from pathlib import Path

M = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "tools/exp76-rt-stage57-rwlock-nohz.py"),
    run_name="exp76_stage57_tests")
prepare, execute = M["prepare"], M["execute"]


def put(root: Path, name: str, value: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    return path


def fixture(root: Path) -> Path:
    tree = root / "trial"
    (tree / ".git").mkdir(parents=True)
    put(tree, M["RT_RWLOCK"], "/* RT lock E404 */\n" + M["RWLOCK_ANCHOR"])
    put(tree, M["INTERRUPT"], "/* softirq public declarations */\n"
        + M["INTERRUPT_ANCHOR"])
    put(tree, M["NONRT_RWLOCK"], M["NONRT_RWLOCK_GUARD"])
    put(tree, M["RT_TYPE"],
        "typedef struct rt_rw_lock rwlock_t;\n"
        "struct rt_rw_lock {\n\tstruct rt_mutex\t\trtmutex;\n};\n")
    put(tree, M["RT_MUTEX"],
        "struct rt_mutex {\n\traw_spinlock_t\t\twait_lock;\n"
        "\tstruct rb_root_cached   waiters;\n};\n")
    put(tree, M["ZS"], "/* preserved compaction */\n"
        "if (rwlock_is_contended(&pool->lock)) { cond_resched(); }\n")
    put(tree, M["TICK"], "if (local_softirq_pending()) {\n"
        "\tsoftirq_check_pending_idle();\n}\n")
    put(tree, M["SOFTIRQ"], "#ifdef CONFIG_NO_HZ_COMMON\n"
        "#ifdef CONFIG_PREEMPT_RT_FULL\n"
        "void softirq_check_pending_idle(void)\n{ }\n#else\n"
        "void softirq_check_pending_idle(void)\n{ }\n#endif\n#endif\n")
    put(tree, "kernel/sched/cpupri.c.rej", "outstanding\n")
    for k in range(63):
        put(tree, f"rejects/r-{k:02d}.rej", "outstanding\n")
    return tree


def should_fail(fn, expected: str) -> None:
    try:
        fn()
    except ValueError as exc:
        assert expected in str(exc), str(exc)
    else:
        raise AssertionError("Expected fail-closed Stage57 error: " + expected)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        tree = fixture(base / "okay")
        before = {name: (tree / name).read_text() for name in
                  (M["RT_RWLOCK"], M["INTERRUPT"])}
        info = execute(tree, base / "verify", "verify")
        assert info["applied"] is False
        assert all((tree / name).read_text() == before[name] for name in before)
        info = execute(tree, base / "apply", "apply")
        assert info["applied"] is True and info["remaining_rejected_files"] == 64
        assert (tree / M["RT_RWLOCK"]).read_text() == before[M["RT_RWLOCK"]].replace(
            M["RWLOCK_ANCHOR"], M["RWLOCK_IMPL"] + M["RWLOCK_ANCHOR"])
        assert (tree / M["INTERRUPT"]).read_text() == before[M["INTERRUPT"]].replace(
            M["INTERRUPT_ANCHOR"], M["INTERRUPT_NEW"])
        assert info["kernel_built"] is False and info["flash_ready"] is False
        assert json.loads((base / "apply/stage57-status.json").read_text()) == info
        should_fail(lambda: prepare(tree), "already defined")

        no_rt_wait = fixture(base / "missing-lock")
        (no_rt_wait / M["RT_MUTEX"]).write_text("struct rt_mutex { int waiters; };\n")
        should_fail(lambda: prepare(no_rt_wait), "RT lock ABI")

        missing_zs = fixture(base / "missing-zs")
        (missing_zs / M["ZS"]).write_text("/* vendor predicate removed */\n")
        should_fail(lambda: prepare(missing_zs), "Vendor zsmalloc")

        missing_rt = fixture(base / "missing-rt")
        (missing_rt / M["SOFTIRQ"]).write_text(
            "#ifdef CONFIG_NO_HZ_COMMON\n"
            "void softirq_check_pending_idle(void)\n{ }\n#endif\n")
        should_fail(lambda: prepare(missing_rt), "RT and nonRT")

        missing_tick = fixture(base / "missing-tick")
        (missing_tick / M["TICK"]).write_text("/* no NOHZ call */\n")
        should_fail(lambda: prepare(missing_tick), "NOHZ idle")

        missing_nonrt = fixture(base / "missing-nonrt")
        (missing_nonrt / M["NONRT_RWLOCK"]).write_text("/* removed API */\n")
        should_fail(lambda: prepare(missing_nonrt), "nonRT rwlock")

        missing_branch = fixture(base / "missing-arch-branch")
        (missing_branch / M["NONRT_RWLOCK"]).write_text(
            "#define rwlock_is_contended(lock) ((void)(lock), 0)\n")
        should_fail(lambda: prepare(missing_branch), "nonRT rwlock")

        wrong_fallback = fixture(base / "wrong-fallback")
        p = wrong_fallback / M["NONRT_RWLOCK"]
        p.write_text(p.read_text().replace("((void)(lock), 0)", "(1)"))
        should_fail(lambda: prepare(wrong_fallback), "nonRT rwlock")

        bad_int = fixture(base / "missing-anchor")
        (bad_int / M["INTERRUPT"]).write_text("/* missing declarations */\n")
        should_fail(lambda: prepare(bad_int), "Softirq public")

        bad_rt = fixture(base / "changed-rt-type")
        (bad_rt / M["RT_TYPE"]).write_text("struct rt_rw_lock { int other; };\n")
        should_fail(lambda: prepare(bad_rt), "RT lock ABI")

        lost_reject = fixture(base / "lost-reject")
        (lost_reject / "rejects/r-00.rej").unlink()
        should_fail(lambda: prepare(lost_reject), "64 outstanding")

        missing_git = fixture(base / "lost-git")
        (missing_git / ".git").rmdir()
        should_fail(lambda: prepare(missing_git), "isolated E404")

        bad_mode = fixture(base / "bad-mode")
        should_fail(lambda: execute(bad_mode, base / "bad", "flash"),
                    "only permits verify/apply")
    print("EXP76_STAGE57_RWLOCK_NOHZ_REGRESSIONS=12_PASS; KERNEL_BUILT=false; FLASH_READY=false")


if __name__ == "__main__":
    main()
