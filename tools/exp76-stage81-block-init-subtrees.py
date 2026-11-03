#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage81 BLOCK+INIT Kbuild / NO FLASH
"""Compile Kbuild-scoped block and init archives after verified DRIVER subtree.

Checks pinned E404 arm64 rules, actual 64 rejected RT patch files and previous
archive reports. Always reports both scoped build outcomes, even if one fails.
Never links vmlinux, builds Image/boot.img or writes tablet partitions.
"""
from __future__ import annotations

import argparse
import json
import os
import runpy
import subprocess
from pathlib import Path

STAGE76 = runpy.run_path(
    str(Path(__file__).with_name("exp76-stage76-drivers-subtree.py")),
    run_name="exp76_stage76_helpers",
)
STAGE50 = STAGE76["STAGE50"]
STAGE = "EXP76_STAGE81_BLOCK_INIT_SCOPED_ARCHIVES_NONFLASH"
OUTPUT = "BLOCK_INIT_SUBTREES_DIAGNOSTIC.json"
TARGETS = ("block/built-in.a", "init/built-in.a")


def prerequisites(report76: Path, report77: Path, report79: Path, out: Path) -> bool:
    drivers = STAGE50["read"](report76)
    version = STAGE50["read"](report77)
    functionfs = STAGE50["read"](report79)
    archive = out / STAGE76["TARGET"]
    header = out / "include/generated/compile.h"
    version_obj = out / "init/version.o"
    return bool(
        drivers.get("stage") == STAGE76["STAGE"]
        and drivers.get("target") == STAGE76["TARGET"]
        and drivers.get("top_level_directory_scope") == STAGE76["SCOPE"]
        and drivers.get("prior_crypto_subtree_gate") is True
        and drivers.get("attempted") is True
        and drivers.get("exit_code") == 0
        and drivers.get("timed_out") is False
        and drivers.get("archive_created") is True
        and drivers.get("archive_has_members") is True
        and drivers.get("archive_inspection_exit_code") == 0
        and type(drivers.get("archive_members_count")) is int
        and drivers["archive_members_count"] > 0
        and type(drivers.get("archive_bytes")) is int
        and drivers["archive_bytes"] > 8
        and drivers.get("remaining_rejected_files") == 64
        and drivers.get("full_kernel_link_performed") is False
        and drivers.get("kernel_built") is False
        and drivers.get("flash_ready") is False
        and archive.is_file()
        and archive.stat().st_size == drivers["archive_bytes"]
        and version.get("stage") == "EXP76_STAGE77_KBUILD_COMPILE_H_INIT_VERSION_NONFLASH"
        and version.get("target") == "init/version.o"
        and version.get("generated_header") == "include/generated/compile.h"
        and version.get("prior_crypto_subtree_gate") is True
        and version.get("exit_code") == 0
        and version.get("timed_out") is False
        and version.get("compile_h_created") is True
        and version.get("compile_h_anchors_valid") is True
        and version.get("init_version_object_created") is True
        and version.get("remaining_rejected_files") == 64
        and version.get("full_kernel_link_performed") is False
        and version.get("kernel_built") is False
        and version.get("flash_ready") is False
        and header.is_file()
        and header.stat().st_size == version.get("compile_h_bytes")
        and version_obj.is_file()
        and version_obj.stat().st_size > 0
        and functionfs.get("stage") ==
            "EXP76_STAGE79_FUNCTIONFS_RT_COMPLETION_SWAIT_NONFLASH"
        and functionfs.get("target") == "drivers/usb/gadget/function/f_fs.c"
        and functionfs.get("applied") is True
        and functionfs.get("rt_completion_swait_used") is True
        and functionfs.get("nonrt_waitqueue_preserved") is True
        and functionfs.get("normal_waitqueue_checks_preserved") is True
        and functionfs.get("completion_lifecycle_preserved") is True
        and functionfs.get("remaining_rejected_files") == 64
        and functionfs.get("full_kernel_link_performed") is False
        and functionfs.get("kernel_built") is False
        and functionfs.get("flash_ready") is False
    )


