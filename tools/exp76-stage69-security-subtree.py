#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage69 security Kbuild / NO FLASH
"""Compile security/built-in.a only after kernel, MM, FS and classified IPC gates.

IPC is legitimately an empty thin archive in the pinned pipa defconfig when
System V IPC and POSIX message queues are disabled. Do not count that as
compiled code. Security must have CONFIG_SECURITY=y and a nonempty archive.
"""
from __future__ import annotations

import argparse
import json
import os
import runpy
import subprocess
from pathlib import Path

STAGE68 = runpy.run_path(
    str(Path(__file__).with_name("exp76-stage68-ipc-subtree.py")),
    run_name="exp76_stage68_reusable_helpers",
)
STAGE50 = STAGE68["STAGE50"]
STAGE = "EXP76_STAGE69_SECURITY_SUBTREE_KBUILD_ARCHIVE_NONFLASH"
TARGET = "security/built-in.a"
SCOPE = "vmlinux-dirs=security"
OUTPUT = "SECURITY_SUBTREE_DIAGNOSTIC.json"


def prerequisites(stage50: Path, stage66: Path, stage67: Path,
                  stage68: Path, out: Path) -> bool:
    if not STAGE68["prerequisites"](stage50, stage66, stage67, out):
        return False
    ipc = STAGE50["read"](stage68)
    archive = out / "ipc/built-in.a"
    if not archive.is_file() or archive.stat().st_size == 0:
        return False
    physical_size = archive.stat().st_size
    selected = set((out / ".config").read_text(encoding="utf-8").splitlines())
    enabled = [k for k in STAGE68["IPC_KCONFIG"] if k + "=y" in selected]
    semantics = ipc.get("compile_semantics")
    disabled = (
        semantics == "CONFIG_DISABLED" and not enabled
        and ipc.get("archive_has_members") is False
        and archive.read_bytes() == STAGE68["EMPTY_THIN_ARCHIVE"]
    )
    compiled = (
        semantics == "OBJECTS_PRESENT" and enabled
        and ipc.get("archive_has_members") is True
        and physical_size > len(STAGE68["EMPTY_THIN_ARCHIVE"])
    )
    return bool(
        ipc.get("stage") == STAGE68["STAGE"]
        and ipc.get("target") == STAGE68["TARGET"]
        and ipc.get("top_level_directory_scope") == STAGE68["SCOPE"]
        and ipc.get("prior_kernel_subtree_gate") is True
        and ipc.get("prior_mm_subtree_gate") is True
        and ipc.get("prior_fs_subtree_gate") is True
        and ipc.get("attempted") is True
        and ipc.get("exit_code") == 0
        and ipc.get("timed_out") is False
        and ipc.get("archive_created") is True
        and ipc.get("archive_bytes") == physical_size
        and ipc.get("enabled_ipc_configs") == enabled
        and (disabled or compiled)
        and ipc.get("remaining_rejected_files") == 64
        and ipc.get("full_kernel_link_performed") is False
        and ipc.get("kernel_built") is False
        and ipc.get("flash_ready") is False
    )


