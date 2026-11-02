#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage36 migration integration contract / NO FLASH
"""Audit the complete missing RT CPU-pinning runtime before attempting its port.

The pinned 4.19.325-rt140 core.c rejected hunk implements migrate_disable(),
migrate_disabled_sched(), migrate_enable(), and cpu_nr_pinned() together,
and uses cpus_ptr/cpus_mask, an incompatible E404 affinity ABI.

Do not add a standalone cpu_nr_pinned() that reads an unmaintained counter.
This audit is read-only for the kernel and records each dependency honestly.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

CORE = "kernel/sched/core.c"
CORE_REJECT = "kernel/sched/core.c.rej"
RQ_HEADER = "kernel/sched/sched.h"
RQ_REJECT = "kernel/sched/sched.h.rej"
CPU = "kernel/cpu.c"
SCHED = "include/linux/sched.h"
PREEMPT = "include/linux/preempt.h"
CPU_PRI_REJECT = "kernel/sched/cpupri.c.rej"

REQUIRED_REJECT_MARKERS = (
    "+void migrate_disable(void)",
    "+void migrate_enable(void)",
    "+int cpu_nr_pinned(int cpu)",
    "+static void migrate_disabled_sched(struct task_struct *p)",
    "+\t\tthis_rq()->nr_pinned++;",
    "+\trq->nr_pinned--;",
    "+\tp->cpus_ptr = cpumask_of(smp_processor_id());",
    "+\tp->cpus_ptr = &p->cpus_mask;",
    "+\t\twake_up_process(takedown_cpu_task);",
)
PINNED_RQ_FIELD = "+\tint\t\t\tnr_pinned;"
PREEMPT_DECLARATIONS = (
    "extern void migrate_disable(void);",
    "extern void migrate_enable(void);",
    "int __migrate_disabled(struct task_struct *p);",
)


def require_one(text: str, needle: str, filename: str) -> None:
    count = text.count(needle)
    if count != 1:
        raise ValueError(f"{filename}: expected 1 occurrence of {needle!r}, saw {count}")


def inspect(tree: Path) -> dict:
    for p in (CORE, CORE_REJECT, RQ_HEADER, RQ_REJECT, CPU, SCHED,
              PREEMPT, CPU_PRI_REJECT):
        if not (tree / p).is_file():
            raise ValueError("Pinned E404 RT source prerequisite missing: " + p)
    count = len(list(tree.rglob("*.rej")))
    if count != 64:
        raise ValueError(f"Stage36 expects 64 unresolved RT rejects, got {count}")

    rejected_core = (tree / CORE_REJECT).read_text(encoding="utf-8")
    rejected_rq = (tree / RQ_REJECT).read_text(encoding="utf-8")
    for needle in REQUIRED_REJECT_MARKERS:
        expected = 3 if "migrate_disabled_sched" in needle else (
            2 if needle in ("+void migrate_disable(void)", "+void migrate_enable(void)")
            else 1
        )
        seen = rejected_core.count(needle)
        if seen != expected:
            raise ValueError(f"{CORE_REJECT}: expected {expected} {needle!r}, saw {seen}")
    require_one(rejected_rq, PINNED_RQ_FIELD, RQ_REJECT)

    core = (tree / CORE).read_text(encoding="utf-8")
    rq = (tree / RQ_HEADER).read_text(encoding="utf-8")
    cpu = (tree / CPU).read_text(encoding="utf-8")
    sched = (tree / SCHED).read_text(encoding="utf-8")
    preempt = (tree / PREEMPT).read_text(encoding="utf-8")
    require_one(core, "static void migrate_disabled_sched(struct task_struct *p);", CORE)
    require_one(core, "return p->migrate_disable;", CORE)
    if cpu.count("cpu_nr_pinned(cpu)") != 2:
        raise ValueError("kernel/cpu.c hotplug calls unexpectedly changed")
    for marker in PREEMPT_DECLARATIONS:
        count = preempt.count(marker)
        expected = 2 if marker.startswith("extern") else 1
        if count != expected:
            raise ValueError(f"{PREEMPT}: expected {expected} {marker!r}, saw {count}")
    for marker in ("cpumask_t\t\t\tcpus_allowed;",
                   "cpumask_t\t\t\tcpus_requested;",
                   "int\t\t\t\tmigrate_disable;",
                   "bool\t\t\t\tmigrate_disable_scheduled;"):
        require_one(sched, marker, SCHED)

    # Presence of any of these means a later stage may have started the real
    # runtime port. Refuse to report the old blocker inventory as current.
    unexpected = (
        (r"\bvoid\s+migrate_disable\s*\(\s*void\s*\)\s*\{", core, CORE),
        (r"\bvoid\s+migrate_enable\s*\(\s*void\s*\)\s*\{", core, CORE),
        (r"\bint\s+cpu_nr_pinned\s*\(\s*int\s+cpu\s*\)\s*\{", core, CORE),
        (r"\bstatic\s+void\s+migrate_disabled_sched\s*\("
         r"\s*struct\s+task_struct\s*\*\s*p\s*\)\s*\{", core, CORE),
        (r"\bint\s+nr_pinned\s*;", rq, RQ_HEADER),
    )
    for pattern, body, filename in unexpected:
        if re.search(pattern, body):
            raise ValueError(filename + ": migration lifecycle changed; re-audit required")
    if "cpus_ptr;" in sched or re.search(r"\bcpus_mask\s*;", sched):
        raise ValueError("E404 affinity mask ABI changed; re-audit required")
    return {
        "stage": "EXP76_STAGE36_RT_CPU_PINNING_CONTRACT_INVENTORY",
        "read_only_kernel_tree": True,
        "upstream_rt_core_rejected_hunk_verified": True,
        "upstream_rt_runqueue_rejected_hunk_verified": True,
        "vendor_embedded_cpus_allowed_verified": True,
        "task_migrate_disable_fields_verified": True,
        "cpu_hotplug_calls_cpu_nr_pinned": 2,
        "core_migrate_disabled_sched_only_declared": True,
        "core_migrate_disable_and_enable_implemented": False,
        "core_cpu_nr_pinned_implemented": False,
        "runqueue_nr_pinned_field_implemented": False,
        "rt_upstream_pointer_mask_requires_vendor_port": True,
        "cross_file_runtime_contract_complete": False,
        "blockers": [
            "kernel/sched/core.c: restore real nested migrate_disable and migrate_enable lifecycle",
            "kernel/sched/core.c: restore migrate_disabled_sched with E404 cpus_allowed ABI",
            "kernel/sched/sched.h: add nr_pinned counter in rq under RT+SMP",
            "kernel/sched/core.c: maintain nr_pinned on disable/enable and handle hotplug wakeup",
            "kernel/sched/core.c: implement cpu_nr_pinned only with functional tracked counter",
            "kernel/cpu.c: preserve hotplug -EAGAIN and task wakeup behavior",
            "include/linux/sched.h: preserve E404 embedded cpus_allowed/cpus_requested masks",
        ],
        "remaining_rejected_files": count,
        "kernel_built": False,
        "flash_ready": False,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    p.add_argument("--mode", required=True, choices=("verify", "audit"))
    args = p.parse_args()
    result = inspect(args.tree.resolve())
    if args.mode == "audit":
        report = args.report.resolve()
        report.mkdir(parents=True, exist_ok=True)
        (report / "stage36-status.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
