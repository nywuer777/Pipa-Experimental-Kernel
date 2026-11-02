#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 GitHub Actions / EXP76 Stage59 E404 RT kthread raw-lock and proc affinity / NO FLASH
"""Reconcile RT kthread worker raw-spinlock callers and E404 /proc cpumask ABI.

The official RT patch converts kthread_worker.lock to raw_spinlock_t and
most worker users but leaves four E404 kthread_worker_fn spin_* operations.
In fs/proc/array.c it substitutes task->cpus_ptr, missing in E404.
Preserve the existing worker concurrency and the actual E404 cpus_allowed
mask. Fail closed on declaration, call-site or RT reject drift.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

KTHREAD = "kernel/kthread.c"
KTHREAD_HEADER = "include/linux/kthread.h"
PROC = "fs/proc/array.c"
SCHED = "include/linux/sched.h"
WORKER_PREFIX = "int kthread_worker_fn(void *worker_ptr)\n"
WORKER_END = "EXPORT_SYMBOL_GPL(kthread_worker_fn);\n"
STOP_OLD = (
    "\t\tspin_lock_irq(&worker->lock);\n"
    "\t\tworker->task = NULL;\n"
    "\t\tspin_unlock_irq(&worker->lock);\n"
)
PICK_OLD = (
    "\twork = NULL;\n"
    "\tspin_lock_irq(&worker->lock);\n"
    "\tif (!list_empty(&worker->work_list)) {\n"
)
PICK_UNLOCK_OLD = (
    "\tworker->current_work = work;\n"
    "\tspin_unlock_irq(&worker->lock);\n"
)
PROC_START = "static void task_cpus_allowed(struct seq_file *m, struct task_struct *task)\n"
PROC_END = "static inline void task_core_dumping("
PROC_OLD = "cpumask_pr_args(task->cpus_ptr)"
PROC_NEW = "cpumask_pr_args(&task->cpus_allowed)"


def exact(src: str, marker: str, label: str, expected: int = 1) -> None:
    n = src.count(marker)
    if n != expected:
        raise ValueError(f"{label}: expected {expected} occurrences, got {n}")


def section(src: str, start: str, end: str, label: str) -> tuple[str, str, str]:
    exact(src, start, label + " start")
    exact(src, end, label + " end")
    before, tail = src.split(start, 1)
    body, after = tail.split(end, 1)
    return before, start + body, end + after


def prepare(tree: Path) -> tuple[dict[str, str], dict]:
    if not (tree / ".git").is_dir():
        raise ValueError("Expected isolated E404 git checkout")
    for name in (KTHREAD, KTHREAD_HEADER, PROC, SCHED,
                 "kernel/sched/cpupri.c.rej"):
        if not (tree / name).is_file():
            raise ValueError("Missing pinned E404 source/reject: " + name)
    rejects = len(list(tree.rglob("*.rej")))
    if rejects != 64:
        raise ValueError(f"Expected 64 unresolved RT rejects, got {rejects}")

    original = {name: (tree / name).read_text(encoding="utf-8")
                for name in (KTHREAD, KTHREAD_HEADER, PROC, SCHED)}
    h, s = original[KTHREAD_HEADER], original[SCHED]
    exact(h, "\traw_spinlock_t\t\tlock;\n",
          "RT kthread_worker.lock must be raw_spinlock_t")
    exact(h, ".lock = __RAW_SPIN_LOCK_UNLOCKED((worker).lock)",
          "RT worker static initializer")
    exact(s, "\tcpumask_t\t\t\tcpus_allowed;\n",
          "E404 task_struct affinity mask")
    if "cpus_ptr;" in s:
        raise ValueError("Unexpected E404 cpus_ptr field")
    k = original[KTHREAD]
    exact(k, "\traw_spin_lock_init(&worker->lock);\n",
          "RT kthread worker lock initialization")
    exact(k, "\traw_spin_lock_irq(&worker->lock);\n",
          "Already-applied RT kthread_flush_work caller")
    exact(k, "\traw_spin_unlock_irq(&worker->lock);\n",
          "Already-applied RT kthread_flush_work unlock")
    pre, worker, post = section(k, WORKER_PREFIX, WORKER_END,
                                "kthread_worker_fn exact body")
    exact(worker, STOP_OLD, "E404 worker stop lock pair")
    exact(worker, PICK_OLD, "E404 worker pending-work acquire")
    exact(worker, PICK_UNLOCK_OLD, "E404 worker pending-work release")
    exact(worker, "spin_lock_irq(&worker->lock)", "Unconverted E404 acquire", 2)
    exact(worker, "spin_unlock_irq(&worker->lock)",
          "Unconverted E404 release", 2)
    if "raw_spin_lock_irq(" in worker or "raw_spin_unlock_irq(" in worker:
        raise ValueError("Worker RT lock conversion partially present")
    fixed_worker = worker.replace(STOP_OLD,
        STOP_OLD.replace("spin_", "raw_spin_"), 1)
    fixed_worker = fixed_worker.replace(PICK_OLD,
        PICK_OLD.replace("spin_", "raw_spin_"), 1)
    fixed_worker = fixed_worker.replace(PICK_UNLOCK_OLD,
        PICK_UNLOCK_OLD.replace("spin_", "raw_spin_"), 1)
    exact(fixed_worker, "raw_spin_lock_irq(&worker->lock)",
          "RT worker lock acquires", 2)
    exact(fixed_worker, "raw_spin_unlock_irq(&worker->lock)",
          "RT worker lock releases", 2)
    if "\tspin_lock_irq(&worker->lock);" in fixed_worker or (
        "\tspin_unlock_irq(&worker->lock);" in fixed_worker
    ):
        raise ValueError("Unconverted worker lock remains")
    fixed_k = pre + fixed_worker + post

    p = original[PROC]
    ppre, proc, ppost = section(p, PROC_START, PROC_END,
                                "E404 /proc task affinity output")
    exact(proc, PROC_OLD, "Imported RT task->cpus_ptr", 2)
    if PROC_NEW in proc:
        raise ValueError("Mixed /proc affinity mask ABI")
    exact(proc, '"Cpus_allowed:\\t%*pb\\n"',
          "Preserved /proc Cpus_allowed format")
    exact(proc, '"Cpus_allowed_list:\\t%*pbl\\n"',
          "Preserved /proc Cpus_allowed_list format")
    fixed_proc = ppre + proc.replace(PROC_OLD, PROC_NEW) + ppost
    exact(fixed_proc, PROC_NEW, "E404 proc mask references", 2)
    if PROC_OLD in fixed_proc:
        raise ValueError("Remaining /proc task->cpus_ptr reference")
    changes = {KTHREAD: fixed_k, PROC: fixed_proc}
    return changes, {
        "stage": "EXP76_STAGE59_KTHREAD_RAW_SPIN_PROC_CPU_AFFINITY_NONFLASH",
        "worker_raw_lock_type_verified": True,
        "worker_raw_lock_pairs_restored": 2,
        "worker_lock_ops_reconciled": 4,
        "existing_rt_worker_lock_ops_preserved": True,
        "e404_task_cpus_allowed_verified": True,
        "proc_affinity_mask_references_restored": 2,
        "proc_output_formats_preserved": True,
        "remaining_rejected_files": rejects,
        "kernel_built": False,
        "runtime_verified": False,
        "flash_ready": False,
        "original_sha256": {
            name: hashlib.sha256(original[name].encode()).hexdigest()
            for name in (KTHREAD, PROC)
        },
        "patched_sha256": {
            name: hashlib.sha256(content.encode()).hexdigest()
            for name, content in changes.items()
        },
    }


def execute(tree: Path, report: Path, mode: str) -> dict:
    if mode not in ("verify", "apply"):
        raise ValueError("Unsupported Stage59 mode")
    changes, state = prepare(tree)
    if mode == "apply":
        for name, body in changes.items():
            (tree / name).write_text(body, encoding="utf-8")
        for name, body in changes.items():
            if (tree / name).read_text(encoding="utf-8") != body:
                raise ValueError("Stage59 post-write verification failed: " + name)
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage59 RT reject files changed")
    state["applied"] = mode == "apply"
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage59-status.json").write_text(
        json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return state


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = p.parse_args()
    print(json.dumps(execute(args.tree.resolve(), args.report.resolve(),
                             args.mode), indent=2))


if __name__ == "__main__":
    main()
