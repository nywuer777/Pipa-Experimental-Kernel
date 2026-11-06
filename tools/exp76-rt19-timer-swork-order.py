#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / E404 RT140 timer-swork early NO_HZ replay / NO FLASH
"""Port early-NO_HZ ordering without changing PREEMPT_RT's sleeping work.

Stage34 already restored the RT140 timer.c reject. This is a separate runtime
sequencing fix: the first tick_nohz_activate() may run before early_initcalls
have constructed glob_worker. Suppress only that premature timer queue, then
replay the sticky tick_nohz_active state once the global sworker exists.

Never change swork_queue(), substitute schedule_work(), or mark PORT_VERIFIED.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

TIMER = "kernel/time/timer.c"
REJECT = "kernel/time/timer.c.rej"
SCHED_SWORK = "kernel/sched/swork.c"
TICK_SCHED = "kernel/time/tick-sched.c"
ORIGINAL_SHA256 = "2c5a9f99c4a3c4bc2fcb5f2d23c6ee6fbf1a20cf061392fe47f3e1b917948bbd"
REJECT_SHA256 = "445c341c5ae29d37e08b9cdfd97aea0c2574961690c7f25dacb9548c226792d7"
WORKER_SHA256 = "101603b79396655c7353db645ad468aabc78fd596962ec0e520e38f373ab3d2c"

DECLARATION = "static struct swork_event timer_update_swork;\n"
NEW_DECLARATION = (
    "static struct swork_event timer_update_swork;\n"
    "/* Tick activation may precede the early initcall that creates kswork. */\n"
    "static bool timer_update_swork_ready;\n"
)
ORIGINAL = """void timers_update_nohz(void)
{
\tswork_queue(&timer_update_swork);
}

static __init int hrtimer_init_thread(void)
{
\tWARN_ON(swork_get());
\tINIT_SWORK(&timer_update_swork, timer_update_keys);
\treturn 0;
}
early_initcall(hrtimer_init_thread);
"""
REPLACEMENT = """void timers_update_nohz(void)
{
\t/*
\t * The first NO_HZ activation can precede early_initcall().
\t * tick_nohz_active is persistent, so replay in hrtimer_init_thread.
\t * Never queue sleeping work before the global worker exists.
\t */
\tif (!smp_load_acquire(&timer_update_swork_ready))
\t\treturn;
\tswork_queue(&timer_update_swork);
}

