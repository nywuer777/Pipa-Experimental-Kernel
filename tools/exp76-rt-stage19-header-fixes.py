#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage19 RT header compile fixes / NO FLASH
"""Resolve compiler-proven E404/RT header integration faults, fail closed.

This is a partial source port. interrupt.h and sched.h rejects remain because
their unrelated RT changes are unresolved. No kernel image or flash.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

HASHES = {
    "include/linux/rwsem.h": "7d43f189d2e64c04521d38486e1e363fe60899763732ae212d55f7b1144f396f",
    "include/linux/interrupt.h": "c6f6ab2612b327b2b9defaab3b84f568a4e1d59fb0b5393e882c51a1b48b6320",
    "include/linux/sched.h": "00b363fe9d8f3dcfb32aff0d39e758365f6e77e57a114f79776545ad5f169e00",
}
RW_PREFIX = "#include <linux/osq_lock.h>\n#endif\n"
RW_GUARD = (
    "#ifdef CONFIG_PREEMPT_RT_FULL\n"
    "#ifdef CONFIG_DEBUG_LOCK_ALLOC\n"
    "#define RW_DEP_MAP_INIT(lockname) .dep_map = { \\\n"
    "\t.name = #lockname, .wait_type_inner = LD_WAIT_SLEEP, }\n"
    "#else\n"
    "#define RW_DEP_MAP_INIT(lockname)\n"
    "#endif\n"
    "#include <linux/rwsem_rt.h>\n"
    "#else /* PREEMPT_RT_FULL */\n"
)
IRQ_REGION = (
    "#ifdef __ARCH_HAS_DO_SOFTIRQ\n"
    "void do_softirq_own_stack(void);\n"
    "#else\n"
    "static inline void do_softirq_own_stack(void)\n"
    "{\n"
    "\t__do_softirq();\n"
    "}\n"
    "#endif\n"
)
IRQ_SUFFIX = (
    "#else\n"
    "extern void thread_do_softirq(void);\n"
    "#endif\n"
)
IRQ_RAISE = "extern void __raise_softirq_irqoff(unsigned int nr);\n"
IRQ_EXTRA = (
    "#ifdef CONFIG_PREEMPT_RT_FULL\n"
    "extern void __raise_softirq_irqoff_ksoft(unsigned int nr);\n"
    "#else\n"
    "static inline void __raise_softirq_irqoff_ksoft(unsigned int nr)\n"
    "{\n"
    "\t__raise_softirq_irqoff(nr);\n"
    "}\n"
    "#endif\n"
)
OLD_MACROS = (
    "#define task_is_traced(task)\t\t((task->state & __TASK_TRACED) != 0)\n",
    "#define task_is_stopped_or_traced(task)\t((task->state & (__TASK_STOPPED | __TASK_TRACED)) != 0)\n",
)
FIELD_ANCHOR = (
    "#ifdef CONFIG_PREEMPT_RT_FULL\n"
    "# if defined CONFIG_HIGHMEM || defined CONFIG_X86_32\n"
)
FIELD_NEW = (
    "#ifdef CONFIG_PREEMPT_RT_FULL\n"
    "\tint\t\t\tsleeping_lock;\n"
    "# if defined CONFIG_HIGHMEM || defined CONFIG_X86_32\n"
)
RCU_IMPORT = "#include <linux/rcu_assign_pointer.h>\n"


def one(s: str, fragment: str, path: str) -> None:
    if s.count(fragment) != 1:
        raise ValueError(path + ": expected exactly one match: " + repr(fragment[:90]))


def prepare(tree: Path):
    originals: dict[str, str] = {}
    for path, sha in HASHES.items():
        source = tree / path
        rejected = tree / (path + ".rej")
        if not source.is_file() or not rejected.is_file():
            raise ValueError("Missing source or unresolved RT reject: " + path)
        actual = hashlib.sha256(rejected.read_bytes()).hexdigest()
        if actual != sha:
            raise ValueError(path + ": RT .rej hash mismatch: " + actual)
        originals[path] = source.read_text(encoding="utf-8")

    rw = originals["include/linux/rwsem.h"]
    one(rw, RW_PREFIX, "rwsem.h")
    one(rw, "#endif /* !PREEMPT_RT_FULL */", "rwsem.h")
    if "#include <linux/rwsem_rt.h>" in rw:
        raise ValueError("rwsem.h already selects the RT header")
    if not (tree / "include/linux/rwsem_rt.h").is_file():
        raise ValueError("Missing upstream RT rwsem implementation header")
    if "RW_DEP_MAP_INIT(name)" not in (tree / "include/linux/rwsem_rt.h").read_text():
        raise ValueError("Unexpected RT rwsem lockdep initializer")
    rw = rw.replace(RW_PREFIX, RW_PREFIX + "\n" + RW_GUARD, 1)

    irq = originals["include/linux/interrupt.h"]
    one(irq, IRQ_REGION, "interrupt.h")
    one(irq, "#ifndef CONFIG_PREEMPT_RT_FULL\nasmlinkage void do_softirq(void);", "interrupt.h")
    one(irq, IRQ_RAISE, "interrupt.h")
    if "extern void thread_do_softirq(void);" in irq:
        raise ValueError("interrupt.h RT softirq branch already present")
    soft = (tree / "kernel/softirq.c").read_text()
    for symbol in ("void thread_do_softirq(void)", "void __raise_softirq_irqoff_ksoft(unsigned int nr)"):
        if soft.count(symbol) != 1:
            raise ValueError("Missing RT softirq implementation: " + symbol)
    irq = irq.replace(IRQ_REGION, IRQ_REGION + IRQ_SUFFIX, 1)
    irq = irq.replace(IRQ_RAISE, IRQ_RAISE + IRQ_EXTRA, 1)
    # Do NOT declare softirq_check_pending_idle(); its RT implementation was
    # not verified in this partial port. Keep interrupt.h.rej unresolved.

    sched = originals["include/linux/sched.h"]
    reject_sched = (tree / "include/linux/sched.h.rej").read_text()
    for old in OLD_MACROS:
        one(sched, old, "sched.h")
        if "-" + old.rstrip("\n") not in reject_sched:
            raise ValueError("sched.h macro removal not covered by pinned RT reject")
    for symbol in (
        "static inline bool task_is_stopped_or_traced(struct task_struct *task)",
        "static inline bool task_is_traced(struct task_struct *task)",
        "static inline void sleeping_lock_inc(void)",
    ):
        one(sched, symbol, "sched.h")
    one(sched, FIELD_ANCHOR, "sched.h")
    if re.search(r"(?m)^\s*int\s+sleeping_lock\s*;", sched):
        raise ValueError("sched.h sleeping_lock field already present")
    for old in OLD_MACROS:
        sched = sched.replace(old, "", 1)
    sched = sched.replace(FIELD_ANCHOR, FIELD_NEW, 1)
    # This is an ABI field, not a complete lifecycle port; initialization
    # must be audited before an RT kernel is considered executable.

    rcu = (tree / "include/linux/rcupdate.h").read_text()
    one(rcu, RCU_IMPORT, "rcupdate.h")
    if rcu.count("#define rcu_assign_pointer(p, v)") != 1:
        raise ValueError("Vendor E404 RCU pointer macro not found exactly once")
    rcu = rcu.replace(RCU_IMPORT, "", 1)
    if rcu.count("#define rcu_assign_pointer(p, v)") != 1:
        raise ValueError("Vendor RCU macro was not preserved")

    return {
        "include/linux/rwsem.h": rw,
        "include/linux/interrupt.h": irq,
        "include/linux/sched.h": sched,
        "include/linux/rcupdate.h": rcu,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tree", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--mode", choices=("verify", "apply"), required=True)
    a = p.parse_args()
    root = a.tree.resolve()
    changes = prepare(root)
    if a.mode == "apply":
        for name, body in changes.items():
            (root / name).write_text(body, encoding="utf-8")
        (root / "include/linux/rwsem.h.rej").unlink()
    remaining = len(list(root.rglob("*.rej")))
    data = {
        "stage": "EXP76_RT_STAGE19_COMPILER_HEADER_FIXES",
        "applied": a.mode == "apply",
        "rwsem_rt_header_branch_completed": a.mode == "apply",
        "interrupt_rt_softirq_branch_completed": a.mode == "apply",
        "sched_task_macro_collision_removed": a.mode == "apply",
        "task_sleeping_lock_field_added": a.mode == "apply",
        "rcu_assign_pointer_vendor_definition_preserved": a.mode == "apply",
        "irq_functional_reject_remaining": True,
        "sched_affinity_reject_remaining": True,
        "sleeping_lock_lifecycle_review_required": True,
        "remaining_rejected_files": remaining,
        "kernel_built": False,
        "flash_ready": False,
    }
    report = a.report.resolve()
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage19-status.json").write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps(data, indent=2))
    if a.mode == "apply" and remaining != 65:
        raise SystemExit("FAIL_CLOSED: expected 65 remaining RT reject files")


if __name__ == "__main__":
    main()