def execute(kernel: Path, out: Path, report: Path, stage50: Path,
            stage66: Path, stage67: Path, stage68: Path, clang: Path,
            timeout: int) -> dict:
    if timeout < 60 or timeout > 600:
        raise ValueError("Unsupported Stage69 security compile timeout")
    if not (kernel / ".git").is_dir():
        raise ValueError("Stage69 requires isolated E404 trial git checkout")
    if not (kernel / "security/Makefile").is_file():
        raise ValueError("Pinned E404 security/Makefile missing")
    rules = kernel / "scripts/Makefile.build"
    if not rules.is_file() or rules.read_text(encoding="utf-8").count(
        "$(obj)/built-in.a: $(real-obj-y) FORCE"
    ) != 1:
        raise ValueError("Pinned archive construction rule missing or modified")
    top = kernel / "Makefile"
    if not top.is_file():
        raise ValueError("Pinned E404 root Makefile missing")
    source = top.read_text(encoding="utf-8")
    for anchor in STAGE50["ROOT_KBUILD_ANCHORS"]:
        if source.count(anchor) != 1:
            raise ValueError("Pinned E404 top-level directory dependency drift")
    if not (out / "include/generated/asm-offsets.h").is_file():
        raise ValueError("Stage69 arm64 prepare prerequisite missing")
    config = out / ".config"
    if not config.is_file():
        raise ValueError("Stage69 requires PREEMPT_RT and security configuration")
    selected = set(config.read_text(encoding="utf-8").splitlines())
    if ("CONFIG_PREEMPT_RT_FULL=y" not in selected
            or "CONFIG_SECURITY=y" not in selected):
        raise ValueError("Stage69 requires PREEMPT_RT and CONFIG_SECURITY=y")
    if not all((clang / name).is_file()
               for name in ("clang", "ld.lld", "llvm-ar")):
        raise ValueError("Pinned Android Clang21 toolchain missing")
    if len(list(kernel.rglob("*.rej"))) != 64:
        raise ValueError("Stage69 requires 64 outstanding RT rejection files")
    if not prerequisites(stage50, stage66, stage67, stage68, out):
        raise ValueError("Stage50/66/67/68 scoped archive gates incomplete")
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
    log_file = report / "security_subtree_make.log"
    with log_file.open("w", encoding="utf-8") as stream:
        try:
            rc = subprocess.run(
                cmd, env=env, stdout=stream, stderr=subprocess.STDOUT,
                timeout=timeout, check=False,
            ).returncode
        except subprocess.TimeoutExpired:
            rc = 124
            stream.write("\nEXP76_STAGE69_SECURITY_SUBTREE_TIMEOUT\n")
    errors, context = STAGE50["failure_extract"](
        log_file.read_text(encoding="utf-8", errors="replace")
    )
    archive = out / TARGET
    made = archive.is_file() and archive.stat().st_size > 0
    size = archive.stat().st_size if made else 0
    has_members = (
        rc == 0 and made and size > len(STAGE68["EMPTY_THIN_ARCHIVE"])
    )
    status = {
        "stage": STAGE,
        "target": TARGET,
        "top_level_directory_scope": SCOPE,
        "prior_kernel_subtree_gate": True,
        "prior_mm_subtree_gate": True,
        "prior_fs_subtree_gate": True,
        "prior_ipc_subtree_gate": True,
        "ipc_compile_semantics": STAGE50["read"](stage68)["compile_semantics"],
        "attempted": True,
        "exit_code": rc,
        "timed_out": rc == 124,
        "archive_created": rc == 0 and made,
        "archive_has_members": has_members,
        "archive_bytes": size,
        "errors_excerpt": errors,
        "first_error_context": context,
        "remaining_rejected_files": 64,
        "full_kernel_link_performed": False,
        "runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    if rc == 0 and not made:
        status["errors_excerpt"].append(
            "make returned 0 without producing security/built-in.a"
        )
    if rc == 0 and made and not has_members:
        status["errors_excerpt"].append(
            "security archive contains zero members with CONFIG_SECURITY=y"
        )
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
    parser.add_argument("--stage50-report", type=Path, required=True)
    parser.add_argument("--stage66-report", type=Path, required=True)
    parser.add_argument("--stage67-report", type=Path, required=True)
    parser.add_argument("--stage68-report", type=Path, required=True)
    parser.add_argument("--clang-bin", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=570)
    a = parser.parse_args()
    status = execute(
        a.kernel.resolve(), a.output.resolve(), a.report.resolve(),
        a.stage50_report.resolve(), a.stage66_report.resolve(),
        a.stage67_report.resolve(), a.stage68_report.resolve(),
        a.clang_bin.resolve(), a.timeout,
    )
    print(json.dumps({
        "stage": status["stage"],
        "target": status["target"],
        "archive_created": status["archive_created"],
        "archive_has_members": status["archive_has_members"],
        "ipc_compile_semantics": status["ipc_compile_semantics"],
        "exit_code": status["exit_code"],
        "timed_out": status["timed_out"],
        "errors_excerpt": status["errors_excerpt"][:8],
        "kernel_built": False,
        "flash_ready": False,
    }, indent=2))


if __name__ == "__main__":
    main()