static __init int hrtimer_init_thread(void)
{
\tint ret;

\tret = swork_get();
\tif (WARN_ON(ret))
\t\treturn ret;
\tINIT_SWORK(&timer_update_swork, timer_update_keys);
\tsmp_store_release(&timer_update_swork_ready, true);

\t/* Retain the first NO_HZ activation that occurred before swork_get. */
\tif (READ_ONCE(tick_nohz_active))
\t\tswork_queue(&timer_update_swork);
\treturn 0;
}
early_initcall(hrtimer_init_thread);
"""


def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def once(text: str, target: str, label: str) -> None:
    count = text.count(target)
    if count != 1:
        raise RuntimeError(f"{label}: expected one {target!r}, found {count}")


def transform(before: str) -> str:
    once(before, DECLARATION, TIMER)
    once(before, ORIGINAL, TIMER)
    if "timer_update_swork_ready" in before:
        raise RuntimeError("Refuse second application")
    after = before.replace(DECLARATION, NEW_DECLARATION, 1)
    after = after.replace(ORIGINAL, REPLACEMENT, 1)
    assert after.count("early_initcall(hrtimer_init_thread);") == 1
    assert after.count("swork_queue(&timer_update_swork);") == 2
    assert after.count("swork_get();") == 1
    assert after.count("smp_store_release(&timer_update_swork_ready, true);") == 1
    assert after.count("smp_load_acquire(&timer_update_swork_ready)") == 1
    return after


def audit_prerequisites(tree: Path) -> dict:
    for required in (TIMER, REJECT, SCHED_SWORK, TICK_SCHED, "include/linux/swork.h"):
        if not (tree / required).is_file():
            raise RuntimeError(f"Missing required RT140 input: {required}")
    original = (tree / TIMER).read_bytes()
    rej = (tree / REJECT).read_bytes()
    sworker = (tree / SCHED_SWORK).read_bytes()
    for blob, expected, name in ((original, ORIGINAL_SHA256, TIMER),
                                  (rej, REJECT_SHA256, REJECT),
                                  (sworker, WORKER_SHA256, SCHED_SWORK)):
        actual = sha256(blob)
        if actual != expected:
            raise RuntimeError(f"{name}: SHA mismatch {actual}, expected {expected}")
    text = original.decode()
    sw = sworker.decode()
    tick = (tree / TICK_SCHED).read_text()
    for mark in ("#include <linux/swork.h>", DECLARATION,
                 "early_initcall(hrtimer_init_thread);", "WARN_ON(swork_get());"):
        once(text, mark, TIMER)
    for mark in ("static struct sworker *glob_worker;", "int swork_get(void)",
                 "raw_spin_lock_irqsave(&glob_worker->lock, flags);"):
        once(sw, mark, SCHED_SWORK)
    for mark in ("void tick_setup_sched_timer(void)", "tick_nohz_activate(ts, NOHZ_MODE_HIGHRES);"):
        once(tick, mark, TICK_SCHED)
    if "test_and_set_bit(0, &tick_nohz_active)" not in tick:
        raise RuntimeError("No sticky NO_HZ activation state to replay")
    if "return (kstrtobool(str, &tick_nohz_enabled) == 0);" not in tick:
        raise RuntimeError("Missing nohz=off control")
    return {"timer_sha256_before":sha256(original), "reject_sha256":sha256(rej),
            "swork_sha256":sha256(sworker), "source_has_rt140_stage34_port":True,
            "direct_rejected_hunk_already_present":True, "rejected_files_preserved":True}


def selftest() -> None:
    base = DECLARATION + "\n" + ORIGINAL
    modified = transform(base)
    assert "if (READ_ONCE(tick_nohz_active))" in modified
    assert modified.index("swork_get();") < modified.index("INIT_SWORK(")
    assert modified.index("INIT_SWORK(") < modified.index("smp_store_release")
    assert modified.index("smp_store_release") < modified.index("if (READ_ONCE(tick_nohz_active))")
    assert "schedule_work(" not in modified
    try:
        transform(modified)
    except RuntimeError as e:
        assert "Refuse second application" in str(e)
    else:
        raise AssertionError("re-application unexpectedly permitted")
    print("EXP76_R19_SWORK_ORDER_SELFTEST=PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--mode", choices=("apply", "verify"), default="verify")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        selftest()
        return
    if not args.tree or not args.report:
        parser.error("--tree and --report are required")
    tree = args.tree.resolve()
    audit = audit_prerequisites(tree)
    before = (tree / TIMER).read_text()
    after = transform(before)
    if args.mode == "apply":
        (tree / TIMER).write_text(after)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    report = {"schema":1,"stage":"EXP76_R19_TIMER_SWORK_INIT_ORDER",
        "mode":args.mode,"applied":args.mode=="apply",
        "source":audit,
        "timer_sha256_after":sha256(after.encode()),
        "change_class":"EARLY_NOHZ_INITCALL_ORDER_WITH_DEFERRED_REPLAY",
        "repaired_reject_hunks_this_round":0,
        "source_reconciled_in_stage34":True,
        "guard_skips_premature_swork_queue":True,
        "swork_queue_implementation_changed":False,
        "swork_get_existing_early_initcall_preserved":True,
        "boot_verified":False,"port_verified":False,
        "rt_handoff_ready":False,"flash_ready":False}
    args.report.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
