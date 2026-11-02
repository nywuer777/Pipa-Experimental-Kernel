#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Clang21 cross-subsystem object diagnostics / NO FLASH
"""Compile nine more RT-sensitive objects only after all 12 earlier objects pass.

Exact object targets, no aggregate link, no kernel boot products, and bounded
per-object logs. A success is object compilation, NOT a runnable RT kernel.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

BASELINE = ("kernel_sched_cpupri.o", "kernel_sched_core.o", "kernel_fork.o")
PRIOR_TARGETS = (
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
CROSS_TARGETS = (
    "kernel/sched/wait.o",
    "kernel/sched/swait.o",
    "kernel/locking/mutex.o",
    "kernel/locking/rwsem.o",
    "kernel/locking/spinlock.o",
    "kernel/rcu/update.o",
    "kernel/rcu/tree.o",
    "kernel/irq/manage.o",
    "kernel/workqueue.o",
)
OUTPUT_FILE = "OBJECT_COVERAGE_CROSS_SUBSYSTEM.json"
DIAGNOSTIC = re.compile(
    r"fatal error:|(?<![a-z])error:|warning:|undefined reference|"
    r"No rule to make target|\bError\s+\d+\b", re.IGNORECASE
)
PROHIBITED = (
    "vmlinux", "boot.img", "arch/arm64/boot/Image",
    "arch/arm64/boot/Image.gz", "arch/arm64/boot/Image.gz-dtb",
)


def read_json(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > 512 * 1024:
        raise ValueError("Missing or oversized prerequisite: " + str(path))
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected JSON object: " + str(path))
    return value


def check_no_images(out: Path) -> None:
    for filename in PROHIBITED:
        if (out / filename).exists():
            raise ValueError("Forbidden boot/link artifact found: " + filename)


def gate_prior(baseline_file: Path, coverage_file: Path) -> bool:
    baseline = read_json(baseline_file)
    coverage = read_json(coverage_file)
    if baseline.get("config_preempt_rt_full") is not True:
        return False
    baseline_targets = baseline.get("targets") or {}
    if not isinstance(baseline_targets, dict) or not all(
        isinstance(baseline_targets.get(name), dict)
        and baseline_targets[name].get("attempted") is True
        and baseline_targets[name].get("compiled") is True
        and baseline_targets[name].get("exit_code") == 0
        for name in BASELINE
    ):
        return False
    if coverage.get("stage") != "EXP76_STAGE30_RT_OBJECT_COVERAGE_NONFLASH" or (
        coverage.get("baseline_3_objects_compiled") is not True
    ):
        return False
    targets = coverage.get("targets") or {}
    if not isinstance(targets, dict) or set(targets) != set(PRIOR_TARGETS):
        return False
    return (
        coverage.get("all_extra_objects_compiled") is True
        and coverage.get("objects_attempted") == len(PRIOR_TARGETS)
        and coverage.get("objects_compiled") == len(PRIOR_TARGETS)
        and all(isinstance(v, dict)
                and v.get("attempted") is True
                and v.get("compiled") is True
                and v.get("exit_code") == 0
                for v in targets.values())
    )


def compile_one(kernel: Path, out: Path, report: Path, target: str,
                environment: dict[str, str], timeout: int) -> dict:
    if target not in CROSS_TARGETS or not target.endswith(".o"):
        raise ValueError("Disallowed object target: " + target)
    if not (kernel / (target[:-2] + ".c")).is_file():
        raise ValueError("Pinned E404 source is missing: " + target)
    log_path = report / (target.replace("/", "_") + ".log")
    command = [
        "make", "-C", str(kernel), "O=" + str(out), "ARCH=arm64",
        "CC=clang", "LD=ld.lld", "HOSTCC=gcc",
        "CROSS_COMPILE=aarch64-linux-gnu-",
        "CLANG_TRIPLE=aarch64-linux-gnu-", "-j2", target,
    ]
    with log_path.open("w", encoding="utf-8") as log:
        try:
            proc = subprocess.run(command, env=environment, stdout=log,
                                  stderr=subprocess.STDOUT, timeout=timeout,
                                  check=False)
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            rc = 124
            log.write("\nEXP76_STAGE46_OBJECT_TIMEOUT\n")
    transcript = log_path.read_text(encoding="utf-8", errors="replace")
    errors = [
        line.strip()[:400] for line in transcript.splitlines()
        if DIAGNOSTIC.search(line)
    ][:24]
    (report / (target.replace("/", "_") + ".errors.txt")).write_text(
        "\n".join(errors) + "\n", encoding="utf-8"
    )
    check_no_images(out)
    return {
        "attempted": True, "compiled": rc == 0, "exit_code": rc,
        "errors_excerpt": errors,
    }


def execute(kernel: Path, out: Path, report: Path, baseline_file: Path,
            coverage_file: Path, clang_bin: Path, timeout: int) -> dict:
    if timeout < 15 or timeout > 150:
        raise ValueError("Unsupported per-object timeout")
    if len(CROSS_TARGETS) != len(set(CROSS_TARGETS)) or len(CROSS_TARGETS) != 9:
        raise ValueError("Unexpected cross-subsystem target list")
    if not (kernel / ".git").is_dir():
        raise ValueError("Expected isolated E404 git checkout")
    if not (clang_bin / "clang").is_file() or not (clang_bin / "ld.lld").is_file():
        raise ValueError("Pinned Android Clang 21 toolchain is absent")
    if not (out / ".config").is_file() or "CONFIG_PREEMPT_RT_FULL=y" not in (
        out / ".config"
    ).read_text(encoding="utf-8").splitlines():
        raise ValueError("Expected explicit CONFIG_PREEMPT_RT_FULL=y")
    if not (out / "include/generated/asm-offsets.h").is_file():
        raise ValueError("Missing arm64 make prepare generated offsets")
    if len(list(kernel.rglob("*.rej"))) != 64:
        raise ValueError("Expected 64 still-rejected RT files")
    for target in CROSS_TARGETS:
        if not (kernel / (target[:-2] + ".c")).is_file():
            raise ValueError("Missing E404 source: " + target)
    check_no_images(out)
    good = gate_prior(baseline_file, coverage_file)
    report.mkdir(parents=True, exist_ok=True)
    targets = {}
    if good:
        env = dict(os.environ)
        env["PATH"] = str(clang_bin) + os.pathsep + env.get("PATH", "")
        env.update({"ARCH": "arm64", "CC": "clang", "LD": "ld.lld",
                    "HOSTCC": "gcc", "LLVM_IAS": "1"})
        for target in CROSS_TARGETS:
            targets[target] = compile_one(kernel, out, report, target, env, timeout)
    else:
        for target in CROSS_TARGETS:
            targets[target] = {
                "attempted": False, "compiled": False,
                "exit_code": None, "skip_reason": "PRIOR_12_OBJECT_GATE_FAILED",
                "errors_excerpt": [],
            }
    check_no_images(out)
    completed = sum(v["compiled"] for v in targets.values())
    status = {
        "stage": "EXP76_STAGE46_RT_CROSS_SUBSYSTEM_OBJECTS_NONFLASH",
        "baseline_12_objects_compiled": good,
        "targets": targets,
        "objects_attempted": sum(v["attempted"] for v in targets.values()),
        "objects_compiled": completed,
        "all_cross_objects_compiled": good and completed == len(CROSS_TARGETS),
        "remaining_rejected_files": 64,
        "compiler": "Pinned Android Clang 21",
        "link_performed": False,
        "runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    (report / OUTPUT_FILE).write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8"
    )
    return status


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--kernel", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--baseline-report", type=Path, required=True)
    p.add_argument("--prior-coverage", type=Path, required=True)
    p.add_argument("--clang-bin", type=Path, required=True)
    p.add_argument("--timeout", type=int, default=100)
    a = p.parse_args()
    status = execute(a.kernel.resolve(), a.output.resolve(), a.report.resolve(),
                     a.baseline_report.resolve(), a.prior_coverage.resolve(),
                     a.clang_bin.resolve(), a.timeout)
    print(json.dumps({
        "stage": status["stage"],
        "baseline_12_objects_compiled": status["baseline_12_objects_compiled"],
        "objects_attempted": status["objects_attempted"],
        "objects_compiled": status["objects_compiled"],
        "kernel_built": False,
        "flash_ready": False,
    }, indent=2))


if __name__ == "__main__":
    main()
