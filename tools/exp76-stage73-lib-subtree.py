#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage73 LIB Kbuild / NO FLASH
"""Compile lib/built-in.a after validated NET archive, with llvm-ar membership.

Only lib/ and its recursive Kbuild children are compiled. No full kernel
link, Image or boot.img is allowed. All prior RT gates remain mandatory.
"""
from __future__ import annotations

import argparse
import json
import os
import runpy
import subprocess
from pathlib import Path

STAGE72 = runpy.run_path(
    str(Path(__file__).with_name("exp76-stage72-net-subtree.py")),
    run_name="exp76_stage72_reusable_helpers",
)
STAGE50 = STAGE72["STAGE50"]
STAGE = "EXP76_STAGE73_LIB_SUBTREE_KBUILD_ARCHIVE_NONFLASH"
TARGET = "lib/built-in.a"
SCOPE = "vmlinux-dirs=lib"
OUTPUT = "LIB_SUBTREE_DIAGNOSTIC.json"


def prerequisites(stage50: Path, stage66: Path, stage67: Path,
                  stage68: Path, stage69: Path, stage72: Path,
                  out: Path) -> bool:
    if not STAGE72["prerequisites"](
        stage50, stage66, stage67, stage68, stage69, out
    ):
        return False
    net = STAGE50["read"](stage72)
    archive = out / STAGE72["TARGET"]
    return bool(
        net.get("stage") == STAGE72["STAGE"]
        and net.get("target") == STAGE72["TARGET"]
        and net.get("top_level_directory_scope") == STAGE72["SCOPE"]
        and net.get("prior_security_subtree_gate") is True
        and net.get("attempted") is True
        and net.get("exit_code") == 0
        and net.get("timed_out") is False
        and net.get("archive_created") is True
        and net.get("archive_has_members") is True
        and net.get("archive_inspection_exit_code") == 0
        and isinstance(net.get("archive_members_count"), int)
        and net["archive_members_count"] > 0
        and isinstance(net.get("archive_bytes"), int)
        and net["archive_bytes"] > 8
        and net.get("remaining_rejected_files") == 64
        and net.get("full_kernel_link_performed") is False
        and net.get("kernel_built") is False
        and net.get("flash_ready") is False
        and archive.is_file()
        and archive.stat().st_size == net["archive_bytes"]
    )


def execute(kernel: Path, out: Path, report: Path, stage50: Path,
            stage66: Path, stage67: Path, stage68: Path, stage69: Path,
            stage72: Path, clang: Path, timeout: int) -> dict:
    if timeout < 60 or timeout > 600:
        raise ValueError("Unsupported Stage73 LIB compile timeout")
    if not (kernel / ".git").is_dir():
        raise ValueError("Stage73 requires isolated E404 trial git checkout")
    if not (kernel / "lib/Makefile").is_file():
        raise ValueError("Pinned E404 lib/Makefile missing")
    rules = kernel / "scripts/Makefile.build"
    if not rules.is_file() or rules.read_text(encoding="utf-8").count(
        "$(obj)/built-in.a: $(real-obj-y) FORCE"
    ) != 1:
        raise ValueError("Pinned E404 archive Kbuild rule drift")
    top = kernel / "Makefile"
    if not top.is_file():
        raise ValueError("Pinned E404 root Makefile missing")
    for anchor in STAGE50["ROOT_KBUILD_ANCHORS"]:
        if top.read_text(encoding="utf-8").count(anchor) != 1:
            raise ValueError("Pinned E404 root directory dependency drift")
    if not (out / "include/generated/asm-offsets.h").is_file():
        raise ValueError("Stage73 arm64 prepare prerequisite missing")
    config = out / ".config"
    if not config.is_file():
        raise ValueError("Stage73 pinned pipa RT config missing")
    options = set(config.read_text(encoding="utf-8").splitlines())
    required = ("CONFIG_PREEMPT_RT_FULL=y", "CONFIG_SECURITY=y", "CONFIG_NET=y")
    if not all(name in options for name in required):
        raise ValueError("Stage73 requires PREEMPT_RT, SECURITY, NET config")
    if not all((clang / name).is_file()
               for name in ("clang", "ld.lld", "llvm-ar")):
        raise ValueError("Pinned Clang21 toolchain incomplete")
    if len(list(kernel.rglob("*.rej"))) != 64:
        raise ValueError("Stage73 requires 64 unresolved PREEMPT_RT rejects")
    if not prerequisites(
        stage50, stage66, stage67, stage68, stage69, stage72, out
    ):
        raise ValueError("Stage50/66/67/68/69/72 scoped archive gates incomplete")
    STAGE50["forbid_images"](out)
    report.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PATH"] = str(clang) + os.pathsep + env.get("PATH", "")
    env.update({"ARCH": "arm64", "CC": "clang", "LD": "ld.lld",
                "HOSTCC": "gcc", "LLVM_IAS": "1"})
    cmd = [
        "make", "-C", str(kernel), "O=" + str(out),
        "ARCH=arm64", "CC=clang", "LD=ld.lld", "HOSTCC=gcc",
        "CROSS_COMPILE=aarch64-linux-gnu-",
        "CLANG_TRIPLE=aarch64-linux-gnu-", "-j2", SCOPE, TARGET,
    ]
    log_file = report / "lib_subtree_make.log"
    with log_file.open("w", encoding="utf-8") as stream:
        try:
            rc = subprocess.run(
                cmd, env=env, stdout=stream, stderr=subprocess.STDOUT,
                timeout=timeout, check=False,
            ).returncode
        except subprocess.TimeoutExpired:
            rc = 124
            stream.write("\nEXP76_STAGE73_LIB_SUBTREE_TIMEOUT\n")
    errors, context = STAGE50["failure_extract"](
        log_file.read_text(encoding="utf-8", errors="replace")
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
                members = [item for item in inspection.stdout.splitlines()
                           if item.strip()]
            else:
                errors.append(
                    "llvm-ar t rejected LIB archive: " +
                    inspection.stderr.strip()[:400]
                )
        except subprocess.TimeoutExpired:
            ar_status = 124
            errors.append("llvm-ar t timed out inspecting LIB archive")
    if rc == 0 and not exists:
        errors.append("make returned zero without creating lib/built-in.a")
    if rc == 0 and exists and not members:
        errors.append("LIB archive has no verified object members")
    result = {
        "stage": STAGE,
        "target": TARGET,
        "top_level_directory_scope": SCOPE,
        "prior_kernel_subtree_gate": True,
        "prior_mm_subtree_gate": True,
        "prior_fs_subtree_gate": True,
        "prior_ipc_subtree_gate": True,
        "prior_security_subtree_gate": True,
        "prior_net_subtree_gate": True,
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
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    for num in (50, 66, 67, 68, 69, 72):
        parser.add_argument(f"--stage{num}-report", type=Path, required=True)
    parser.add_argument("--clang-bin", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=570)
    a = parser.parse_args()
    result = execute(
        a.kernel.resolve(), a.output.resolve(), a.report.resolve(),
        a.stage50_report.resolve(), a.stage66_report.resolve(),
        a.stage67_report.resolve(), a.stage68_report.resolve(),
        a.stage69_report.resolve(), a.stage72_report.resolve(),
        a.clang_bin.resolve(), a.timeout,
    )
    print(json.dumps({
        "stage": result["stage"], "target": result["target"],
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
