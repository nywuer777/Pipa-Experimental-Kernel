#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 GitHub Actions / EXP76 Stage54 RT POSIX timer ABI / NO FLASH
"""Port compiler-proven 4.19.325-rt140 POSIX reject hunks into E404.

Move RCU freeing out of the active timer union, restore the original
per-CPU expiry lock and wait helper, split the internal CPU timer worker
from the RT/nonRT task-argument wrappers, and pass the tick task pointer.
All edits are exact-fragment, source-checked, and non-flashable.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

HEADER = "include/linux/posix-timers.h"
CPU = "kernel/time/posix-cpu-timers.c"
TIMERS = "kernel/time/posix-timers.c"
TICK = "kernel/time/timer.c"
REJECTS = {
    HEADER + ".rej": "eb1c4a42dd58ff9c693c9c37efd1fbc68daebe09b8c7b4004b41f908d291ec08",
    CPU + ".rej": "3f7e605cdefa648198f9a9d578c216d085940c98a9ed5b9748d4c9324aaea932",
}
RCU_OLD = "\t\tstruct rcu_head\t\trcu;\n\t} it;\n};\n"
RCU_NEW = "\t} it;\n\tstruct rcu_head\t\trcu;\n};\n"
DECL_OLD = "void run_posix_cpu_timers(void);\n"
DECL_NEW = "void run_posix_cpu_timers(struct task_struct *task);\n"
ENTRY_OLD = (
    "void run_posix_cpu_timers(void)\n"
    "{\n"
    "\tstruct task_struct *tsk = current;\n"
    "\tstruct k_itimer *timer, *next;\n"
    "\tunsigned long flags;\n"
    "\tLIST_HEAD(firing);\n\n"
    "\tlockdep_assert_irqs_disabled();\n"
)
ENTRY_NEW = (
    "static void __run_posix_cpu_timers(struct task_struct *tsk)\n"
    "{\n"
    "\tstruct k_itimer *timer, *next;\n"
    "\tunsigned long flags;\n"
    "\tspinlock_t *expiry_lock;\n"
    "\tLIST_HEAD(firing);\n\n"
    "\tWARN_ON_ONCE_NONRT(!irqs_disabled());\n"
)
ANCHOR = (
    "/*\n"
    " * This is called from the timer interrupt handler.  The irq handler has\n"
    " * already updated our counts.  We need to check if any timers fire now.\n"
    " * Interrupts are disabled.\n"
    " */\n"
)
EXPIRY = (
    "static DEFINE_PER_CPU(spinlock_t, cpu_timer_expiry_lock) = "
    "__SPIN_LOCK_UNLOCKED(cpu_timer_expiry_lock);\n\n"
    "void cpu_timers_grab_expiry_lock(struct k_itimer *timer)\n"
    "{\n"
    "\tint cpu = timer->it.cpu.firing_cpu;\n\n"
    "\tif (cpu >= 0) {\n"
    "\t\tspinlock_t *expiry_lock = per_cpu_ptr(&cpu_timer_expiry_lock, cpu);\n\n"
    "\t\tspin_lock_irq(expiry_lock);\n"
    "\t\tspin_unlock_irq(expiry_lock);\n"
    "\t}\n"
    "}\n\n"
)
TICK_OLD = (
    "\tscheduler_tick();\n"
    "\tif (IS_ENABLED(CONFIG_POSIX_TIMERS))\n"
    "\t\trun_posix_cpu_timers();\n"
)
TICK_NEW = TICK_OLD.replace("run_posix_cpu_timers();", "run_posix_cpu_timers(p);")


def unique(src: str, fragment: str, label: str) -> None:
    n = src.count(fragment)
    if n != 1:
        raise ValueError(f"{label}: expected one exact match, got {n}")


def prepare(tree: Path) -> tuple[dict[str, str], dict]:
    if not (tree / ".git").is_dir():
        raise ValueError("Expected isolated E404 git checkout")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Expected 64 unresolved RT reject files")
    for name, expected in REJECTS.items():
        file = tree / name
        if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != expected:
            raise ValueError("Pinned POSIX RT reject hash mismatch: " + name)
    originals = {}
    for name in (HEADER, CPU, TIMERS, TICK):
        path = tree / name
        if not path.is_file():
            raise ValueError("Missing E404 POSIX source: " + name)
        originals[name] = path.read_text(encoding="utf-8")
    h, c, t, k = (originals[x] for x in (HEADER, CPU, TIMERS, TICK))
    unique(h, RCU_OLD, "POSIX timer union RCU layout")
    unique(h, DECL_OLD, "E404 CPU timer declaration")
    unique(c, ENTRY_OLD, "E404 CPU timer worker")
    unique(c, ANCHOR, "POSIX CPU timer expiry insertion")
    unique(c, "expiry_lock = this_cpu_ptr(&cpu_timer_expiry_lock);",
           "Already-applied RT expiry reader")
    if c.count("void run_posix_cpu_timers(struct task_struct *tsk)\n") != 2:
        raise ValueError("Expected original two RT/nonRT CPU timer wrappers")
    if c.count("__run_posix_cpu_timers(tsk);") != 2:
        raise ValueError("Expected original two RT/nonRT internal worker calls")
    if "void cpu_timers_grab_expiry_lock(struct k_itimer *timer)\n" in c:
        raise ValueError("RT expiry helper already defined")
    for item in ("container_of(head, struct k_itimer, rcu)",
                 "call_rcu(&tmr->rcu, k_itimer_rcu_free)"):
        unique(t, item, "RT POSIX RCU user")
    if "it.rcu" in t:
        raise ValueError("Legacy POSIX union RCU consumer remains")
    unique(k, TICK_OLD, "E404 scheduler tick timer call")
    changes = {
        HEADER: h.replace(RCU_OLD, RCU_NEW, 1).replace(DECL_OLD, DECL_NEW, 1),
        CPU: c.replace(ANCHOR, EXPIRY + ANCHOR, 1).replace(ENTRY_OLD, ENTRY_NEW, 1),
        TICK: k.replace(TICK_OLD, TICK_NEW, 1),
    }
    after_cpu = changes[CPU]
    if "void run_posix_cpu_timers(void)" in after_cpu or (
        after_cpu.count("void run_posix_cpu_timers(struct task_struct *tsk)\n") != 2
    ) or after_cpu.count("static void __run_posix_cpu_timers(") != 1:
        raise ValueError("Unreconciled POSIX timer entry points")
    if "WARN_ON_ONCE_NONRT(!irqs_disabled());" not in after_cpu:
        raise ValueError("RT worker IRQ-context assertion not reconciled")
    return changes, {
        "stage": "EXP76_STAGE54_POSIX_RCU_CPU_TIMER_EXPIRY_NONFLASH",
        "rt_rejected_hunks_sha256_verified": True,
        "timer_rcu_head_out_of_union": True,
        "per_cpu_expiry_lock_defined": True,
        "posix_timer_lifetime_wait_helper_defined": True,
        "rt_nonrt_worker_dispatch_preserved": True,
        "e404_timer_tick_task_argument_linked": True,
        "remaining_rejected_files": 64,
        "runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
        "original_sha256": {
            name: hashlib.sha256(body.encode()).hexdigest()
            for name, body in originals.items() if name != TIMERS
        },
    }


def execute(tree: Path, report: Path, mode: str) -> dict:
    if mode not in ("verify", "apply"):
        raise ValueError("Unsupported Stage54 mode")
    edits, status = prepare(tree)
    if mode == "apply":
        for name, body in edits.items():
            (tree / name).write_text(body, encoding="utf-8")
        if any((tree / name).read_text(encoding="utf-8") != body
               for name, body in edits.items()):
            raise ValueError("Stage54 source write verification failed")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage54 RT reject evidence changed")
    status["applied"] = mode == "apply"
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage54-status.json").write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8"
    )
    return status


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = p.parse_args()
    print(json.dumps(execute(args.tree.resolve(), args.report.resolve(), args.mode), indent=2))


if __name__ == "__main__":
    main()
