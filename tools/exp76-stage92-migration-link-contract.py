#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage92 linked migration ABI cross-check / NO FLASH
"""Validate Stage41 RT CPU-pinning source and actual linked System.map symbols.

This is a static+link contract, not a runtime migration or latency test.
Do not change source, delete .rej evidence, publish Image or flash.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

STAGE = "EXP76_STAGE92_RT_MIGRATION_ABI_SYMBOL_CROSSCHECK_NONFLASH"
REPORT = "stage92-status.json"
STAGE41 = "EXP76_STAGE41_RT_MIGRATION_LIFECYCLE_E404"
STAGE86 = "EXP76_STAGE86_RAW_ARM64_IMAGE_AND_RT_SYMBOL_DIAGNOSTIC_NONFLASH"
SYMBOLS = ("migrate_disable", "migrate_enable", "cpu_nr_pinned")
SOURCES = (
    "kernel/sched/core.c", "kernel/sched/sched.h",
    "include/linux/sched.h", "include/linux/cpu.h", "kernel/cpu.c",
)
CHECKS = {
    "saved_affinity_field": (
        "include/linux/sched.h", "cpumask_t\t\t\tmigrate_disable_saved_mask;"
    ),
    "runqueue_nr_pinned_field": (
        "kernel/sched/sched.h", "\tint\t\t\tnr_pinned;"
    ),
    "cpu_nr_pinned_declaration": (
        "include/linux/cpu.h", "extern int cpu_nr_pinned(int cpu);"
    ),
    "deferred_affinity_requested_mask": (
        "kernel/sched/core.c", "cpumask_copy(&p->migrate_disable_saved_mask, new_mask);"
    ),
    "restore_saved_affinity": (
        "kernel/sched/core.c", "cpumask_copy(&p->cpus_allowed, &p->migrate_disable_saved_mask);"
    ),
    "pin_to_current_cpu_mask": (
        "kernel/sched/core.c", "cpumask_copy(&p->cpus_allowed, cpumask_of(task_cpu(p)));"
    ),
    "nested_pin_increment": (
        "kernel/sched/core.c", "this_rq()->nr_pinned++;"
    ),
    "nested_pin_decrement": (
        "kernel/sched/core.c", "rq->nr_pinned--;"
    ),
    "asynchronous_cpu_stopper": (
        "kernel/sched/core.c", "stop_one_cpu_nowait(task_cpu(p), migration_cpu_stop,"
    ),
    "asynchronous_completion_guard": (
        "kernel/sched/core.c", "arg->done"
    ),
    "asynchronous_worker_disable_guard": (
        "kernel/sched/core.c", "work->disabled"
    ),
    "hotplug_wakeup": (
        "kernel/sched/core.c", "wake_up_process(takedown_cpu_task);"
    ),
    "lazy_preempt_disable": (
        "kernel/sched/core.c", "preempt_lazy_disable();"
    ),
    "lazy_preempt_enable": (
        "kernel/sched/core.c", "preempt_lazy_enable();"
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_state(path: Path, stage: str) -> dict:
    if not path.is_file():
        raise ValueError("Stage92 required prior CI report missing: " + str(path))
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("stage") != stage:
        raise ValueError("Stage92 prior report stage mismatch: " + stage)
    return state


def linked_symbols(system_map: Path) -> tuple[list[str], list[str]]:
    if not system_map.is_file():
        raise ValueError("Stage92 real linked System.map missing")
    discovered: dict[str, set[str]] = {name: set() for name in SYMBOLS}
    for line in system_map.read_text(encoding="utf-8", errors="replace").splitlines():
        items = line.split()
        if len(items) == 3 and items[1] in ("T", "t", "W", "w"):
            if items[2] in discovered and re.fullmatch(r"[0-9a-fA-F]+", items[0]):
                discovered[items[2]].add(items[0])
    present = [name for name in SYMBOLS if len(discovered[name]) == 1]
    missing = [name for name in SYMBOLS if len(discovered[name]) != 1]
    return present, missing


def execute(tree: Path, out: Path, stage41_path: Path,
            stage86_path: Path, report: Path) -> dict:
    if not (tree / ".git").is_dir():
        raise ValueError("Stage92 requires isolated pinned E404 trial tree")
    rejects = list(tree.rglob("*.rej"))
    if len(rejects) != 64 or not (tree / "kernel/sched/cpupri.c.rej").is_file():
        raise ValueError("Stage92 requires all 64 original RT rejection files")
    config = out / ".config"
    if not config.is_file():
        raise ValueError("Stage92 real RT Kconfig missing")
    settings = set(config.read_text(encoding="utf-8").splitlines())
    for setting in ("CONFIG_SMP=y", "CONFIG_PREEMPT_RT_FULL=y"):
        if setting not in settings:
            raise ValueError("Stage92 requires actual SMP + PREEMPT_RT_FULL: " + setting)
    stage41 = require_state(stage41_path, STAGE41)
    stage86 = require_state(stage86_path, STAGE86)
    required_stage41 = (
        "applied",
        "original_rt_migration_hunk_ported",
        "nested_migrate_disable_enable_present",
        "runqueue_nr_pinned_counted",
        "cpu_nr_pinned_reads_accounted_runqueue",
        "saved_vendor_affinity_mask_and_setaffinity_deferral",
        "upstream_async_stopper_safety_checks_preserved",
        "cpu_hotplug_caller_unchanged",
    )
    if not all(stage41.get(key) is True for key in required_stage41):
        raise ValueError("Stage92 incomplete Stage41 source integration evidence")
    if not (
        stage41.get("remaining_rejected_files") == 64
        and stage41.get("migration_runtime_semantics_verified") is False
        and stage41.get("flash_ready") is False
    ):
        raise ValueError("Stage92 Stage41 is not a verified runtime baseline")
    if not (
        stage86.get("attempted") is True
        and stage86.get("exit_code") == 0
        and stage86.get("raw_arm64_header_valid") is True
        and stage86.get("all_previous_unresolved_symbols_restored") is True
        and stage86.get("remaining_rejected_files") == 64
        and stage86.get("packaged_boot_image_generated") is False
        and stage86.get("flash_performed") is False
        and stage86.get("flash_ready") is False
    ):
        raise ValueError("Stage92 prior actual arm64 Image/link evidence invalid")
    kernel = out / "vmlinux"
    if not kernel.is_file() or kernel.open("rb").read(4) != b"\x7fELF":
        raise ValueError("Stage92 linked vmlinux ELF missing")
    contents = {}
    source_sha = {}
    for path in SOURCES:
        file = tree / path
        if not file.is_file():
            raise ValueError("Stage92 scheduler ABI source missing: " + path)
        contents[path] = file.read_text(encoding="utf-8")
        source_sha[path] = sha256(file)
    repeatable_rt_guards = {
        "asynchronous_completion_guard",
        "asynchronous_worker_disable_guard",
        "hotplug_wakeup",
        "lazy_preempt_disable",
        "lazy_preempt_enable",
    }
    for label, (path, token) in CHECKS.items():
        occurrences = contents[path].count(token)
        expected = occurrences >= 1 if label in repeatable_rt_guards else occurrences == 1
        if not expected:
            raise ValueError(
                "Stage92 RT scheduler pinning source contract violated: " +
                label + f" (found {occurrences})"
            )
    core = contents["kernel/sched/core.c"]
    for symbol in SYMBOLS:
        if not re.search(r"\b(?:void|int)\s+" + symbol + r"\s*\(", core):
            raise ValueError("Stage92 RT migration definition absent: " + symbol)
    cpu = contents["kernel/cpu.c"]
    if cpu.count("cpu_nr_pinned(cpu)") != 2:
        raise ValueError("Stage92 CPU hotplug pinning check call count changed")
    sched = contents["include/linux/sched.h"]
    if re.search(r"(?m)^\s*(?:const\s+)?(?:struct\s+cpumask\s*\*|cpumask_t)\s+cpus_ptr\s*;", sched):
        raise ValueError("Stage92 accidentally reintroduced unsupported E404 cpus_ptr ABI")
    present, missing = linked_symbols(out / "System.map")
    if missing:
        raise ValueError("Stage92 migration functions absent from actual linked System.map: " +
                         ", ".join(missing))
    result = {
        "stage": STAGE,
        "source_stage41_applied": True,
        "arm64_stage86_image_link_verified": True,
        "smp_preempt_rt_full_config_verified": True,
        "cross_file_source_contracts_verified": list(CHECKS),
        "cross_file_source_contract_count": len(CHECKS),
        "system_map_symbols_present": present,
        "system_map_symbols_missing": missing,
        "source_sha256": source_sha,
        "vmlinux_elf_sha256": sha256(kernel),
        "system_map_sha256": sha256(out / "System.map"),
        "vendor_embedded_cpus_allowed_preserved": True,
        "cpu_hotplug_callers_verified": 2,
        "original_rejects_retained": True,
        "remaining_rejected_files": 64,
        "verification_scope": "SOURCE_AND_LINK_ONLY",
        "migration_runtime_semantics_verified": False,
        "cpu_hotplug_runtime_verified": False,
        "rcu_runtime_verified": False,
        "device_boot_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    report.mkdir(parents=True, exist_ok=True)
    (report / REPORT).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--stage41-report", required=True, type=Path)
    p.add_argument("--stage86-report", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(execute(
        a.tree.resolve(), a.output.resolve(), a.stage41_report.resolve(),
        a.stage86_report.resolve(), a.report.resolve(),
    ), indent=2))


if __name__ == "__main__":
    main()
