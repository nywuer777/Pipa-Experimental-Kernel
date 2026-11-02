#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Clang21 scheduler coverage / NO FLASH
"""Compile a bounded set of RT-critical ARM64 objects after the 3-object gate.

All invocations target individual .o files only. No link, Image, modules or
boot artifacts. A successful object build never declares a working RT kernel.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

EXTRA_OBJECTS = (
    "kernel/sched/rt.o",
    "kernel/sched/fair.o",
    "kernel/sched/deadline.o",
    "kernel/sched/idle.o",
    "kernel/sched/stop_task.o",
    "kernel/cpu.o",
    "kernel/locking/rtmutex.o",
    "kernel/softirq.o",
    "kernel/time/timer.o",
)
BASELINE = ("kernel_sched_cpupri.o", "kernel_sched_core.o", "kernel_fork.o")
DIAGNOSTIC = re.compile(
    r"fatal error:|(?<![a-z])error:|warning:|undefined reference|"
    r"No rule to make target|\bError\s+\d+\b", re.IGNORECASE
)
MIGRATE_DECL = re.compile(
    r"\bstatic\s+(?:inline\s+)?void\s+migrate_disabled_sched"
    r"\s*\(\s*struct\s+task_struct\s*\*\s*p\s*\)\s*;"
)
MIGRATE_DEF = re.compile(
    r"\bstatic\s+(?:inline\s+)?void\s+migrate_disabled_sched"
    r"\s*\(\s*struct\s+task_struct\s*\*\s*p\s*\)\s*\{"
)
MIGRATION_ENTRY_DEF = re.compile(r"\bvoid\s+migrate_(?:disable|enable)\s*\(\s*void\s*\)\s*\{")


def diagnostic_lines(log: str, limit: int = 24) -> list[str]:
    return [x.strip()[:400] for x in log.splitlines() if DIAGNOSTIC.search(x)][:limit]


def inspect_migration(core: str) -> dict:
    decl = len(MIGRATE_DECL.findall(core))
    definition = len(MIGRATE_DEF.findall(core))
    entries = len(MIGRATION_ENTRY_DEF.findall(core))
    return {
        "migrate_disabled_sched_declarations": decl,
        "migrate_disabled_sched_definitions": definition,
        "migrate_disabled_sched_missing_local_definition": decl > 0 and definition == 0,
        "migration_entrypoint_definitions_in_core": entries,
        "runtime_migration_contract_verified": False,
    }


def baseline_passed(path: Path) -> bool:
    if not path.is_file():
        return False
    value = json.loads(path.read_text(encoding="utf-8"))
    targets = value.get("targets", {})
    return (
        value.get("config_preempt_rt_full") is True
        and all(targets.get(name, {}).get("compiled") is True for name in BASELINE)
    )


def run_object(kernel: Path, output: Path, report: Path, name: str,
               env: dict[str, str], timeout: int) -> dict:
    if name not in EXTRA_OBJECTS or not name.endswith(".o"):
        raise ValueError("Unexpected build target: " + name)
    if not (kernel / name[:-2] + ".c").is_file():
        raise ValueError("Pinned E404 object source missing: " + name)
    log_file = report / (name.replace("/", "_") + ".log")
    command = [
        "make", "-C", str(kernel), "O=" + str(output), "ARCH=arm64",
        "CC=clang", "LD=ld.lld", "HOSTCC=gcc",
        "CROSS_COMPILE=aarch64-linux-gnu-",
        "CLANG_TRIPLE=aarch64-linux-gnu-", "-j2", name,
    ]
    with log_file.open("w", encoding="utf-8") as log:
        try:
            p = subprocess.run(command, env=env, stdout=log,
                               stderr=subprocess.STDOUT, timeout=timeout,
                               check=False)
            rc = p.returncode
        except subprocess.TimeoutExpired:
            rc = 124
            log.write("\nEXP76_STAGE30_OBJECT_TIMEOUT\n")
    captured = log_file.read_text(encoding="utf-8", errors="replace")
    errors = diagnostic_lines(captured)
    (report / (name.replace("/", "_") + ".errors.txt")).write_text(
        "\n".join(errors) + "\n", encoding="utf-8"
    )
    return {"attempted": True, "compiled": rc == 0, "exit_code": rc,
            "errors_excerpt": errors}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kernel", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--baseline-report", required=True, type=Path)
    parser.add_argument("--clang-bin", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=140)
    args = parser.parse_args()
    kernel = args.kernel.resolve()
    output = args.output.resolve()
    report = args.report.resolve()
    clang = args.clang_bin.resolve()
    if not (kernel / ".git").is_dir():
        raise ValueError("Expected pinned E404 trial Git checkout")
    if not (output / "include/generated/asm-offsets.h").is_file():
        raise ValueError("arm64 make prepare must complete before Stage30")
    if not (clang / "clang").is_file() or not (clang / "ld.lld").is_file():
        raise ValueError("Pinned Clang21 tools absent")
    if args.timeout < 10 or args.timeout > 180:
        raise ValueError("Unsupported per-object timeout")
    report.mkdir(parents=True, exist_ok=True)
    core_file = kernel / "kernel/sched/core.c"
    contract = inspect_migration(core_file.read_text(encoding="utf-8"))
    ready = baseline_passed(args.baseline_report)
    targets = {}
    if ready:
        env = dict(os.environ)
        env["PATH"] = str(clang) + os.pathsep + env.get("PATH", "")
        env.update({"ARCH": "arm64", "CC": "clang", "LD": "ld.lld",
                    "HOSTCC": "gcc", "LLVM_IAS": "1"})
        for name in EXTRA_OBJECTS:
            targets[name] = run_object(kernel, output, report, name, env, args.timeout)
    else:
        for name in EXTRA_OBJECTS:
            targets[name] = {
                "attempted": False, "compiled": False,
                "exit_code": None, "skip_reason": "BASELINE_3_OBJECT_GATE_FAILED",
                "errors_excerpt": [],
            }
    for prohibited in (
        output / "arch/arm64/boot/Image",
        output / "arch/arm64/boot/Image.gz",
        output / "vmlinux",
        output / "boot.img",
    ):
        if prohibited.exists():
            raise ValueError("Unexpected kernel image or link product: " + str(prohibited))
    status = {
        "stage": "EXP76_STAGE30_RT_OBJECT_COVERAGE_NONFLASH",
        "baseline_3_objects_compiled": ready,
        "migration_contract": contract,
        "targets": targets,
        "objects_attempted": sum(v["attempted"] for v in targets.values()),
        "objects_compiled": sum(v["compiled"] for v in targets.values()),
        "all_extra_objects_compiled": ready and all(v["compiled"] for v in targets.values()),
        "link_performed": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    (report / "OBJECT_COVERAGE.json").write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "stage": status["stage"], "baseline_3_objects_compiled": ready,
        "objects_attempted": status["objects_attempted"],
        "objects_compiled": status["objects_compiled"],
        "migration_contract": contract,
        "flash_ready": False,
    }, indent=2))


if __name__ == "__main__":
    main()
