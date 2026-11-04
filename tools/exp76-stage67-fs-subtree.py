#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage67 FS subtree Kbuild / NO FLASH
"""Compile fs/built-in.a only after successful scoped kernel/ and mm/ archives.

Scope top-level E404 Kbuild to the fs/ subtree, preserving all 64 RT rejects.
This is an object/archive diagnostic, not a full kernel link or boot artifact.
"""
from __future__ import annotations

import argparse
import json
import os
import runpy
import subprocess
from pathlib import Path

STAGE66 = runpy.run_path(
    str(Path(__file__).with_name("exp76-stage66-mm-subtree.py")),
    run_name="exp76_stage66_reusable_helpers",
)
STAGE50 = STAGE66["STAGE50"]
STAGE = "EXP76_STAGE67_FS_SUBTREE_KBUILD_ARCHIVE_NONFLASH"
TARGET = "fs/built-in.a"
SCOPE = "vmlinux-dirs=fs"
OUTPUT = "FS_SUBTREE_DIAGNOSTIC.json"


def prerequisites(stage50: Path, stage66: Path, out: Path) -> bool:
    if not STAGE66["prior_ok"](stage50, out / "kernel/built-in.a"):
        return False
    mm = STAGE50["read"](stage66)
    file = out / "mm/built-in.a"
    return (
        mm.get("stage") == STAGE66["STAGE"]
        and mm.get("target") == STAGE66["TARGET"]
        and mm.get("top_level_directory_scope") == STAGE66["SCOPE"]
        and mm.get("prior_kernel_subtree_gate") is True
        and mm.get("attempted") is True
        and mm.get("exit_code") == 0
        and mm.get("timed_out") is False
        and mm.get("archive_created") is True
        and isinstance(mm.get("archive_bytes"), int)
        and mm["archive_bytes"] > 0
        and mm.get("remaining_rejected_files") == 64
        and mm.get("full_kernel_link_performed") is False
        and mm.get("kernel_built") is False
        and mm.get("flash_ready") is False
        and file.is_file()
        and file.stat().st_size > 0
    )


def execute(kernel: Path, out: Path, report: Path,
            stage50: Path, stage66: Path, clang: Path, timeout: int) -> dict:
    if timeout < 60 or timeout > 600:
        raise ValueError("Unsupported Stage67 timeout")
    if not (kernel / ".git").is_dir():
        raise ValueError("Stage67 needs isolated E404 trial git checkout")
    if not (kernel / "fs/Makefile").is_file():
        raise ValueError("Pinned E404 fs/Makefile missing")
    rules = kernel / "scripts/Makefile.build"
    if not rules.is_file() or rules.read_text(encoding="utf-8").count(
        "$(obj)/built-in.a: $(real-obj-y) FORCE"
    ) != 1:
        raise ValueError("Pinned archive construction rule missing or modified")
    top = kernel / "Makefile"
    if not top.is_file():
        raise ValueError("Pinned E404 top-level Makefile missing")
    source = top.read_text(encoding="utf-8")
    for anchor in STAGE50["ROOT_KBUILD_ANCHORS"]:
        if source.count(anchor) != 1:
            raise ValueError("Pinned E404 top-level directory dependency drift")
    if not (out / "include/generated/asm-offsets.h").is_file():
        raise ValueError("Stage67 arm64 prepare prerequisite missing")
    config = out / ".config"
    if not config.is_file() or "CONFIG_PREEMPT_RT_FULL=y" not in config.read_text(
        encoding="utf-8"
    ).splitlines():
        raise ValueError("Stage67 requires PREEMPT_RT_FULL configuration")
    if not all((clang / name).is_file()
               for name in ("clang", "ld.lld", "llvm-ar")):
        raise ValueError("Pinned Android Clang21 toolchain incomplete")
    if len(list(kernel.rglob("*.rej"))) != 64:
        raise ValueError("Stage67 requires exactly 64 outstanding RT rejects")
    if not prerequisites(stage50, stage66, out):
        raise ValueError("Stage50 and Stage66 scoped archive gates must both pass")
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
    log_file = report / "fs_subtree_make.log"
    with log_file.open("w", encoding="utf-8") as stream:
        try:
            rc = subprocess.run(
                cmd, env=env, stdout=stream, stderr=subprocess.STDOUT,
                timeout=timeout, check=False,
            ).returncode
        except subprocess.TimeoutExpired:
            rc = 124
            stream.write("\nEXP76_STAGE67_FS_SUBTREE_TIMEOUT\n")
    errors, context = STAGE50["failure_extract"](
        log_file.read_text(encoding="utf-8", errors="replace")
    )
    archive = out / TARGET
    made = archive.is_file() and archive.stat().st_size > 0
    status = {
        "stage": STAGE,
        "target": TARGET,
        "top_level_directory_scope": SCOPE,
        "prior_kernel_subtree_gate": True,
        "prior_mm_subtree_gate": True,
        "attempted": True,
        "exit_code": rc,
        "timed_out": rc == 124,
        "archive_created": rc == 0 and made,
        "archive_bytes": archive.stat().st_size if made else 0,
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
            "make returned 0 without producing fs/built-in.a"
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
    parser.add_argument("--clang-bin", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=570)
    a = parser.parse_args()
    status = execute(
        a.kernel.resolve(), a.output.resolve(), a.report.resolve(),
        a.stage50_report.resolve(), a.stage66_report.resolve(),
        a.clang_bin.resolve(), a.timeout,
    )
    print(json.dumps({
        "stage": status["stage"],
        "target": status["target"],
        "prior_kernel_subtree_gate": status["prior_kernel_subtree_gate"],
        "prior_mm_subtree_gate": status["prior_mm_subtree_gate"],
        "archive_created": status["archive_created"],
        "exit_code": status["exit_code"],
        "timed_out": status["timed_out"],
        "errors_excerpt": status["errors_excerpt"][:8],
        "kernel_built": False,
        "flash_ready": False,
    }, indent=2))


if __name__ == "__main__":
    main()
