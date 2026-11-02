#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage60 futex ABI and RT hunk regressions / NO FLASH
"""Verify exact E404 futex RT repair and fail-closed mismatch handling."""
from __future__ import annotations

import hashlib
import json
import runpy
import tempfile
from pathlib import Path

M = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "tools/exp76-rt-stage60-futex.py"),
    run_name="exp76_stage60_unit",
)
prepare, execute = M["prepare"], M["execute"]


def put(root: Path, path: str, content: str) -> Path:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def fixture(root: Path) -> Path:
    trial = root / "source"
    (trial / ".git").mkdir(parents=True)
    put(trial, M["FUTEX"],
        "/* E404+RT futex */\n"
        "static inline struct hrtimer_sleeper *futex_setup_timer(void)\n"
        "{\n" + M["TIMER_OLD"] + "return timeout;\n}\n"
        + M["FUNCTION"] + "void)\n{\n" + M["BUCKET_OLD"]
        + "\trt_mutex_init_waiter(&rt_waiter, false);\n"
        + "\thb2 = hash_futex(&key2);\n"
        + "\tspin_lock(&hb2->lock);\n"
        + "\tBUG_ON(&hb2->lock != q.lock_ptr);\n"
        + "\tspin_unlock(&hb2->lock);\n"
        + "\tspin_lock(&hb2->lock);\n"
        + "\tBUG_ON(&hb2->lock != q.lock_ptr);\n"
        + "\tspin_unlock(&hb2->lock);\n"
        + "}\n\n" + M["ROBUST"] + "\n")
    put(trial, M["HRTIMER"],
        "extern void hrtimer_init_sleeper(struct hrtimer_sleeper *sl, clockid_t clock_id,\n"
        "\t\t\t\t enum hrtimer_mode mode,\n"
        "\t\t\t\t struct task_struct *task);\n"
        "extern void hrtimer_init_sleeper_on_stack("
        "struct hrtimer_sleeper *sl, clockid_t clock_id,\n"
        " enum hrtimer_mode mode, struct task_struct *task);\n"
        "static inline void hrtimer_init_sleeper_on_stack("
        "struct hrtimer_sleeper *sl, clockid_t clock_id,\n"
        " enum hrtimer_mode mode, struct task_struct *task) { }\n")
    rej = (
        "diff a/kernel/futex.c b/kernel/futex.c\n"
        "@@ rejected @@\n"
        "-\tstruct futex_hash_bucket *hb;\n"
        "+\tstruct futex_hash_bucket *hb, *hb2;\n"
    )
    put(trial, M["REJECT"], rej)
    M["REJECT_HASH"] = hashlib.sha256(rej.encode()).hexdigest()
    put(trial, "kernel/sched/cpupri.c.rej", "outstanding\n")
    for i in range(62):
        put(trial, f"rejects/pending-{i:02d}.rej", "unresolved\n")
    assert len(list(trial.rglob("*.rej"))) == 64
    return trial


def failure(fn, marker: str) -> None:
    try:
        fn()
    except ValueError as e:
        assert marker in str(e), str(e)
    else:
        raise AssertionError("Expected Stage60 reject " + marker)


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        trial = fixture(root / "correct")
        first = (trial / M["FUTEX"]).read_text()
        dry = execute(trial, root / "dry", "verify")
        assert not dry["applied"] and (trial / M["FUTEX"]).read_text() == first
        applied = execute(trial, root / "apply", "apply")
        assert applied["applied"] and applied["remaining_rejected_files"] == 64
        assert not applied["kernel_built"] and not applied["flash_ready"]
        assert (trial / M["FUTEX"]).read_text() == (
            first.replace(M["TIMER_OLD"], M["TIMER_NEW"], 1)
            .replace(M["BUCKET_OLD"], M["BUCKET_NEW"], 1)
        )
        assert json.loads((root / "apply/stage60-status.json").read_text()) == applied
        failure(lambda: prepare(trial), "E404 consolidated futex")

        missing_clock = fixture(root / "clock-drift")
        p = missing_clock / M["FUTEX"]
        p.write_text(p.read_text().replace("FLAGS_CLOCKRT", "FLAGS_BAD"))
        failure(lambda: prepare(missing_clock), "E404 consolidated futex")

        missing_hb = fixture(root / "hb-drift")
        p = missing_hb / M["FUTEX"]
        p.write_text(p.read_text().replace(M["BUCKET_OLD"], "/* no bucket */\n"))
        failure(lambda: prepare(missing_hb), "Rejected hb2")

        missing_waiter = fixture(root / "waiter-drift")
        p = missing_waiter / M["FUTEX"]
        p.write_text(p.read_text().replace("rt_mutex_init_waiter(&rt_waiter, false);",
                                             "rt_mutex_init_waiter(&rt_waiter);"))
        failure(lambda: prepare(missing_waiter), "RT waiter")

        missing_hash = fixture(root / "hash-drift")
        p = missing_hash / M["FUTEX"]
        p.write_text(p.read_text().replace("hb2 = hash_futex(&key2);",
                                             "hb2 = hash_futex(&key1);"))
        failure(lambda: prepare(missing_hash), "second hash")

        missing_header = fixture(root / "header-drift")
        p = missing_header / M["HRTIMER"]
        p.write_text(p.read_text().replace("clockid_t clock_id,", "clockid_t ignored,"))
        failure(lambda: prepare(missing_header), "four-argument")

        wrong_constructor = fixture(root / "no-constructor")
        p = wrong_constructor / M["HRTIMER"]
        p.write_text(p.read_text().replace("hrtimer_init_sleeper_on_stack(",
                                            "hrtimer_init_sleeper_stack("))
        failure(lambda: prepare(wrong_constructor), "on-stack sleeper")

        wrong_reject = fixture(root / "bad-reject")
        p = wrong_reject / M["REJECT"]
        p.write_text(p.read_text() + "# corrupted\n")
        failure(lambda: prepare(wrong_reject), "SHA256")

        missing_reject = fixture(root / "rejects-count")
        (missing_reject / "rejects/pending-00.rej").unlink()
        failure(lambda: prepare(missing_reject), "64 outstanding")

        no_git = fixture(root / "git-absent")
        (no_git / ".git").rmdir()
        failure(lambda: prepare(no_git), "isolated E404")

        bad_mode = fixture(root / "wrong-mode")
        failure(lambda: execute(bad_mode, root / "bad", "flash"),
                "only accepts verify/apply")
    print("EXP76_STAGE60_FUTEX_RT_REGRESSIONS=10_PASS; KERNEL_BUILT=false; FLASH_READY=false")


if __name__ == "__main__":
    main()
