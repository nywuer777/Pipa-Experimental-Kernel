#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage61 RT idle softirq dispatch and E404 userfaultfd seqlock / NO FLASH
"""Complete two compiler-proven E404/4.19-RT integration contracts.

do_softirq() is absent from PREEMPT_RT_FULL: queue completion from idle
must wake the already defined local RT softirq threads, not run softirq
actions inline under the IRQ-disabled idle context. The Stage38 partial
RT port provides both ksoftirqd and ktimer_softirqd wake helpers.

The RT patch also migrated four userfaultfd refile_seq consumers and its
initializer to the seqlock API; the E404 field declaration remained a bare
seqcount. Restore the matching type without altering the refile protocol.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

SMP = "kernel/smp.c"
SOFTIRQ = "kernel/softirq.c"
INTERRUPT = "include/linux/interrupt.h"
USERFAULT = "fs/userfaultfd.c"
REJECT = "kernel/sched/cpupri.c.rej"

SMP_OLD = (
    "\tlocal_irq_save(flags);\n"
    "\tflush_smp_call_function_queue(true);\n"
    "\tif (local_softirq_pending())\n"
    "\t\tdo_softirq();\n\n"
    "\tlocal_irq_restore(flags);\n"
)
SMP_NEW = (
    "\tlocal_irq_save(flags);\n"
    "\tflush_smp_call_function_queue(true);\n"
    "\tif (local_softirq_pending()) {\n"
    "#ifdef CONFIG_PREEMPT_RT_FULL\n"
    "\t\twakeup_rt_softirqd_from_idle();\n"
    "#else\n"
    "\t\tdo_softirq();\n"
    "#endif\n"
    "\t}\n\n"
    "\tlocal_irq_restore(flags);\n"
)
TIMER_WAKE = (
    "#ifdef CONFIG_PREEMPT_RT_FULL\n"
    "static void wakeup_timer_softirqd(void)\n"
    "{\n"
    "\t/* Interrupts are disabled: no need to stop preemption */\n"
    "\tstruct task_struct *tsk = __this_cpu_read(ktimer_softirqd);\n\n"
    "\tif (tsk && tsk->state != TASK_RUNNING)\n"
    "\t\twake_up_process(tsk);\n"
    "}\n"
    "#endif\n"
)
IDLE_HELPER = (
    "\n/* Called with IRQs disabled from the SMP idle queue flush. */\n"
    "void wakeup_rt_softirqd_from_idle(void)\n"
    "{\n"
    "\tif (!local_softirq_pending())\n"
    "\t\treturn;\n"
    "\twakeup_softirqd();\n"
    "\twakeup_timer_softirqd();\n"
    "}\n"
)
SOFTIRQ_NEW = TIMER_WAKE[:-len("#endif\n")] + IDLE_HELPER + "#endif\n"
PUBLIC_ANCHOR = "extern void raise_softirq(unsigned int nr);\n\n"
PUBLIC_NEW = (
    PUBLIC_ANCHOR
    + "#ifdef CONFIG_PREEMPT_RT_FULL\n"
    + "void wakeup_rt_softirqd_from_idle(void);\n"
    + "#endif\n\n"
)
UFFD_OLD = "\tstruct seqcount refile_seq;\n"
UFFD_NEW = "\tseqlock_t refile_seq;\n"

def one(body: str, fragment: str, label: str) -> None:
    n = body.count(fragment)
    if n != 1:
        raise ValueError(f"{label}: expected exactly one pinned source fragment, got {n}")

def prepare(tree: Path) -> tuple[dict[str, str], dict]:
    if not (tree / ".git").is_dir():
        raise ValueError("Stage61 requires isolated E404 git checkout")
    rejects = len(list(tree.rglob("*.rej")))
    if rejects != 64:
        raise ValueError(f"Expected 64 outstanding RT rejected files, found {rejects}")
    for name in (SMP, SOFTIRQ, INTERRUPT, USERFAULT, REJECT):
        if not (tree / name).is_file():
            raise ValueError("Missing RT source or rejection evidence: " + name)
    original = {name: (tree / name).read_text(encoding="utf-8")
                for name in (SMP, SOFTIRQ, INTERRUPT, USERFAULT)}
    smp, soft, intr, uffd = (original[k] for k in
                             (SMP, SOFTIRQ, INTERRUPT, USERFAULT))
    one(smp, "void flush_smp_call_function_from_idle(void)\n",
        "E404 SMP idle flush entry point")
    one(smp, SMP_OLD, "E404 idle softirq direct dispatch")
    one(soft, TIMER_WAKE, "Original RT per-CPU timer softirq worker")
    one(soft, "static void wakeup_softirqd(void)\n",
        "Original regular softirq worker wake")
    one(soft, "DEFINE_PER_CPU(struct task_struct *, ktimer_softirqd);",
        "Stage38 RT timer worker declaration")
    one(intr, PUBLIC_ANCHOR, "Linux public softirq API declaration")
    one(intr, "static inline struct task_struct *this_cpu_ksoftirqd(void)\n",
        "Existing local softirq worker accessor")
    if "wakeup_rt_softirqd_from_idle" in soft + intr + smp:
        raise ValueError("Stage61 RT softirq idle bridge already applied")
    one(uffd, UFFD_OLD, "E404 userfaultfd racy seqcount declaration")
    for marker in (
        "write_seqlock(&ctx->refile_seq);",
        "write_sequnlock(&ctx->refile_seq);",
        "read_seqbegin(&ctx->refile_seq);",
        "read_seqretry(&ctx->refile_seq, seq)",
        "seqlock_init(&ctx->refile_seq);",
    ):
        one(uffd, marker, "Applied RT userfaultfd seqlock consumer")
    one(uffd, "/* a refile sequence protected by fault_pending_wqh lock */",
        "Vendor userfaultfd writer serialization")
    fixed = {
        SMP: smp.replace(SMP_OLD, SMP_NEW, 1),
        SOFTIRQ: soft.replace(TIMER_WAKE, SOFTIRQ_NEW, 1),
        INTERRUPT: intr.replace(PUBLIC_ANCHOR, PUBLIC_NEW, 1),
        USERFAULT: uffd.replace(UFFD_OLD, UFFD_NEW, 1),
    }
    one(fixed[SMP], SMP_NEW, "Conditional RT/nonRT SMP idle dispatch")
    one(fixed[SOFTIRQ], IDLE_HELPER, "RT worker wake without synthetic softirq")
    one(fixed[INTERRUPT],
        "void wakeup_rt_softirqd_from_idle(void);",
        "RT public softirq idle wake declaration")
    one(fixed[USERFAULT], UFFD_NEW, "E404 userfaultfd RT seqlock ABI")
    if UFFD_OLD in fixed[USERFAULT]:
        raise ValueError("Mismatched E404 userfaultfd seqcount declaration remains")
    return fixed, {
        "stage": "EXP76_STAGE61_SMP_IDLE_RT_SOFTIRQ_USERFAULTFD_SEQLOCK_NONFLASH",
        "rt_idle_dispatch_uses_existing_softirq_threads": True,
        "nonrt_direct_do_softirq_preserved": True,
        "rt_timer_and_regular_softirq_workers_woken": True,
        "userfaultfd_refile_seqlock_layout_reconciled": True,
        "remaining_rejected_files": rejects,
        "runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
        "original_sha256": {
            p: hashlib.sha256(t.encode()).hexdigest() for p,t in original.items()
        },
        "patched_sha256": {
            p: hashlib.sha256(t.encode()).hexdigest() for p,t in fixed.items()
        },
    }

def execute(tree: Path, report: Path, mode: str) -> dict:
    if mode not in ("verify", "apply"):
        raise ValueError("Stage61 mode must be verify or apply")
    edits, status = prepare(tree)
    if mode == "apply":
        for name, data in edits.items():
            (tree / name).write_text(data, encoding="utf-8")
        for name, data in edits.items():
            if (tree / name).read_text(encoding="utf-8") != data:
                raise ValueError("Stage61 source write verification failed: " + name)
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage61 RT reject count changed")
    status["applied"] = mode == "apply"
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage61-status.json").write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8"
    )
    return status

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--mode", choices=("verify", "apply"), required=True)
    a = p.parse_args()
    print(json.dumps(execute(a.tree.resolve(), a.report.resolve(), a.mode), indent=2))

if __name__ == "__main__":
    main()
