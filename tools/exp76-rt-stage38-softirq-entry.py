#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage38 RT softirq rejected entry guards / NO FLASH
"""Restore early PREEMPT_RT softirq helpers and branch structure from .rej.

Do not suppress compiler errors or synthesize no-op softirq implementations.
The rejected sections supply RT runner/NOHZ handling, ktimer wakeup, vector
execution, non-RT dispatch and the missing #ifndef for the partial RT #else.
Remaining softirq rejects must still be ported and runtime-tested separately.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SOFTIRQ = "kernel/softirq.c"
REJECT = "kernel/softirq.c.rej"
PENDING = "kernel/sched/cpupri.c.rej"
NAME_ANCHOR = (
    'const char * const softirq_to_name[NR_SOFTIRQS] = {\n'
    '\t"HI", "TIMER", "NET_TX", "NET_RX", "BLOCK", "IRQ_POLL",\n'
    '\t"TASKLET", "SCHED", "HRTIMER", "RCU"\n'
    '};\n'
)
KSOFTIRQD_ANCHOR = "DEFINE_PER_CPU(struct task_struct *, ksoftirqd);\n"
WAKE_ANCHOR = (
    "static void wakeup_softirqd(void)\n"
    "{\n"
    "\t/* Interrupts are disabled: no need to stop preemption */\n"
    "\tstruct task_struct *tsk = __this_cpu_read(ksoftirqd);\n\n"
    "\tif (tsk)\n"
    "\t\twake_up_process(tsk);\n"
    "}\n"
)
RT_ELSE = "#else /* !PREEMPT_RT_FULL */"


def exactly_once(body: str, part: str, label: str) -> None:
    count = body.count(part)
    if count != 1:
        raise ValueError(f"{label}: expected one {part!r}, saw {count}")


def additions(piece: str) -> str:
    return "\n".join(line[1:] for line in piece.splitlines()
                     if line.startswith("+")) + "\n"


def source_sections(rejected: str) -> tuple[str, str, str, str]:
    # 4.19.325-rt140 reject, first 3 hunks only; these are read from the
    # actual E404 .rej rather than reconstructed from a different kernel.
    hunks = re.split(r"(?m)^@@ ", rejected)
    if len(hunks) < 7:
        raise ValueError("Unexpected truncated softirq rejected hunks")
    first, second, third = hunks[1:4]
    split_name = " const char * const softirq_to_name[NR_SOFTIRQS] = {"
    exactly_once(first, split_name, REJECT)
    before, after = first.split(split_name)
    declaration = additions(before)
    runners = additions(after)
    wake_and_guard = additions(second)
    nonrt_dispatch = additions(third)
    if not declaration.startswith("#ifdef CONFIG_PREEMPT_RT_FULL\n"):
        raise ValueError("Missing upstream ktimer softirq RT declaration")
    if not runners.startswith("#ifdef CONFIG_NO_HZ_COMMON\n"):
        raise ValueError("Missing upstream softirq runner NOHZ gate")
    if not runners.rstrip().endswith("#endif"):
        raise ValueError("Softirq NOHZ runner block lacks endif")
    if not wake_and_guard.rstrip().endswith("#ifndef CONFIG_PREEMPT_RT_FULL"):
        raise ValueError("Missing upstream non-RT branch matching partial #else")
    if "static void handle_softirq(unsigned int vec_nr)" not in wake_and_guard:
        raise ValueError("Missing upstream softirq vector executor")
    for marker in (
        "static inline int ksoftirqd_softirq_pending(void)",
        "static void handle_pending_softirqs(u32 pending)",
        "static void run_ksoftirqd(unsigned int cpu)",
    ):
        if marker not in nonrt_dispatch:
            raise ValueError("Missing original non-RT dispatch: " + marker)
    for marker in (
        "DEFINE_PER_CPU(struct task_struct *, ktimer_softirqd);",
        "static inline void softirq_set_runner(unsigned int sirq)",
        "static inline void softirq_clr_runner(unsigned int sirq)",
        "void softirq_check_pending_idle(void)",
        "static void wakeup_timer_softirqd(void)",
    ):
        if marker not in declaration + runners + wake_and_guard:
            raise ValueError("Missing original RT helper: " + marker)
    return declaration, runners, wake_and_guard, nonrt_dispatch


def prepare(tree: Path) -> tuple[str, dict]:
    for name in (SOFTIRQ, REJECT, PENDING):
        if not (tree / name).is_file():
            raise ValueError("Missing pinned RT file: " + name)
    rejected_count = len(list(tree.rglob("*.rej")))
    if rejected_count != 64:
        raise ValueError(f"Stage38 needs 64 pending RT rejects, saw {rejected_count}")
    reject = (tree / REJECT).read_text(encoding="utf-8")
    declare, runners, wake, nonrt = source_sections(reject)
    body = (tree / SOFTIRQ).read_text(encoding="utf-8")
    for term in (KSOFTIRQD_ANCHOR, NAME_ANCHOR, WAKE_ANCHOR, RT_ELSE):
        exactly_once(body, term, SOFTIRQ)
    if "#ifndef CONFIG_PREEMPT_RT_FULL" in body or "softirq_set_runner(unsigned int sirq)" in body:
        raise ValueError("Early RT softirq guards already ported or source changed")
    if "DEFINE_PER_CPU(struct task_struct *, ktimer_softirqd);" in body:
        raise ValueError("RT ktimer already present")
    if "static void handle_softirq(unsigned int vec_nr)" in body:
        raise ValueError("RT softirq vector handler already present")
    updated = body.replace(KSOFTIRQD_ANCHOR, KSOFTIRQD_ANCHOR + declare, 1)
    updated = updated.replace(NAME_ANCHOR, NAME_ANCHOR + "\n" + runners, 1)
    updated = updated.replace(WAKE_ANCHOR, WAKE_ANCHOR + "\n" + wake + nonrt, 1)
    # There must be the one real #else already carried by the partial patch.
    if updated.count("#ifndef CONFIG_PREEMPT_RT_FULL") != 1:
        raise ValueError("Expected one restored RT conditional")
    if updated.count(RT_ELSE) != 1:
        raise ValueError("Unexpected second non-RT to RT transition")
    return updated, {
        "stage": "EXP76_STAGE38_RT_SOFTIRQ_REJECTED_ENTRY_AND_GUARDS",
        "applied": False,
        "original_rejected_hunks_consumed": 3,
        "rt_ktimer_worker_declaration_restored": True,
        "rt_nohz_runner_tracking_restored": True,
        "rt_vector_handler_restored": True,
        "non_rt_softirq_dispatch_restored": True,
        "paired_preempt_rt_branch_guard_restored": True,
        "remaining_rejected_files": rejected_count,
        "softirq_object_compiled": False,
        "full_softirq_semantics_verified": False,
        "migration_runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = parser.parse_args()
    root = args.tree.resolve()
    updated, result = prepare(root)
    if args.mode == "apply":
        (root / SOFTIRQ).write_text(updated, encoding="utf-8")
    result["applied"] = args.mode == "apply"
    if len(list(root.rglob("*.rej"))) != 64:
        raise ValueError("Unexpected change in RT reject count")
    output = args.report.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "stage38-status.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
