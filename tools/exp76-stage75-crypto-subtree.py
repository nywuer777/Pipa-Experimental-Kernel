#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage75 CRYPTO Kbuild / NO FLASH
"""Compile scoped crypto/built-in.a after validated LIB archive.

Require all earlier RT nonflash gates, pinned E404 Kbuild, CONFIG_CRYPTO=y,
and a real nonempty llvm-ar member listing. No vmlinux, Image or boot.img.
"""
from __future__ import annotations

import argparse
import json
import os
import runpy
import subprocess
from pathlib import Path

STAGE73 = runpy.run_path(
    str(Path(__file__).with_name("exp76-stage73-lib-subtree.py")),
    run_name="exp76_stage73_helpers",
)
STAGE50 = STAGE73["STAGE50"]
STAGE = "EXP76_STAGE75_CRYPTO_SUBTREE_KBUILD_ARCHIVE_NONFLASH"
TARGET = "crypto/built-in.a"
SCOPE = "vmlinux-dirs=crypto"
OUTPUT = "CRYPTO_SUBTREE_DIAGNOSTIC.json"


def prerequisites(stage50: Path, stage66: Path, stage67: Path,
                  stage68: Path, stage69: Path, stage72: Path,
                  stage73: Path, out: Path) -> bool:
    if not STAGE73["prerequisites"](
        stage50, stage66, stage67, stage68, stage69, stage72, out
    ):
        return False
    lib = STAGE50["read"](stage73)
    archive = out / STAGE73["TARGET"]
    return bool(
        lib.get("stage") == STAGE73["STAGE"]
        and lib.get("target") == STAGE73["TARGET"]
        and lib.get("top_level_directory_scope") == STAGE73["SCOPE"]
        and lib.get("prior_net_subtree_gate") is True
        and lib.get("attempted") is True
        and lib.get("exit_code") == 0
        and lib.get("timed_out") is False
        and lib.get("archive_created") is True
        and lib.get("archive_has_members") is True
        and lib.get("archive_inspection_exit_code") == 0
        and isinstance(lib.get("archive_members_count"), int)
        and lib["archive_members_count"] > 0
        and isinstance(lib.get("archive_bytes"), int)
        and lib["archive_bytes"] > 8
        and lib.get("remaining_rejected_files") == 64
        and lib.get("full_kernel_link_performed") is False
        and lib.get("kernel_built") is False
        and lib.get("flash_ready") is False
        and archive.is_file()
        and archive.stat().st_size == lib["archive_bytes"]
    )


