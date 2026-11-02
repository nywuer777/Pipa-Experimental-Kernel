#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 GitHub Actions / EXP76 Stage53 RT LRU drain and E404 deadline affinity / NO FLASH
"""Reconcile E404's LRU drain loop with the already-applied upstream RT helper.

The RT patch guards per-cpu lru_add_drain_work under !PREEMPT_RT_BASE and
provides remote_lru_add_drain() for both RT and non-RT. The E404 vendor
loop remained on the old per-cpu work API, producing undeclared symbols.
Also restore the E404 task_struct cpus_allowed mask in cpudeadline.c.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SWAP = "mm/swap.c"
CPUDL = "kernel/sched/cpudeadline.c"
SMP_HEADER = "#ifdef CONFIG_SMP\n\n#ifdef CONFIG_PREEMPT_RT_BASE\n"
RT_HELPER = (
    "static inline void remote_lru_add_drain(int cpu, struct cpumask *has_work)\n"
    "{\n"
    "\tlocal_lock_on(swapvec_lock, cpu);\n"
    "\tlru_add_drain_cpu(cpu);\n"
    "\tlocal_unlock_on(swapvec_lock, cpu);\n"
    "}\n"
)
NONRT_HELPER = (
    "static inline void remote_lru_add_drain(int cpu, struct cpumask *has_work)\n"
    "{\n"
    "\tstruct work_struct *work = &per_cpu(lru_add_drain_work, cpu);\n\n"
    "\tINIT_WORK(work, lru_add_drain_per_cpu);\n"
    "\tqueue_work_on(cpu, mm_percpu_wq, work);\n"
    "\tcpumask_set_cpu(cpu, has_work);\n"
    "}\n"
)
OLD_DRAIN = (
    "\tfor_each_online_cpu(cpu) {\n"
    "\t\tstruct work_struct *work = &per_cpu(lru_add_drain_work, cpu);\n\n"
    "\t\tif (pagevec_count(&per_cpu(lru_add_pvec, cpu)) ||\n"
    "\t\t    pagevec_count(&per_cpu(lru_rotate_pvecs, cpu)) ||\n"
    "\t\t    pagevec_count(&per_cpu(lru_deactivate_file_pvecs, cpu)) ||\n"
    "\t\t    pagevec_count(&per_cpu(lru_deactivate_pvecs, cpu)) ||\n"
    "\t\t    pagevec_count(&per_cpu(lru_lazyfree_pvecs, cpu)) ||\n"
    "\t\t    need_activate_page_drain(cpu)) {\n"
    "\t\t\tINIT_WORK(work, lru_add_drain_per_cpu);\n"
    "\t\t\tqueue_work_on(cpu, mm_percpu_wq, work);\n"
    "\t\t\tcpumask_set_cpu(cpu, &has_work);\n"
    "\t\t}\n"
    "\t}\n\n"
    "\tfor_each_cpu(cpu, &has_work)\n"
    "\t\tflush_work(&per_cpu(lru_add_drain_work, cpu));\n"
)
NEW_DRAIN = (
    "\tfor_each_online_cpu(cpu) {\n"
    "\t\tif (pagevec_count(&per_cpu(lru_add_pvec, cpu)) ||\n"
    "\t\t    pagevec_count(&per_cpu(lru_rotate_pvecs, cpu)) ||\n"
    "\t\t    pagevec_count(&per_cpu(lru_deactivate_file_pvecs, cpu)) ||\n"
    "\t\t    pagevec_count(&per_cpu(lru_deactivate_pvecs, cpu)) ||\n"
    "\t\t    pagevec_count(&per_cpu(lru_lazyfree_pvecs, cpu)) ||\n"
    "\t\t    need_activate_page_drain(cpu)) {\n"
    "\t\t\tremote_lru_add_drain(cpu, &has_work);\n"
    "\t\t}\n"
    "\t}\n\n"
    "#ifndef CONFIG_PREEMPT_RT_BASE\n"
    "\tfor_each_cpu(cpu, &has_work)\n"
    "\t\tflush_work(&per_cpu(lru_add_drain_work, cpu));\n"
    "#endif\n"
)
CPUDL_AND_OLD = "cpumask_and(later_mask, cp->free_cpus, p->cpus_ptr)"
CPUDL_AND_NEW = "cpumask_and(later_mask, cp->free_cpus, &p->cpus_allowed)"
CPUDL_TEST_OLD = "cpumask_test_cpu(best_cpu, p->cpus_ptr)"
CPUDL_TEST_NEW = "cpumask_test_cpu(best_cpu, &p->cpus_allowed)"


def one(src: str, snippet: str, name: str) -> None:
    n = src.count(snippet)
    if n != 1:
        raise ValueError(f"{name}: expected exactly one pinned fragment, got {n}")


def prepare(tree: Path) -> tuple[dict[str, str], dict]:
    if not (tree / ".git").is_dir():
        raise ValueError("Expected isolated E404 git checkout")
    for name in (SWAP, CPUDL, "kernel/sched/cpupri.c.rej"):
        if not (tree / name).is_file():
            raise ValueError("Missing E404 RT source/reject: " + name)
    rejected = len(list(tree.rglob("*.rej")))
    if rejected != 64:
        raise ValueError(f"Expected 64 unresolved RT rejects, got {rejected}")
    swap = (tree / SWAP).read_text(encoding="utf-8")
    cpudl = (tree / CPUDL).read_text(encoding="utf-8")
    one(swap, SMP_HEADER, "Pinned RT SMP/PREEMPT_RT branch")
    one(swap, RT_HELPER, "Pinned RT remote LRU helper")
    one(swap, NONRT_HELPER, "Pinned non-RT per-CPU work helper")
    one(swap, OLD_DRAIN, "E404 vendor LRU drain loop")
    one(swap, "void lru_add_drain_all(void)\n{\n\tstatic DEFINE_MUTEX(lock);\n", "Pinned SMP drain declaration")
    one(cpudl, CPUDL_AND_OLD, "RT cpudeadline affinity mask")
    one(cpudl, CPUDL_TEST_OLD, "RT cpudeadline best_cpu mask")
    if "int cpudl_find(struct cpudl *cp, struct task_struct *p," not in cpudl:
        raise ValueError("E404 cpudl_find ABI drift")
    if CPUDL_AND_NEW in cpudl or CPUDL_TEST_NEW in cpudl:
        raise ValueError("E404 cpudeadline ABI already reconciled")
    swap_new = swap.replace(OLD_DRAIN, NEW_DRAIN, 1)
    cpudl_new = (
        cpudl.replace(CPUDL_AND_OLD, CPUDL_AND_NEW, 1)
        .replace(CPUDL_TEST_OLD, CPUDL_TEST_NEW, 1)
    )
    one(swap_new, NEW_DRAIN, "RT/nonRT split LRU drain loop")
    one(swap_new, RT_HELPER, "Preserved RT remote helper")
    one(swap_new, NONRT_HELPER, "Preserved non-RT remote helper")
    one(cpudl_new, CPUDL_AND_NEW, "Restored E404 deadline affinity")
    one(cpudl_new, CPUDL_TEST_NEW, "Restored E404 deadline best_cpu mask")
    if OLD_DRAIN in swap_new or "p->cpus_ptr" in cpudl_new:
        raise ValueError("Unreconciled old LRU drain or deadline ABI")
    return {SWAP: swap_new, CPUDL: cpudl_new}, {
        "stage": "EXP76_STAGE53_RT_LRU_DRAIN_E404_CPUDEADLINE_NONFLASH",
        "original_sha256": {
            SWAP: hashlib.sha256(swap.encode()).hexdigest(),
            CPUDL: hashlib.sha256(cpudl.encode()).hexdigest(),
        },
        "patched_sha256": {
            SWAP: hashlib.sha256(swap_new.encode()).hexdigest(),
            CPUDL: hashlib.sha256(cpudl_new.encode()).hexdigest(),
        },
        "rt_remote_lru_drain_helper_preserved": True,
        "nonrt_percpu_work_and_flush_preserved": True,
        "vendor_pagevec_conditions_preserved": True,
        "deadline_cpus_allowed_abi_restored": True,
        "remaining_rejected_files": rejected,
        "rt_runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }


def execute(tree: Path, report: Path, mode: str) -> dict:
    if mode not in ("verify", "apply"):
        raise ValueError("Unsupported Stage53 mode")
    changes, status = prepare(tree)
    if mode == "apply":
        for name, content in changes.items():
            (tree / name).write_text(content, encoding="utf-8")
        if any((tree / name).read_text(encoding="utf-8") != content
               for name, content in changes.items()):
            raise ValueError("Stage53 source write verification failed")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage53 changed the RT reject count")
    status["applied"] = mode == "apply"
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage53-status.json").write_text(
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
