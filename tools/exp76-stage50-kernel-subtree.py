#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 GitHub Actions / EXP76 Stage50 bounded kernel subtree Kbuild archive / NO FLASH
"""Build kernel/built-in.a ONLY after 22 RT objects compile.

Kbuild archive is not vmlinux, Image or a bootable kernel. Preserve the
first actual integrated compile error; never turn failure into success or
create installable artifacts. The source tree is the isolated E404 overlay.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

BASE = ("kernel_sched_cpupri.o", "kernel_sched_core.o", "kernel_fork.o")
PRIOR = (
    "kernel/sched/rt.o", "kernel/sched/fair.o", "kernel/sched/deadline.o",
    "kernel/sched/idle.o", "kernel/sched/stop_task.o", "kernel/cpu.o",
    "kernel/locking/rtmutex.o", "kernel/softirq.o", "kernel/time/timer.o",
)
CROSS = (
    "kernel/sched/wait.o", "kernel/sched/swait.o",
    "kernel/locking/mutex-rt.o", "kernel/locking/rwsem-rt.o",
    "kernel/locking/rwlock-rt.o", "kernel/locking/spinlock.o",
    "kernel/rcu/update.o", "kernel/rcu/tree.o",
    "kernel/irq/manage.o", "kernel/workqueue.o",
)
TARGET = "kernel/built-in.a"
OUTPUT = "KERNEL_SUBTREE_DIAGNOSTIC.json"
BAD_ARTIFACTS = (
    "vmlinux", "vmlinux.o", "System.map", "boot.img",
    "arch/arm64/boot/Image", "arch/arm64/boot/Image.gz",
    "arch/arm64/boot/Image.gz-dtb",
)
ERROR = re.compile(
    r"fatal error:|(?<![a-z])error:|undefined reference|"
    r"No rule to make target|missing separator|"
    r"\bError\s+\d+\b|Killed\b", re.I,
)


def read(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > 512 * 1024:
        raise ValueError("Missing or oversized compilation evidence: " + str(path))
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Invalid compilation evidence JSON")
    return value


def all_passed(baseline: Path, prior: Path, cross: Path) -> bool:
    a, b, c = read(baseline), read(prior), read(cross)
    if a.get("config_preempt_rt_full") is not True:
        return False
    if (b.get("stage") != "EXP76_STAGE30_RT_OBJECT_COVERAGE_NONFLASH"
            or b.get("all_extra_objects_compiled") is not True
            or b.get("baseline_3_objects_compiled") is not True
            or b.get("objects_compiled") != 9
            or b.get("objects_attempted") != 9):
        return False
    if (c.get("stage") != "EXP76_STAGE46_RT_CROSS_SUBSYSTEM_OBJECTS_NONFLASH"
            or c.get("baseline_12_objects_compiled") is not True
            or c.get("all_cross_objects_compiled") is not True
            or c.get("objects_compiled") != 10
            or c.get("objects_attempted") != 10
            or c.get("remaining_rejected_files") != 64
            or c.get("link_performed") is not False):
        return False
    for obj, targets in ((BASE, a.get("targets")), (PRIOR, b.get("targets")),
                         (CROSS, c.get("targets"))):
        if not isinstance(targets, dict) or set(targets) != set(obj):
            return False
        if not all(isinstance(v, dict) and v.get("attempted") is True
                   and v.get("compiled") is True and v.get("exit_code") == 0
                   for v in targets.values()):
            return False
    return True


def forbid_images(out: Path) -> None:
    for relative in BAD_ARTIFACTS:
        if (out / relative).exists():
            raise ValueError("Unexpected link or boot artifact: " + relative)


def failure_extract(log: str) -> tuple[list[str], list[str]]:
    lines = log.splitlines()
    important = [x.strip()[:420] for x in lines if ERROR.search(x)][:35]
    first = next((i for i, line in enumerate(lines) if ERROR.search(line)), None)
    context = ([x[:420] for x in lines[max(0, first - 10):first + 8]]
               if first is not None else lines[-22:])
    return important, context[:24]


def execute(kernel: Path, out: Path, report: Path, baseline: Path,
            prior: Path, cross: Path, clang: Path, timeout: int) -> dict:
    if timeout < 60 or timeout > 600:
        raise ValueError("Unsupported subtree compile timeout")
    if not (kernel / ".git").is_dir():
        raise ValueError("Expected isolated E404 git checkout")
    if not all((clang / name).is_file()
               for name in ("clang", "ld.lld", "llvm-ar")):
        raise ValueError("Pinned Android Clang21 compiler/linker/archiver absent")
    if not (out / "include/generated/asm-offsets.h").is_file():
        raise ValueError("Missing generated arm64 offsets")
    config = out / ".config"
    if not config.is_file() or "CONFIG_PREEMPT_RT_FULL=y" not in config.read_text(
        encoding="utf-8"
    ).splitlines():
        raise ValueError("PREEMPT_RT_FULL not established in Kbuild config")
    if len(list(kernel.rglob("*.rej"))) != 64:
        raise ValueError("Expected 64 unresolved RT rejects")
    rules = kernel / "scripts/Makefile.build"
    if not rules.is_file() or (
        "$(obj)/built-in.a: $(real-obj-y) FORCE"
        not in rules.read_text(encoding="utf-8")
    ):
        raise ValueError("Pinned archive construction rule not found")
    if not (kernel / "kernel/Makefile").is_file():
        raise ValueError("kernel/ Kbuild Makefile is missing")
    forbid_images(out)
    ready = all_passed(baseline, prior, cross)
    report.mkdir(parents=True, exist_ok=True)
    archive = out / TARGET
    info = {
        "stage": "EXP76_STAGE50_KERNEL_SUBTREE_KBUILD_ARCHIVE_NONFLASH",
        "target": TARGET,
        "baseline_22_objects_compiled": ready,
        "attempted": ready,
        "exit_code": None,
        "archive_created": False,
        "archive_bytes": 0,
        "skip_reason": None if ready else "BASELINE_22_OBJECT_GATE_FAILED",
        "errors_excerpt": [],
        "first_error_context": [],
        "remaining_rejected_files": 64,
        "full_kernel_link_performed": False,
        "runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    if ready:
        env = dict(os.environ)
        env["PATH"] = str(clang) + os.pathsep + env.get("PATH", "")
        env.update({"ARCH": "arm64", "CC": "clang", "LD": "ld.lld",
                    "HOSTCC": "gcc", "LLVM_IAS": "1"})
        cmd = [
            "make", "-C", str(kernel), "O=" + str(out), "ARCH=arm64",
            "CC=clang", "LD=ld.lld", "HOSTCC=gcc",
            "CROSS_COMPILE=aarch64-linux-gnu-",
            "CLANG_TRIPLE=aarch64-linux-gnu-", "-j2", TARGET,
        ]
        log_path = report / "kernel_subtree_make.log"
        with log_path.open("w", encoding="utf-8") as stream:
            try:
                completed = subprocess.run(
                    cmd, env=env, stdout=stream,
                    stderr=subprocess.STDOUT, timeout=timeout, check=False
                )
                rc = completed.returncode
            except subprocess.TimeoutExpired:
                rc = 124
                stream.write("\nEXP76_STAGE50_KERNEL_SUBTREE_TIMEOUT\n")
        log = log_path.read_text(encoding="utf-8", errors="replace")
        errors, context = failure_extract(log)
        created = archive.is_file() and archive.stat().st_size > 0
        info.update({
            "exit_code": rc,
            "archive_created": rc == 0 and created,
            "archive_bytes": archive.stat().st_size if created else 0,
            "errors_excerpt": errors,
            "first_error_context": context,
        })
        if rc == 0 and not created:
            info["errors_excerpt"].append(
                "make returned 0 but kernel/built-in.a was not created"
            )
    forbid_images(out)
    (report / OUTPUT).write_text(json.dumps(info, indent=2) + "\n",
                                 encoding="utf-8")
    return info


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--kernel", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--baseline-report", type=Path, required=True)
    p.add_argument("--prior-coverage", type=Path, required=True)
    p.add_argument("--cross-coverage", type=Path, required=True)
    p.add_argument("--clang-bin", type=Path, required=True)
    p.add_argument("--timeout", type=int, default=450)
    a = p.parse_args()
    status = execute(
        a.kernel.resolve(), a.output.resolve(), a.report.resolve(),
        a.baseline_report.resolve(), a.prior_coverage.resolve(),
        a.cross_coverage.resolve(), a.clang_bin.resolve(), a.timeout,
    )
    print(json.dumps({
        "stage": status["stage"], "target": status["target"],
        "attempted": status["attempted"],
        "exit_code": status["exit_code"],
        "archive_created": status["archive_created"],
        "errors_excerpt": status["errors_excerpt"][:8],
        "kernel_built": False, "flash_ready": False,
    }, indent=2))


if __name__ == "__main__":
    main()
