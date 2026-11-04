#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 Actions / EXP76 Stage57 PREEMPT_RT rwlock contention and NOHZ declaration / NO FLASH
"""Close two exact Kbuild diagnostics without weakening RT synchronization.

E404's zsmalloc tests rwlock_is_contended(&pool->lock), an API already
provided on nonRT via linux/rwlock.h but missing from the RT rwlock header.
Under RT, inspect the rt_mutex waiter red-black tree while holding its
raw wait_lock; preserve the vendor compaction yield predicate unchanged.

The Stage38 softirq port already defines softirq_check_pending_idle() in
both RT and nonRT CONFIG_NO_HZ_COMMON paths. Its public prototype was
omitted, leaving tick-sched.c's upstream RT call undeclared.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

RT_RWLOCK = "include/linux/rwlock_rt.h"
INTERRUPT = "include/linux/interrupt.h"
NONRT_RWLOCK = "include/linux/rwlock.h"
NONRT_RWLOCK_GUARD = (
    "#ifdef arch_rwlock_is_contended\n"
    "#define rwlock_is_contended(lock) \\\n"
    "\t arch_rwlock_is_contended(&(lock)->raw_lock)\n"
    "#else\n"
    "#define rwlock_is_contended(lock)\t((void)(lock), 0)\n"
    "#endif /* arch_rwlock_is_contended */\n"
)
RT_TYPE = "include/linux/rwlock_types_rt.h"
RT_MUTEX = "include/linux/rtmutex.h"
ZS = "mm/zsmalloc.c"
TICK = "kernel/time/tick-sched.c"
SOFTIRQ = "kernel/softirq.c"

RWLOCK_ANCHOR = (
    "void __read_rt_unlock(struct rt_rw_lock *lock);\n"
    "void __write_rt_unlock(struct rt_rw_lock *lock);\n\n"
    "#endif\n"
)
RWLOCK_IMPL = (
    "/* Match rwlock_is_contended() from non-RT rwlock.h for RT zsmalloc. */\n"
    "static inline int rwlock_is_contended(rwlock_t *rwlock)\n"
    "{\n"
    "\tstruct rt_mutex *mutex = &rwlock->rtmutex;\n"
    "\tunsigned long flags;\n"
    "\tint pending;\n\n"
    "\traw_spin_lock_irqsave(&mutex->wait_lock, flags);\n"
    "\tpending = !RB_EMPTY_ROOT(&mutex->waiters.rb_root);\n"
    "\traw_spin_unlock_irqrestore(&mutex->wait_lock, flags);\n"
    "\treturn pending;\n"
    "}\n\n"
)
INTERRUPT_ANCHOR = (
    "extern void raise_softirq_irqoff(unsigned int nr);\n"
    "extern void raise_softirq(unsigned int nr);\n\n"
    "DECLARE_PER_CPU(struct task_struct *, ksoftirqd);\n"
)
INTERRUPT_NEW = INTERRUPT_ANCHOR.replace(
    "\nDECLARE_PER_CPU",
    "\n/* Implemented in softirq.c's RT and non-RT NOHZ branches. */\n"
    "#ifdef CONFIG_NO_HZ_COMMON\n"
    "void softirq_check_pending_idle(void);\n"
    "#endif\n\nDECLARE_PER_CPU",
)


def single(src: str, part: str, what: str) -> None:
    number = src.count(part)
    if number != 1:
        raise ValueError(f"{what}: expected one pinned fragment, found {number}")


def prepare(tree: Path) -> tuple[dict[str, str], dict]:
    if not (tree / ".git").is_dir():
        raise ValueError("Requires isolated E404 trial git checkout")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage57 expected 64 outstanding RT rejects")
    for name in (RT_RWLOCK, INTERRUPT, NONRT_RWLOCK, RT_TYPE, RT_MUTEX,
                 ZS, TICK, SOFTIRQ, "kernel/sched/cpupri.c.rej"):
        if not (tree / name).is_file():
            raise ValueError("Missing pinned E404+RT ABI evidence: " + name)
    files = {name: (tree / name).read_text(encoding="utf-8")
             for name in (RT_RWLOCK, INTERRUPT, NONRT_RWLOCK, RT_TYPE,
                          RT_MUTEX, ZS, TICK, SOFTIRQ)}
    rr, intr = files[RT_RWLOCK], files[INTERRUPT]
    single(rr, RWLOCK_ANCHOR, "RT rwlock tail API")
    if "rwlock_is_contended" in rr:
        raise ValueError("RT rwlock contention helper already defined")
    # E404 legitimately has TWO declarations: arch-specific and generic
    # fallback. Pin the entire #if/#else contract, not an ambiguous token.
    single(files[NONRT_RWLOCK], NONRT_RWLOCK_GUARD,
           "Pinned nonRT rwlock contention branches")
    for name, marker in (
        (RT_TYPE, "typedef struct rt_rw_lock rwlock_t;"),
        (RT_TYPE, "struct rt_mutex\t\trtmutex;"),
        (RT_MUTEX, "struct rb_root_cached   waiters;"),
        (RT_MUTEX, "raw_spinlock_t\t\twait_lock;"),
    ):
        single(files[name], marker, "RT lock ABI " + name)
    single(files[ZS], "rwlock_is_contended(&pool->lock)",
           "Vendor zsmalloc compaction contention test")
    single(files[TICK], "softirq_check_pending_idle();",
           "NOHZ idle softirq audit call")
    if files[SOFTIRQ].count("void softirq_check_pending_idle(void)\n") != 2:
        raise ValueError("Stage38 RT and nonRT NOHZ softirq functions missing")
    if "#ifdef CONFIG_NO_HZ_COMMON" not in files[SOFTIRQ]:
        raise ValueError("Missing Stage38 NOHZ implementation guard")
    single(intr, INTERRUPT_ANCHOR, "Softirq public API declaration anchor")
    if "void softirq_check_pending_idle(void);" in intr:
        raise ValueError("NOHZ softirq prototype already present")
    new = {
        RT_RWLOCK: rr.replace(RWLOCK_ANCHOR, RWLOCK_IMPL + RWLOCK_ANCHOR, 1),
        INTERRUPT: intr.replace(INTERRUPT_ANCHOR, INTERRUPT_NEW, 1),
    }
    single(new[RT_RWLOCK], RWLOCK_IMPL, "RT waiters guarded by raw spinlock")
    single(new[INTERRUPT], INTERRUPT_NEW, "NOHZ public softirq declaration")
    return new, {
        "stage": "EXP76_STAGE57_RT_RWLOCK_CONTENTION_NOHZ_SOFTIRQ_ABI_NONFLASH",
        "rt_rwlock_waiters_checked_under_raw_spinlock": True,
        "vendor_zsmalloc_compaction_condition_preserved": True,
        "nonrt_rwlock_api_preserved": True,
        "rt_and_nonrt_nohz_softirq_implementation_verified": True,
        "nohz_softirq_public_prototype_guarded": True,
        "remaining_rejected_files": 64,
        "runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
        "original_sha256": {name: hashlib.sha256(files[name].encode()).hexdigest()
                            for name in (RT_RWLOCK, INTERRUPT)},
        "patched_sha256": {name: hashlib.sha256(value.encode()).hexdigest()
                           for name, value in new.items()},
    }


def execute(tree: Path, report: Path, mode: str) -> dict:
    if mode not in ("verify", "apply"):
        raise ValueError("Stage57 only permits verify/apply")
    changes, result = prepare(tree)
    if mode == "apply":
        for name, body in changes.items():
            (tree / name).write_text(body, encoding="utf-8")
        for name, body in changes.items():
            if (tree / name).read_text(encoding="utf-8") != body:
                raise ValueError("Stage57 failed postwrite verification")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage57 changed RT reject evidence")
    result["applied"] = mode == "apply"
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage57-status.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = p.parse_args()
    print(json.dumps(execute(args.tree.resolve(), args.report.resolve(), args.mode), indent=2))


if __name__ == "__main__":
    main()
