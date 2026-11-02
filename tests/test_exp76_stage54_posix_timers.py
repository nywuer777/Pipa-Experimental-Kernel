#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 Actions / EXP76 Stage54 POSIX RT lifetime regressions / NO FLASH
"""Check strict source edits, rejection pins, and rollback on drift."""
from __future__ import annotations
import hashlib
import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT / "tools/exp76-rt-stage54-posix-timers.py"),
                   run_name="stage54_fixture")
prepare, execute = M["prepare"], M["execute"]


def put(root: Path, name: str, body: str) -> Path:
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def fixture(root: Path) -> Path:
    tree = root / "trial"
    (tree / ".git").mkdir(parents=True)
    put(tree, M["HEADER"], "#ifndef POSIX\n" + M["RCU_OLD"] + M["DECL_OLD"])
    put(tree, M["TIMERS"],
        "tmr = container_of(head, struct k_itimer, rcu);\n"
        "call_rcu(&tmr->rcu, k_itimer_rcu_free);\n")
    put(tree, M["CPU"],
        "/* E404+RT */\n" + M["ANCHOR"] + M["ENTRY_OLD"]
        + "expiry_lock = this_cpu_ptr(&cpu_timer_expiry_lock);\n"
        + "void run_posix_cpu_timers(struct task_struct *tsk)\n"
        + "{ __run_posix_cpu_timers(tsk); }\n"
        + "void run_posix_cpu_timers(struct task_struct *tsk)\n"
        + "{ __run_posix_cpu_timers(tsk); }\n")
    put(tree, M["TICK"], "void update_process_times(void) {\n" + M["TICK_OLD"] + "}\n")
    rejects = tree / "kernel/sched"
    rejects.mkdir(parents=True)
    put(tree, "kernel/sched/cpupri.c.rej", "pending\n")
    for n in range(61):
        put(tree, f"kernel/sched/pending-{n:02d}.rej", "pending\n")
    for path in M["REJECTS"]:
        file = put(tree, path, "pinned test fixture\n" + path + "\n")
        M["REJECTS"][path] = hashlib.sha256(file.read_bytes()).hexdigest()
    assert len(list(tree.rglob("*.rej"))) == 64
    return tree


def rejected(fn, fragment: str) -> None:
    try:
        fn()
    except ValueError as ex:
        assert fragment in str(ex), str(ex)
    else:
        raise AssertionError("Expected Stage54 rejection: " + fragment)


def main() -> None:
    assert M["RCU_NEW"] != M["RCU_OLD"]
    assert len(M["EXPIRY"]) > 200
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        src = fixture(root / "happy")
        original = {name: (src / name).read_text() for name in
                    (M["HEADER"], M["CPU"], M["TICK"])}
        a = execute(src, root / "dry-run", "verify")
        assert a["applied"] is False
        assert all((src / name).read_text() == body for name, body in original.items())
        b = execute(src, root / "applied", "apply")
        assert b["applied"] and b["remaining_rejected_files"] == 64
        assert b["runtime_verified"] is False and b["flash_ready"] is False
        assert (src / M["HEADER"]).read_text() == original[M["HEADER"]].replace(
            M["RCU_OLD"], M["RCU_NEW"]).replace(M["DECL_OLD"], M["DECL_NEW"])
        assert M["EXPIRY"] in (src / M["CPU"]).read_text()
        assert M["ENTRY_NEW"] in (src / M["CPU"]).read_text()
        assert (src / M["TICK"]).read_text() == original[M["TICK"]].replace(
            M["TICK_OLD"], M["TICK_NEW"])
        assert json.loads((root / "applied/stage54-status.json").read_text()) == b
        rejected(lambda: prepare(src), "POSIX timer union RCU layout")

        lost_rcu = fixture(root / "union-drift")
        path = lost_rcu / M["HEADER"]
        path.write_text(path.read_text().replace(M["RCU_OLD"], "struct rcu_head rcu;\n"))
        rejected(lambda: prepare(lost_rcu), "POSIX timer union")

        missing_reader = fixture(root / "missing-reader")
        path = missing_reader / M["CPU"]
        path.write_text(path.read_text().replace(
            "expiry_lock = this_cpu_ptr(&cpu_timer_expiry_lock);", "/* missing */"))
        rejected(lambda: prepare(missing_reader), "RT expiry reader")

        missing_worker = fixture(root / "missing-worker")
        path = missing_worker / M["CPU"]
        path.write_text(path.read_text().replace(
            "void run_posix_cpu_timers(struct task_struct *tsk)", "void lost_timer(void)"))
        rejected(lambda: prepare(missing_worker), "two RT/nonRT")

        invalid_rcu = fixture(root / "legacy-rcu")
        path = invalid_rcu / M["TIMERS"]
        path.write_text(path.read_text().replace("tmr->rcu", "tmr->it.rcu"))
        rejected(lambda: prepare(invalid_rcu), "RT POSIX RCU user")

        missing_tick = fixture(root / "tick-drift")
        path = missing_tick / M["TICK"]
        path.write_text(path.read_text().replace("scheduler_tick();", "tick_changed();"))
        rejected(lambda: prepare(missing_tick), "scheduler tick")

        bad_reject = fixture(root / "reject-drift")
        path = bad_reject / (M["HEADER"] + ".rej")
        path.write_text("incorrect rejected hunk")
        rejected(lambda: prepare(bad_reject), "hash mismatch")

        lost_reject = fixture(root / "reject-count")
        (lost_reject / "kernel/sched/pending-00.rej").unlink()
        rejected(lambda: prepare(lost_reject), "64 unresolved")

        no_git = fixture(root / "wrong-tree")
        (no_git / ".git").rmdir()
        rejected(lambda: prepare(no_git), "isolated E404")

        wrong_mode = fixture(root / "wrong-mode")
        rejected(lambda: execute(wrong_mode, root / "bad-mode", "flash"),
                 "Unsupported Stage54 mode")
    print("EXP76_STAGE54_POSIX_TIMER_REGRESSIONS=10_PASS; KERNEL_BUILT=false; FLASH_READY=false")


if __name__ == "__main__":
    main()
