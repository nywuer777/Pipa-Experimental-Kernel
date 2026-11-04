#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage66 MM subtree Kbuild / NO FLASH
"""Build only mm/built-in.a after a successful scoped kernel/built-in.a gate.

The E404 root Makefile expands vmlinux-dirs to unrelated subsystems by
default. Explicitly pin vmlinux-dirs=mm while requesting mm/built-in.a.
This builds memory management objects only, never vmlinux, Image or boot.img.
"""
from __future__ import annotations

import argparse
import json
import os
import runpy
import subprocess
from pathlib import Path

STAGE50 = runpy.run_path(
    str(Path(__file__).with_name("exp76-stage50-kernel-subtree.py")),
    run_name="exp76_stage50_reusable_helpers",
)
TARGET = "mm/built-in.a"
SCOPE = "vmlinux-dirs=mm"
OUTPUT = "MM_SUBTREE_DIAGNOSTIC.json"
EXPECTED_STAGE50 = "EXP76_STAGE50_KERNEL_SUBTREE_KBUILD_ARCHIVE_NONFLASH"
STAGE = "EXP76_STAGE66_MM_SUBTREE_KBUILD_ARCHIVE_NONFLASH"


def prior_ok(path: Path, archive: Path) -> bool:
    report = STAGE50["read"](path)
    return (
        report.get("stage") == EXPECTED_STAGE50
        and report.get("target") == "kernel/built-in.a"
        and report.get("top_level_directory_scope") == "vmlinux-dirs=kernel"
        and report.get("baseline_22_objects_compiled") is True
        and report.get("attempted") is True
        and report.get("exit_code") == 0
        and report.get("archive_created") is True
        and isinstance(report.get("archive_bytes"), int)
        and report["archive_bytes"] > 0
        and report.get("remaining_rejected_files") == 64
        and report.get("full_kernel_link_performed") is False
        and report.get("kernel_built") is False
        and report.get("flash_ready") is False
        and archive.is_file()
        and archive.stat().st_size > 0
    )


def execute(kernel: Path, out: Path, report: Path, stage50: Path,
            clang: Path, timeout: int) -> dict:
    if timeout < 60 or timeout > 600:
        raise ValueError("Unsupported Stage66 timeout")
    if not (kernel / ".git").is_dir():
        raise ValueError("Stage66 needs isolated E404 trial git checkout")
    if not (kernel / "mm/Makefile").is_file():
        raise ValueError("E404 mm/Makefile missing")
    if not (kernel / "scripts/Makefile.build").is_file():
        raise ValueError("Kbuild archive rules missing")
    source = (kernel / "scripts/Makefile.build").read_text(encoding="utf-8")
    if source.count("$(obj)/built-in.a: $(real-obj-y) FORCE") != 1:
        raise ValueError("Pinned E404 archive construction rule drift")
    top = kernel / "Makefile"
    if not top.is_file():
        raise ValueError("Pinned E404 top-level Makefile missing")
    top_source = top.read_text(encoding="utf-8")
    for marker in STAGE50["ROOT_KBUILD_ANCHORS"]:
        if top_source.count(marker) != 1:
            raise ValueError("Pinned E404 top-level directory dependency drift")
    if not (out / "include/generated/asm-offsets.h").is_file():
        raise ValueError("Missing arm64 prepare prerequisite")
    config = out / ".config"
    if not config.is_file() or "CONFIG_PREEMPT_RT_FULL=y" not in config.read_text(
        encoding="utf-8"
    ).splitlines():
        raise ValueError("Stage66 requires PREEMPT_RT_FULL config")
    if not all((clang / bin_name).is_file()
               for bin_name in ("clang", "ld.lld", "llvm-ar")):
        raise ValueError("Pinned Clang21 toolchain incomplete")
    if len(list(kernel.rglob("*.rej"))) != 64:
        raise ValueError("Stage66 requires 64 outstanding RT rejection files")
    if not prior_ok(stage50, out / "kernel/built-in.a"):
        raise ValueError("Stage50 scoped kernel/built-in.a success gate failed")
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
    log_file = report / "mm_subtree_make.log"
    with log_file.open("w", encoding="utf-8") as stream:
        try:
            rc = subprocess.run(cmd, env=env, stdout=stream,
                                stderr=subprocess.STDOUT,
                                timeout=timeout, check=False).returncode
        except subprocess.TimeoutExpired:
            rc = 124
            stream.write("\nEXP76_STAGE66_MM_SUBTREE_TIMEOUT\n")
    errors, context = STAGE50["failure_extract"](
        log_file.read_text(encoding="utf-8", errors="replace")
    )
    archive = out / TARGET
    created = archive.is_file() and archive.stat().st_size > 0
    status = {
        "stage": STAGE,
        "target": TARGET,
        "top_level_directory_scope": SCOPE,
        "prior_kernel_subtree_gate": True,
        "attempted": True,
        "exit_code": rc,
        "timed_out": rc == 124,
        "archive_created": rc == 0 and created,
        "archive_bytes": archive.stat().st_size if created else 0,
        "errors_excerpt": errors,
        "first_error_context": context,
        "remaining_rejected_files": 64,
        "full_kernel_link_performed": False,
        "runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    if rc == 0 and not created:
        status["errors_excerpt"].append(
            "make returned 0 without producing mm/built-in.a"
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
    parser.add_argument("--clang-bin", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=570)
    a = parser.parse_args()
    result = execute(
        a.kernel.resolve(), a.output.resolve(), a.report.resolve(),
        a.stage50_report.resolve(), a.clang_bin.resolve(), a.timeout,
    )
    print(json.dumps({
        "stage": result["stage"],
        "target": result["target"],
        "prior_kernel_subtree_gate": result["prior_kernel_subtree_gate"],
        "archive_created": result["archive_created"],
        "exit_code": result["exit_code"],
        "timed_out": result["timed_out"],
        "errors_excerpt": result["errors_excerpt"][:8],
        "kernel_built": False,
        "flash_ready": False,
    }, indent=2))


if __name__ == "__main__":
    main()
