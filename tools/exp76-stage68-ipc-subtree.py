#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage68 IPC Kbuild / NO FLASH
"""Compile only ipc/built-in.a after successful kernel, MM and FS diagnostics.

Pin E404 top-level Kbuild directory dependency invariants. A scoped
vmlinux-dirs=ipc target limits this test to System V IPC/POSIX queues
under PREEMPT_RT_FULL. No full kernel link or installable images.
"""
from __future__ import annotations

import argparse
import json
import os
import runpy
import subprocess
from pathlib import Path

STAGE67 = runpy.run_path(
    str(Path(__file__).with_name("exp76-stage67-fs-subtree.py")),
    run_name="exp76_stage67_helpers",
)
STAGE50 = STAGE67["STAGE50"]
STAGE = "EXP76_STAGE68_IPC_SUBTREE_KBUILD_ARCHIVE_NONFLASH"
TARGET = "ipc/built-in.a"
SCOPE = "vmlinux-dirs=ipc"
OUTPUT = "IPC_SUBTREE_DIAGNOSTIC.json"
IPC_KCONFIG = ("CONFIG_SYSVIPC", "CONFIG_POSIX_MQUEUE", "CONFIG_IPC_NS")
EMPTY_AR_HEADERS = (b"!<thin>\n", b"!<arch>\n")


def prerequisites(stage50: Path, stage66: Path, stage67: Path,
                  out: Path) -> bool:
    if not STAGE67["prerequisites"](stage50, stage66, out):
        return False
    fs = STAGE50["read"](stage67)
    archive = out / "fs/built-in.a"
    return (
        fs.get("stage") == STAGE67["STAGE"]
        and fs.get("target") == STAGE67["TARGET"]
        and fs.get("top_level_directory_scope") == STAGE67["SCOPE"]
        and fs.get("prior_kernel_subtree_gate") is True
        and fs.get("prior_mm_subtree_gate") is True
        and fs.get("attempted") is True
        and fs.get("exit_code") == 0
        and fs.get("timed_out") is False
        and fs.get("archive_created") is True
        and isinstance(fs.get("archive_bytes"), int)
        and fs["archive_bytes"] > 0
        and fs.get("remaining_rejected_files") == 64
        and fs.get("full_kernel_link_performed") is False
        and fs.get("kernel_built") is False
        and fs.get("flash_ready") is False
        and archive.is_file()
        and archive.stat().st_size > 0
    )


