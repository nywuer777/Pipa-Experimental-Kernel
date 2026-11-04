#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage84 vmlinux link diagnostic / NO FLASH
"""Attempt actual Kbuild arm64 vmlinux integration after scoped archives.

A successful scoped archive does not validate cross-subsystem linking. Run
the pinned E404 kernel's real vmlinux target with Clang21 and capture the
first actual compiler or linker error. Do not build bootable Image or boot.img,
and do not write tablet partitions. Keep all 64 pending RT rejects.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import runpy
import subprocess
from pathlib import Path

M81 = runpy.run_path(
    str(Path(__file__).with_name("exp76-stage81-block-init-subtrees.py")),
    run_name="exp76_stage81_helpers",
)
M83 = runpy.run_path(
    str(Path(__file__).with_name("exp76-rt-stage83-arm64-neon-crypto.py")),
    run_name="exp76_stage83_helpers",
)
STAGE50 = M81["STAGE50"]
STAGE = "EXP76_STAGE84_PINNED_ARM64_VMLINUX_LINK_DIAGNOSTIC_NOFLASH"
TARGET = "vmlinux"
REPORT = "VMLINUX_LINK_DIAGNOSTIC.json"
FORBIDDEN = (
    "arch/arm64/boot/Image", "arch/arm64/boot/Image.gz",
    "arch/arm64/boot/Image.gz-dtb", "boot.img", "vendor_boot.img",
    "dtbo.img",
)
LINK_RULES = (
    "vmlinux: scripts/link-vmlinux.sh autoksyms_recursive $(vmlinux-deps) FORCE",
    "all: vmlinux",
)


def forbid_boot_images(out: Path) -> None:
    unwanted = [name for name in FORBIDDEN if (out / name).exists()]
    if unwanted:
        raise ValueError("Stage84 forbidden boot image artifact: " + ", ".join(unwanted))


def provenance(stage81: Path, stage83: Path, out: Path) -> bool:
    block_init = STAGE50["read"](stage81)
    neon = STAGE50["read"](stage83)
    targets = block_init.get("targets") or {}
    if not isinstance(targets, dict) or set(targets) != {"block", "init"}:
        return False
    if not (
        block_init.get("stage") == M81["STAGE"]
        and block_init.get("prior_drivers_subtree_gate") is True
        and block_init.get("prior_compile_h_gate") is True
        and block_init.get("prior_functionfs_rt_gate") is True
        and block_init.get("all_archives_verified") is True
        and block_init.get("remaining_rejected_files") == 64
        and block_init.get("full_kernel_link_performed") is False
        and block_init.get("kernel_built") is False
        and block_init.get("flash_ready") is False
    ):
        return False
    for name in ("block", "init"):
        obj = targets[name]
        archive = out / name / "built-in.a"
        if not (
            isinstance(obj, dict)
            and obj.get("target") == f"{name}/built-in.a"
            and obj.get("directory_scope") == f"vmlinux-dirs={name}"
            and obj.get("attempted") is True
            and obj.get("exit_code") == 0
            and obj.get("timed_out") is False
            and obj.get("archive_created") is True
            and obj.get("archive_has_members") is True
            and obj.get("archive_inspection_exit_code") == 0
            and type(obj.get("archive_members_count")) is int
            and obj["archive_members_count"] > 0
            and type(obj.get("archive_bytes")) is int
            and obj["archive_bytes"] > 8
            and archive.is_file()
            and archive.stat().st_size == obj["archive_bytes"]
        ):
            return False
    return bool(
        neon.get("stage") == M83["STAGE"]
        and neon.get("target") == M83["SOURCE"]
        and neon.get("applied") is True
        and neon.get("rejected_hunk_sha256") == M83["REJECT_SHA"]
        and neon.get("rejected_hunks_reviewed") == 1
        and neon.get("config_dependencies_patched") ==
            sorted(M83["BLOCKS"])
        and neon.get("nonrt_kernel_mode_neon_preserved") is True
        and neon.get("reject_audit_file_retained") is True
        and neon.get("remaining_rejected_files") == 64
        and neon.get("full_kernel_link_performed") is False
        and neon.get("kernel_built") is False
        and neon.get("flash_ready") is False
    )


def execute(kernel: Path, out: Path, report: Path, stage81: Path,
            stage83: Path, clang: Path, timeout: int) -> dict:
    if timeout < 60 or timeout > 900:
        raise ValueError("Stage84 timeout outside 60..900 second range")
    if not (kernel / ".git").is_dir():
        raise ValueError("Stage84 requires pinned isolated E404 Git checkout")
    makefile = kernel / "Makefile"
    linker = kernel / "scripts/link-vmlinux.sh"
    if not makefile.is_file() or not linker.is_file():
        raise ValueError("Stage84 pinned E404 vmlinux Kbuild files missing")
    text = makefile.read_text(encoding="utf-8")
    if any(text.count(line) != 1 for line in LINK_RULES):
        raise ValueError("Stage84 E404 vmlinux target rule drift")
    if "vmlinux_link()" not in linker.read_text(encoding="utf-8"):
        raise ValueError("Stage84 pinned vmlinux linker script changed")
    if not (out / "include/generated/asm-offsets.h").is_file():
        raise ValueError("Stage84 arm64 prepare prerequisite missing")
    cfg = out / ".config"
    if not cfg.is_file():
        raise ValueError("Stage84 PREEMPT_RT config missing")
    config_lines = set(cfg.read_text(encoding="utf-8").splitlines())
    if not {"CONFIG_PREEMPT_RT_FULL=y", "CONFIG_BLOCK=y"}.issubset(config_lines):
        raise ValueError("Stage84 requires PREEMPT_RT_FULL=y and BLOCK=y")
    if len(list(kernel.rglob("*.rej"))) != 64:
        raise ValueError("Stage84 requires 64 unresolved RT rejects")
    if not all((clang / binary).is_file() for binary in
               ("clang", "ld.lld", "llvm-ar")):
        raise ValueError("Stage84 pinned Clang21 toolchain missing")
    if not provenance(stage81, stage83, out):
        raise ValueError("Stage84 BLOCK/INIT and ARM64 crypto provenance failed")
    latest = STAGE50["read"](stage83)
    src = kernel / M83["SOURCE"]
    if not src.is_file() or hashlib.sha256(
        src.read_bytes()
    ).hexdigest() != latest.get("patched_source_sha256"):
        raise ValueError("Stage84 ARM64 crypto source differs from reviewed patch")
    forbid_boot_images(out)
    if (out / TARGET).exists():
        raise ValueError("Stage84 requires no preexisting linked vmlinux")
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
        "CLANG_TRIPLE=aarch64-linux-gnu-", "-j2", TARGET,
    ]
    log = report / "vmlinux_make.log"
    with log.open("w", encoding="utf-8") as stream:
        try:
            rc = subprocess.run(
                command, env=env, stdout=stream,
                stderr=subprocess.STDOUT, timeout=timeout, check=False,
            ).returncode
        except subprocess.TimeoutExpired:
            rc = 124
            stream.write("\nEXP76_STAGE84_VMLINUX_KBUILD_TIMEOUT\n")
    errors, context = STAGE50["failure_extract"](
        log.read_text(encoding="utf-8", errors="replace")
    )
    vmlinux = out / TARGET
    present = vmlinux.is_file()
    size = vmlinux.stat().st_size if present else 0
    is_elf = bool(
        present and size > 4096 and
        vmlinux.open("rb").read(4) == b"\x7fELF"
    )
    verified = rc == 0 and is_elf
    if rc == 0 and not is_elf:
        errors.append("make vmlinux returned success but no valid ELF output")
    forbid_boot_images(out)
    if len(list(kernel.rglob("*.rej"))) != 64:
        raise ValueError("Stage84 modified original RT rejection evidence")
    result = {
        "stage": STAGE,
        "target": TARGET,
        "prior_block_init_archives_gate": True,
        "prior_arm64_crypto_kconfig_gate": True,
        "attempted": True,
        "exit_code": rc,
        "timed_out": rc == 124,
        "vmlinux_created": present,
        "vmlinux_bytes": size,
        "vmlinux_elf_verified": verified,
        "first_compiler_linker_errors": errors[:30],
        "first_failure_context": context[:36],
        "remaining_rejected_files": 64,
        "boot_image_generated": False,
        "flash_performed": False,
        "runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    (report / REPORT).write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--kernel", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--stage81-report", type=Path, required=True)
    p.add_argument("--stage83-report", type=Path, required=True)
    p.add_argument("--clang-bin", type=Path, required=True)
    p.add_argument("--timeout", type=int, default=720)
    a = p.parse_args()
    result = execute(
        a.kernel.resolve(), a.output.resolve(), a.report.resolve(),
        a.stage81_report.resolve(), a.stage83_report.resolve(),
        a.clang_bin.resolve(), a.timeout,
    )
    print(json.dumps({
        "stage": STAGE, "attempted": True,
        "exit_code": result["exit_code"],
        "vmlinux_elf_verified": result["vmlinux_elf_verified"],
        "timed_out": result["timed_out"],
        "first_compiler_linker_errors": result["first_compiler_linker_errors"][:8],
        "kernel_built": False, "flash_ready": False,
    }, indent=2))


if __name__ == "__main__":
    main()