def execute(kernel: Path, out: Path, report: Path, stage50: Path,
            stage66: Path, stage67: Path, stage68: Path, stage69: Path,
            stage72: Path, stage73: Path, clang: Path, timeout: int) -> dict:
    if timeout < 60 or timeout > 600:
        raise ValueError("Unsupported Stage75 CRYPTO compile timeout")
    if not (kernel / ".git").is_dir():
        raise ValueError("Stage75 requires isolated E404 trial git checkout")
    if not (kernel / "crypto/Makefile").is_file():
        raise ValueError("Pinned E404 crypto/Makefile missing")
    rules = kernel / "scripts/Makefile.build"
    if not rules.is_file() or rules.read_text(encoding="utf-8").count(
        "$(obj)/built-in.a: $(real-obj-y) FORCE"
    ) != 1:
        raise ValueError("Pinned E404 archive rule drift")
    top = kernel / "Makefile"
    if not top.is_file():
        raise ValueError("Pinned E404 root Makefile missing")
    root_source = top.read_text(encoding="utf-8")
    for anchor in STAGE50["ROOT_KBUILD_ANCHORS"]:
        if root_source.count(anchor) != 1:
            raise ValueError("Pinned E404 top-level directory dependency drift")
    if not (out / "include/generated/asm-offsets.h").is_file():
        raise ValueError("Stage75 arm64 prepare prerequisite missing")
    config = out / ".config"
    if not config.is_file():
        raise ValueError("Stage75 pinned pipa RT config missing")
    options = set(config.read_text(encoding="utf-8").splitlines())
    required = (
        "CONFIG_PREEMPT_RT_FULL=y", "CONFIG_SECURITY=y",
        "CONFIG_NET=y", "CONFIG_CRYPTO=y",
    )
    if not all(option in options for option in required):
        raise ValueError("Stage75 requires PREEMPT_RT, SECURITY, NET, CRYPTO=y")
    if not all((clang / name).is_file()
               for name in ("clang", "ld.lld", "llvm-ar")):
        raise ValueError("Pinned Clang21 toolchain incomplete")
    if len(list(kernel.rglob("*.rej"))) != 64:
        raise ValueError("Stage75 requires 64 outstanding PREEMPT_RT rejects")
    if not prerequisites(
        stage50, stage66, stage67, stage68, stage69, stage72, stage73, out
    ):
        raise ValueError("Stage50/66/67/68/69/72/73 scoped archives not verified")
    STAGE50["forbid_images"](out)
    report.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PATH"] = str(clang) + os.pathsep + env.get("PATH", "")
    env.update({
        "ARCH": "arm64", "CC": "clang", "LD": "ld.lld",
        "HOSTCC": "gcc", "LLVM_IAS": "1",
    })
    cmd = [
        "make", "-C", str(kernel), "O=" + str(out),
        "ARCH=arm64", "CC=clang", "LD=ld.lld", "HOSTCC=gcc",
        "CROSS_COMPILE=aarch64-linux-gnu-",
        "CLANG_TRIPLE=aarch64-linux-gnu-", "-j2", SCOPE, TARGET,
    ]
    log = report / "crypto_subtree_make.log"
    with log.open("w", encoding="utf-8") as stream:
        try:
            rc = subprocess.run(
                cmd, env=env, stdout=stream, stderr=subprocess.STDOUT,
                timeout=timeout, check=False,
            ).returncode
        except subprocess.TimeoutExpired:
            rc = 124
            stream.write("\nEXP76_STAGE75_CRYPTO_SUBTREE_TIMEOUT\n")
    errors, context = STAGE50["failure_extract"](
        log.read_text(encoding="utf-8", errors="replace")
    )
    archive = out / TARGET
    exists = archive.is_file() and archive.stat().st_size > 0
    size = archive.stat().st_size if exists else 0
    members: list[str] = []
    ar_status = None
    if rc == 0 and exists:
        try:
            inspection = subprocess.run(
                [str(clang / "llvm-ar"), "t", str(archive)],
                capture_output=True, text=True, timeout=30, check=False,
            )
            ar_status = inspection.returncode
            if ar_status == 0:
                members = [
                    line for line in inspection.stdout.splitlines()
                    if line.strip()
                ]
            else:
                errors.append(
                    "llvm-ar t rejected CRYPTO archive: " +
                    inspection.stderr.strip()[:400]
                )
        except subprocess.TimeoutExpired:
            ar_status = 124
            errors.append("llvm-ar t timed out inspecting CRYPTO archive")
    if rc == 0 and not exists:
        errors.append("make returned 0 without creating crypto/built-in.a")
    if rc == 0 and exists and not members:
        errors.append("CONFIG_CRYPTO=y but no verified archive members")
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
        "first_error_context": context,
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
    for stage in (50, 66, 67, 68, 69, 72, 73):
        parser.add_argument(f"--stage{stage}-report", type=Path, required=True)
    parser.add_argument("--clang-bin", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=570)
    args = parser.parse_args()
    result = execute(
        args.kernel.resolve(), args.output.resolve(), args.report.resolve(),
        args.stage50_report.resolve(), args.stage66_report.resolve(),
        args.stage67_report.resolve(), args.stage68_report.resolve(),
        args.stage69_report.resolve(), args.stage72_report.resolve(),
        args.stage73_report.resolve(), args.clang_bin.resolve(), args.timeout,
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
        "kernel_built": False, "flash_ready": False,
    }, indent=2))


if __name__ == "__main__":
    main()