def execute(kernel: Path, out: Path, report: Path, stage50: Path,
            stage66: Path, stage67: Path, clang: Path, timeout: int) -> dict:
    if timeout < 60 or timeout > 600:
        raise ValueError("Unsupported Stage68 IPC compile timeout")
    if not (kernel / ".git").is_dir():
        raise ValueError("Stage68 requires isolated E404 git checkout")
    if not (kernel / "ipc/Makefile").is_file():
        raise ValueError("Pinned E404 ipc/Makefile missing")
    rules = kernel / "scripts/Makefile.build"
    if not rules.is_file() or rules.read_text(encoding="utf-8").count(
        "$(obj)/built-in.a: $(real-obj-y) FORCE"
    ) != 1:
        raise ValueError("Pinned E404 archive rule drift")
    top = kernel / "Makefile"
    if not top.is_file():
        raise ValueError("Pinned E404 root Makefile missing")
    root_makefile = top.read_text(encoding="utf-8")
    for anchor in STAGE50["ROOT_KBUILD_ANCHORS"]:
        if root_makefile.count(anchor) != 1:
            raise ValueError("Pinned E404 Kbuild dependency scope drift")
    if not (out / "include/generated/asm-offsets.h").is_file():
        raise ValueError("Stage68 arm64 prepare prerequisite missing")
    config = out / ".config"
    if not config.is_file():
        raise ValueError("Stage68 requires CONFIG_PREEMPT_RT_FULL=y")
    selected = set(config.read_text(encoding="utf-8").splitlines())
    if "CONFIG_PREEMPT_RT_FULL=y" not in selected:
        raise ValueError("Stage68 requires CONFIG_PREEMPT_RT_FULL=y")
    enabled_ipc = [name for name in IPC_KCONFIG if name + "=y" in selected]
    if not all((clang / name).is_file()
               for name in ("clang", "ld.lld", "llvm-ar")):
        raise ValueError("Pinned Clang21 compiler toolchain missing")
    if len(list(kernel.rglob("*.rej"))) != 64:
        raise ValueError("Stage68 expects 64 unresolved RT rejects")
    if not prerequisites(stage50, stage66, stage67, out):
        raise ValueError("Stage50/66/67 scoped kernel/MM/FS archive gates failed")
    STAGE50["forbid_images"](out)
    report.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PATH"] = str(clang) + os.pathsep + env.get("PATH", "")
    env.update({"ARCH": "arm64", "CC": "clang", "LD": "ld.lld",
                "HOSTCC": "gcc", "LLVM_IAS": "1"})
    cmd = [
        "make", "-C", str(kernel), "O=" + str(out), "ARCH=arm64",
        "CC=clang", "LD=ld.lld", "HOSTCC=gcc",
        "CROSS_COMPILE=aarch64-linux-gnu-",
        "CLANG_TRIPLE=aarch64-linux-gnu-", "-j2", SCOPE, TARGET,
    ]
    log_file = report / "ipc_subtree_make.log"
    with log_file.open("w", encoding="utf-8") as stream:
        try:
            rc = subprocess.run(cmd, env=env, stdout=stream,
                                stderr=subprocess.STDOUT, timeout=timeout,
                                check=False).returncode
        except subprocess.TimeoutExpired:
            rc = 124
            stream.write("\nEXP76_STAGE68_IPC_SUBTREE_TIMEOUT\n")
    errors, context = STAGE50["failure_extract"](
        log_file.read_text(encoding="utf-8", errors="replace")
    )
    archive = out / TARGET
    exists = archive.is_file() and archive.stat().st_size > 0
    size = archive.stat().st_size if exists else 0
    magic = archive.read_bytes()[:8] if exists else b""
    valid_magic = magic in EMPTY_AR_HEADERS
    empty_ar = exists and size == 8 and valid_magic
    has_objects = rc == 0 and exists and size > 8 and valid_magic
    if rc != 0 or not exists:
        semantic = "FAILED"
    elif empty_ar and not enabled_ipc:
        semantic = "CONFIG_DISABLED"
    elif empty_ar:
        semantic = "ERROR_EMPTY_WITH_IPC_CONFIG_ENABLED"
    elif has_objects:
        semantic = "OBJECTS_PRESENT"
    else:
        semantic = "ERROR_UNKNOWN_ARCHIVE"
    result = {
        "stage": STAGE,
        "target": TARGET,
        "top_level_directory_scope": SCOPE,
        "prior_kernel_subtree_gate": True,
        "prior_mm_subtree_gate": True,
        "prior_fs_subtree_gate": True,
        "attempted": True,
        "exit_code": rc,
        "timed_out": rc == 124,
        "archive_created": rc == 0 and exists,
        "archive_bytes": size,
        "archive_magic_hex": magic.hex(),
        "archive_has_members": has_objects,
        "enabled_ipc_configs": enabled_ipc,
        "compile_semantics": semantic,
        "errors_excerpt": errors,
        "first_error_context": context,
        "remaining_rejected_files": 64,
        "full_kernel_link_performed": False,
        "runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    if rc == 0 and not exists:
        result["errors_excerpt"].append(
            "make returned 0 but ipc/built-in.a was not generated"
        )
    if semantic.startswith("ERROR_"):
        result["errors_excerpt"].append(
            "IPC archive members absent despite enabled configuration or invalid archive"
        )
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
    parser.add_argument("--stage50-report", type=Path, required=True)
    parser.add_argument("--stage66-report", type=Path, required=True)
    parser.add_argument("--stage67-report", type=Path, required=True)
    parser.add_argument("--clang-bin", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=570)
    a = parser.parse_args()
    result = execute(
        a.kernel.resolve(), a.output.resolve(), a.report.resolve(),
        a.stage50_report.resolve(), a.stage66_report.resolve(),
        a.stage67_report.resolve(), a.clang_bin.resolve(), a.timeout,
    )
    print(json.dumps({
        "stage": result["stage"], "target": result["target"],
        "prior_kernel_subtree_gate": result["prior_kernel_subtree_gate"],
        "prior_mm_subtree_gate": result["prior_mm_subtree_gate"],
        "prior_fs_subtree_gate": result["prior_fs_subtree_gate"],
        "exit_code": result["exit_code"],
        "archive_created": result["archive_created"],
        "archive_has_members": result["archive_has_members"],
        "enabled_ipc_configs": result["enabled_ipc_configs"],
        "compile_semantics": result["compile_semantics"],
        "timed_out": result["timed_out"],
        "errors_excerpt": result["errors_excerpt"][:8],
        "kernel_built": False, "flash_ready": False,
    }, indent=2))


if __name__ == "__main__":
    main()
