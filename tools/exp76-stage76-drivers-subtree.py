#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage76 DRIVERS Kbuild / NO FLASH
"""Bounded drivers/built-in.a diagnostic after verified CRYPTO subtree.

The driver tree is compiled in isolation, without full linking, boot artifacts
or flashing. Preserve the 64 RT rejects. Capture first Clang/Make errors and
inspect the archive with pinned llvm-ar only on a successful make.
"""
from __future__ import annotations

import argparse
import json
import os
import runpy
import subprocess
from pathlib import Path

STAGE75 = runpy.run_path(
    str(Path(__file__).with_name("exp76-stage75-crypto-subtree.py")),
    run_name="exp76_stage75_helpers",
)
STAGE50 = STAGE75["STAGE50"]
STAGE = "EXP76_STAGE76_DRIVERS_SUBTREE_KBUILD_ARCHIVE_NONFLASH"
TARGET = "drivers/built-in.a"
SCOPE = "vmlinux-dirs=drivers"
OUTPUT = "DRIVERS_SUBTREE_DIAGNOSTIC.json"


def prerequisites(stage50: Path, stage66: Path, stage67: Path,
                  stage68: Path, stage69: Path, stage72: Path,
                  stage73: Path, stage75: Path, out: Path) -> bool:
    if not STAGE75["prerequisites"](
        stage50, stage66, stage67, stage68, stage69, stage72, stage73, out
    ):
        return False
    crypto = STAGE50["read"](stage75)
    archive = out / STAGE75["TARGET"]
    return bool(
        crypto.get("stage") == STAGE75["STAGE"]
        and crypto.get("target") == STAGE75["TARGET"]
        and crypto.get("top_level_directory_scope") == STAGE75["SCOPE"]
        and crypto.get("prior_lib_subtree_gate") is True
        and crypto.get("attempted") is True
        and crypto.get("exit_code") == 0
        and crypto.get("timed_out") is False
        and crypto.get("archive_created") is True
        and crypto.get("archive_has_members") is True
        and crypto.get("archive_inspection_exit_code") == 0
        and isinstance(crypto.get("archive_members_count"), int)
        and crypto["archive_members_count"] > 0
        and isinstance(crypto.get("archive_bytes"), int)
        and crypto["archive_bytes"] > 8
        and crypto.get("remaining_rejected_files") == 64
        and crypto.get("full_kernel_link_performed") is False
        and crypto.get("kernel_built") is False
        and crypto.get("flash_ready") is False
        and archive.is_file()
        and archive.stat().st_size == crypto["archive_bytes"]
    )


