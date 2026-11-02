#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 GitHub Actions / EXP76 Stage55 IRQ work atomic and vendor mmap rwsem ABI / NO FLASH
"""Fix two proven E404/RT aggregate Kbuild source errors, preserving semantics.

The RT patch assigns IRQ_WORK_HARD_IRQ by |= to an atomic_t flags member.
Use atomic_or, the existing arm64 atomic API, immediately after init_irq_work.

E404's Oplus NAND swapin path inspects the non-RT-only mmap_sem.wait_list
member. The already-ported RT rwsem header provides rwsem_is_contended().
Use that established helper for both RT and non-RT, not a fabricated field.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

TOPOLOGY = "kernel/sched/topology.c"
MADVISE = "mm/madvise.c"
IRQ_HEADER = "include/linux/irq_work.h"
RWSEM_HEADER = "include/linux/rwsem.h"
RT_RWSEM = "include/linux/rwsem_rt.h"

IRQ_OLD = (
    "\tinit_irq_work(&rd->rto_push_work, rto_push_irq_work_func);\n"
    "\trd->rto_push_work.flags |= IRQ_WORK_HARD_IRQ;\n"
)
IRQ_NEW = (
    "\tinit_irq_work(&rd->rto_push_work, rto_push_irq_work_func);\n"
    "\tatomic_or(IRQ_WORK_HARD_IRQ, &rd->rto_push_work.flags);\n"
)
MADVISE_OLD = (
    "if ((e404_data.rom_type == 3) && "
    "!list_empty(&vma->vm_mm->mmap_sem.wait_list))"
)
MADVISE_NEW = (
    "if ((e404_data.rom_type == 3) && "
    "rwsem_is_contended(&vma->vm_mm->mmap_sem))"
)
GUARD = "#if defined(CONFIG_OPLUS_NANDSWAP) || defined(CONFIG_PROCESS_RECLAIM_ENHANCE)\n"


def exactly_once(data: str, fragment: str, name: str) -> None:
    count = data.count(fragment)
    if count != 1:
        raise ValueError(f"{name}: expected exactly one pinned match, found {count}")


def prepare(tree: Path) -> tuple[dict[str, str], dict]:
    if not (tree / ".git").is_dir():
        raise ValueError("Expected isolated E404 source checkout")
    for name in (TOPOLOGY, MADVISE, IRQ_HEADER, RWSEM_HEADER, RT_RWSEM,
                 "kernel/sched/cpupri.c.rej"):
        if not (tree / name).is_file():
            raise ValueError("Missing pinned RT source/reject: " + name)
    rejected = len(list(tree.rglob("*.rej")))
    if rejected != 64:
        raise ValueError(f"Expected 64 unresolved RT reject files, found {rejected}")
    original = {name: (tree / name).read_text(encoding="utf-8")
                for name in (TOPOLOGY, MADVISE)}
    irq = (tree / IRQ_HEADER).read_text(encoding="utf-8")
    sem = (tree / RWSEM_HEADER).read_text(encoding="utf-8")
    rtsem = (tree / RT_RWSEM).read_text(encoding="utf-8")

    exactly_once(irq, "\tatomic_t flags;\n", "irq_work.flags atomic_t contract")
    exactly_once(irq, "#define IRQ_WORK_HARD_IRQ\tBIT(3)\n",
                 "IRQ_WORK_HARD_IRQ defined flag")
    exactly_once(irq, "\tatomic_set(&work->flags, 0);\n",
                 "init_irq_work zero-initializes flags")
    exactly_once(sem, "#include <linux/rwsem_rt.h>\n",
                 "PREEMPT_RT_FULL selects RT rwsem")
    exactly_once(rtsem, "static inline int rwsem_is_contended(struct rw_semaphore *sem)\n",
                 "RT rwsem contention helper")
    exactly_once(sem, "static inline int rwsem_is_contended(struct rw_semaphore *sem)\n",
                 "E404 nonRT rwsem contention helper")

    top = original[TOPOLOGY]
    mad = original[MADVISE]
    exactly_once(top, IRQ_OLD, "RT rootdomain IRQ hard work initialization")
    exactly_once(mad, MADVISE_OLD, "Vendor Oplus NAND swapin wait heuristic")
    exactly_once(mad, GUARD, "Vendor Oplus NAND swapin build guard")
    if MADVISE_NEW in mad or IRQ_NEW in top:
        raise ValueError("Stage55 correction already applied")
    replacements = {
        TOPOLOGY: top.replace(IRQ_OLD, IRQ_NEW, 1),
        MADVISE: mad.replace(MADVISE_OLD, MADVISE_NEW, 1),
    }
    for name, fragment in ((TOPOLOGY, IRQ_NEW), (MADVISE, MADVISE_NEW)):
        exactly_once(replacements[name], fragment, name + " fixed contract")
    return replacements, {
        "stage": "EXP76_STAGE55_ATOMIC_IRQ_WORK_AND_VENDOR_RWSEM_NONFLASH",
        "irq_work_flags_atomic_t_preserved": True,
        "irq_work_hard_irq_atomic_or": True,
        "vendor_nandswap_rom_type_guard_preserved": True,
        "rt_and_nonrt_rwsem_is_contended_helper_verified": True,
        "remaining_rejected_files": rejected,
        "runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
        "original_sha256": {
            name: hashlib.sha256(body.encode()).hexdigest()
            for name, body in original.items()
        },
        "patched_sha256": {
            name: hashlib.sha256(body.encode()).hexdigest()
            for name, body in replacements.items()
        },
    }


def execute(tree: Path, report: Path, mode: str) -> dict:
    if mode not in ("verify", "apply"):
        raise ValueError("Stage55 mode must be apply or verify")
    changes, info = prepare(tree)
    if mode == "apply":
        for name, content in changes.items():
            (tree / name).write_text(content, encoding="utf-8")
        if any((tree / name).read_text(encoding="utf-8") != content
               for name, content in changes.items()):
            raise ValueError("Stage55 post-write source integrity failure")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage55 altered unresolved RT rejects")
    info["applied"] = mode == "apply"
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage55-status.json").write_text(
        json.dumps(info, indent=2) + "\n", encoding="utf-8")
    return info


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = p.parse_args()
    print(json.dumps(execute(args.tree.resolve(), args.report.resolve(), args.mode), indent=2))


if __name__ == "__main__":
    main()