def execute(kernel: Path, out: Path, report: Path, stage76: Path,
            stage77: Path, stage79: Path, clang: Path, timeout: int) -> dict:
    if not (60 <= timeout <= 600):
        raise ValueError("Stage81 requires 60..600 second per-target timeout")
    if not (kernel / ".git").is_dir():
        raise ValueError("Stage81 requires isolated E404 trial git checkout")
    for dirname in ("block", "init"):
        if not (kernel / dirname / "Makefile").is_file():
            raise ValueError("Pinned E404 Makefile missing: " + dirname)
    rules = kernel / "scripts/Makefile.build"
    if not rules.is_file() or rules.read_text(encoding="utf-8").count(
        "$(obj)/built-in.a: $(real-obj-y) FORCE"
    ) != 1:
        raise ValueError("Pinned E404 Kbuild archive rule drift")
    top = kernel / "Makefile"
    if not top.is_file():
        raise ValueError("Pinned E404 root Makefile missing")
    contents = top.read_text(encoding="utf-8")
    for anchor in STAGE50["ROOT_KBUILD_ANCHORS"]:
        if contents.count(anchor) != 1:
            raise ValueError("Pinned E404 root directory dependency drift")
    cfg = out / ".config"
    if not cfg.is_file():
        raise ValueError("Stage81 requires real RT .config")
    options = set(cfg.read_text(encoding="utf-8").splitlines())
    for item in ("CONFIG_PREEMPT_RT_FULL=y", "CONFIG_BLOCK=y"):
        if item not in options:
            raise ValueError("Stage81 requires PREEMPT_RT and CONFIG_BLOCK=y")
    if not (out / "include/generated/asm-offsets.h").is_file():
        raise ValueError("Stage81 arm64 prepare gate missing")
    if len(list(kernel.rglob("*.rej"))) != 64:
        raise ValueError("Stage81 requires exactly 64 outstanding RT rejects")
    if not all((clang / binary).is_file() for binary in
               ("clang", "ld.lld", "llvm-ar")):
        raise ValueError("Stage81 pinned Clang21 toolchain incomplete")
    if not prerequisites(stage76, stage77, stage79, out):
        raise ValueError("Stage81 DRIVERS/compile.h/FunctionFS provenance gates incomplete")
    STAGE50["forbid_images"](out)
    report.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PATH"] = str(clang) + os.pathsep + env.get("PATH", "")
    env.update({
        "ARCH": "arm64", "CC": "clang", "LD": "ld.lld",
        "HOSTCC": "gcc", "LLVM_IAS": "1",
    })
    outcomes = {}
    for target in TARGETS:
        name = target.split("/")[0]
        command = [
            "make", "-C", str(kernel), "O=" + str(out),
            "ARCH=arm64", "CC=clang", "LD=ld.lld", "HOSTCC=gcc",
            "CROSS_COMPILE=aarch64-linux-gnu-",
            "CLANG_TRIPLE=aarch64-linux-gnu-",
            "-j2", "vmlinux-dirs=" + name, target,
        ]
        log = report / (name + "_make.log")
        with log.open("w", encoding="utf-8") as stream:
            try:
                rc = subprocess.run(
                    command, env=env, stdout=stream,
                    stderr=subprocess.STDOUT, timeout=timeout, check=False,
                ).returncode
            except subprocess.TimeoutExpired:
                rc = 124
                stream.write(f"\nEXP76_STAGE81_{name.upper()}_TIMEOUT\n")
        errors, context = STAGE50["failure_extract"](
            log.read_text(encoding="utf-8", errors="replace")
        )
        archive = out / target
        present = archive.is_file() and archive.stat().st_size > 0
        size = archive.stat().st_size if present else 0
        members = []
        ar_rc = None
        if rc == 0 and present:
            try:
                ar = subprocess.run(
                    [str(clang / "llvm-ar"), "t", str(archive)],
                    capture_output=True, text=True, timeout=30, check=False,
                )
                ar_rc = ar.returncode
                if ar_rc == 0:
                    members = [x for x in ar.stdout.splitlines() if x.strip()]
                else:
                    errors.append(
                        "llvm-ar failed for " + name + ": " +
                        ar.stderr.strip()[:400]
                    )
            except subprocess.TimeoutExpired:
                ar_rc = 124
                errors.append("llvm-ar timed out for " + name)
        if rc == 0 and not present:
            errors.append(f"make returned zero without creating {target}")
        if rc == 0 and present and not members:
            errors.append(f"{target} lacks verified object members")
        outcomes[name] = {
            "target": target,
            "directory_scope": "vmlinux-dirs=" + name,
            "attempted": True,
            "exit_code": rc,
            "timed_out": rc == 124,
            "archive_created": rc == 0 and present,
            "archive_bytes": size,
            "archive_inspection_exit_code": ar_rc,
            "archive_has_members": rc == 0 and ar_rc == 0 and bool(members),
            "archive_members_count": len(members),
            "archive_members_sample": members[:20],
            "errors_excerpt": errors[:25],
            "first_error_context": context[:24],
        }
        STAGE50["forbid_images"](out)
    result = {
        "stage": STAGE,
        "prior_drivers_subtree_gate": True,
        "prior_compile_h_gate": True,
        "prior_functionfs_rt_gate": True,
        "targets": outcomes,
        "all_archives_verified": all(
            outcome["archive_has_members"] and outcome["exit_code"] == 0
            for outcome in outcomes.values()
        ),
        "remaining_rejected_files": 64,
        "full_kernel_link_performed": False,
        "runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    STAGE50["forbid_images"](out)
    (report / OUTPUT).write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--kernel", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    for n in (76, 77, 79):
        p.add_argument(f"--stage{n}-report", required=True, type=Path)
    p.add_argument("--clang-bin", required=True, type=Path)
    p.add_argument("--timeout", type=int, default=570)
    a = p.parse_args()
    result = execute(
        a.kernel.resolve(), a.output.resolve(), a.report.resolve(),
        a.stage76_report.resolve(), a.stage77_report.resolve(),
        a.stage79_report.resolve(), a.clang_bin.resolve(), a.timeout,
    )
    print(json.dumps({
        "stage": STAGE,
        "all_archives_verified": result["all_archives_verified"],
        "targets": {
            name: {
                "exit_code": obj["exit_code"],
                "timed_out": obj["timed_out"],
                "archive_has_members": obj["archive_has_members"],
                "archive_members_count": obj["archive_members_count"],
                "errors_excerpt": obj["errors_excerpt"][:5],
            } for name, obj in result["targets"].items()
        },
        "kernel_built": False,
        "flash_ready": False,
    }, indent=2))


if __name__ == "__main__":
    main()