def execute(kernel: Path, out: Path, report: Path, stage50: Path,
            stage66: Path, stage67: Path, stage68: Path, stage69: Path,
            stage72: Path, stage73: Path, stage75: Path, clang: Path,
            timeout: int) -> dict:
    if timeout < 60 or timeout > 600:
        raise ValueError("Unsupported Stage76 DRIVERS compile timeout")
    if not (kernel / ".git").is_dir():
        raise ValueError("Stage76 requires isolated E404 trial git checkout")
    if not (kernel / "drivers/Makefile").is_file():
        raise ValueError("Pinned E404 drivers/Makefile missing")
    rules = kernel / "scripts/Makefile.build"
    if not rules.is_file() or rules.read_text(encoding="utf-8").count(
        "$(obj)/built-in.a: $(real-obj-y) FORCE"
    ) != 1:
        raise ValueError("Pinned E404 archive rule drift")
    top = kernel / "Makefile"
    if not top.is_file():
        raise ValueError("Pinned E404 root Makefile missing")
    root_make = top.read_text(encoding="utf-8")
    for anchor in STAGE50["ROOT_KBUILD_ANCHORS"]:
        if root_make.count(anchor) != 1:
            raise ValueError("Pinned E404 directory dependency drift")
    if not (out / "include/generated/asm-offsets.h").is_file():
        raise ValueError("Stage76 arm64 prepare prerequisite missing")
    config = out / ".config"
    if not config.is_file():
        raise ValueError("Stage76 requires pinned pipa RT configuration")
    options = set(config.read_text(encoding="utf-8").splitlines())
    for option in ("CONFIG_PREEMPT_RT_FULL=y", "CONFIG_SECURITY=y",
                   "CONFIG_NET=y", "CONFIG_CRYPTO=y"):
        if option not in options:
            raise ValueError("Stage76 requires PREEMPT_RT and prior enabled subsystems")
    if not all((clang / name).is_file()
               for name in ("clang", "ld.lld", "llvm-ar")):
        raise ValueError("Pinned Clang21 toolchain incomplete")
    if len(list(kernel.rglob("*.rej"))) != 64:
        raise ValueError("Stage76 requires 64 outstanding RT rejects")
    if not prerequisites(
        stage50, stage66, stage67, stage68, stage69, stage72, stage73,
        stage75, out,
    ):
        raise ValueError("Stage50/66/67/68/69/72/73/75 archive gates incomplete")
    STAGE50["forbid_images"](out)
    report.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PATH"] = str(clang) + os.pathsep + env.get("PATH", "")
    env.update({
        "ARCH": "arm64", "CC": "clang", "LD": "ld.lld",
        "HOSTCC": "gcc", "LLVM_IAS": "1",
    })
    command = [
        "make", "-C", str(kernel), "O=" + str(out),
        "ARCH=arm64", "CC=clang", "LD=ld.lld", "HOSTCC=gcc",
        "CROSS_COMPILE=aarch64-linux-gnu-",
        "CLANG_TRIPLE=aarch64-linux-gnu-", "-j2", SCOPE, TARGET,
    ]
    log = report / "drivers_subtree_make.log"
    with log.open("w", encoding="utf-8") as stream:
        try:
            rc = subprocess.run(
                command, env=env, stdout=stream, stderr=subprocess.STDOUT,
                timeout=timeout, check=False,
            ).returncode
        except subprocess.TimeoutExpired:
            rc = 124
            stream.write("\nEXP76_STAGE76_DRIVERS_SUBTREE_TIMEOUT\n")
    errors, context = STAGE50["failure_extract"](
        log.read_text(encoding="utf-8", errors="replace")
    )
    archive = out / TARGET
    exists = archive.is_file() and archive.stat().st_size > 0
    size = archive.stat().st_size if exists else 0
    ar_status = None
    members: list[str] = []
    if rc == 0 and exists:
        try:
            inspection = subprocess.run(
                [str(clang / "llvm-ar"), "t", str(archive)],
                capture_output=True, text=True, timeout=30, check=False,
            )
            ar_status = inspection.returncode
            if ar_status == 0:
                members = [
                    item for item in inspection.stdout.splitlines()
                    if item.strip()
                ]
            else:
                errors.append(
                    "llvm-ar t rejected DRIVERS archive: " +
                    inspection.stderr.strip()[:400]
                )
        except subprocess.TimeoutExpired:
            ar_status = 124
            errors.append("llvm-ar t timed out inspecting DRIVERS archive")
    if rc == 0 and not exists:
        errors.append("make returned 0 without creating drivers/built-in.a")
    if rc == 0 and exists and not members:
        errors.append("DRIVERS archive has no verified object members")
    status = {
        "stage": STAGE,
        "target": TARGET,
        "top_level_directory_scope": SCOPE,
        "prior_kernel_subtree_gate": True,
        "prior_mm_subtree_gate": True,
        "prior_fs_subtree_gate": True,
        "prior_ipc_subtree_gate": True,
        "prior_security_subtree_gate": True,
        "prior_net_subtree_gate": True,
        "prior_lib_subtree_gate": True,
        "prior_crypto_subtree_gate": True,
        "attempted": True,
        "exit_code": rc,
        "timed_out": rc == 124,
        "archive_created": rc == 0 and exists,
        "archive_bytes": size,
        "archive_inspection_exit_code": ar_status,
        "archive_has_members": rc == 0 and ar_status == 0 and bool(members),
        "archive_members_count": len(members),
        "archive_members_sample": members[:24],
        "errors_excerpt": errors[:25],
        "first_error_context": context[:30],
        "remaining_rejected_files": 64,
        "full_kernel_link_performed": False,
        "runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    STAGE50["forbid_images"](out)
    (report / OUTPUT).write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8"
    )
    return status


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    for stage in (50, 66, 67, 68, 69, 72, 73, 75):
        parser.add_argument(f"--stage{stage}-report", type=Path, required=True)
    parser.add_argument("--clang-bin", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=570)
    args = parser.parse_args()
    result = execute(
        args.kernel.resolve(), args.output.resolve(), args.report.resolve(),
        args.stage50_report.resolve(), args.stage66_report.resolve(),
        args.stage67_report.resolve(), args.stage68_report.resolve(),
        args.stage69_report.resolve(), args.stage72_report.resolve(),
        args.stage73_report.resolve(), args.stage75_report.resolve(),
        args.clang_bin.resolve(), args.timeout,
    )
    print(json.dumps({
        "stage": result["stage"],
        "target": result["target"],
        "archive_created": result["archive_created"],
        "archive_has_members": result["archive_has_members"],
        "archive_members_count": result["archive_members_count"],
        "exit_code": result["exit_code"],
        "timed_out": result["timed_out"],
        "errors_excerpt": result["errors_excerpt"][:8],
        "kernel_built": False,
        "flash_ready": False,
    }, indent=2))


if __name__ == "__main__":
    main()
