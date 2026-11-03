#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage86 ARM64 raw Image compile / NO FLASH
"""Verify RT link-symbol recovery and build a non-distributed raw ARM64 Image.

Requires the successful Stage84 vmlinux ELF, reviewed Stage85 ABI repair and
the pinned E404 ARM64 image recipe. System.map must contain all ten symbols
which Stage84 could not resolve before Stage85. Then invoke Kbuild's Image
target; check its ARM64 header without distributing or flashing the result.
No boot.img, vendor_boot, dtb concatenation or Image artifact uploads.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import runpy
import subprocess
from pathlib import Path

M84 = runpy.run_path(
    str(Path(__file__).with_name("exp76-stage84-vmlinux-link.py")),
    run_name="exp76_stage84_helpers",
)
M85 = runpy.run_path(
    str(Path(__file__).with_name("exp76-rt-stage85-rwsem-idr-link.py")),
    run_name="exp76_stage85_helpers",
)
READ = M84["STAGE50"]["read"]
STAGE = "EXP76_STAGE86_RAW_ARM64_IMAGE_AND_RT_SYMBOL_DIAGNOSTIC_NONFLASH"
REPORT = "RAW_ARM64_IMAGE_DIAGNOSTIC.json"
RAW_IMAGE = "arch/arm64/boot/Image"
SYMBOLS = (
    "down_write", "up_write", "down_read", "up_read",
    "idr_preload_end", "down_read_killable", "down_write_trylock",
    "down_read_trylock", "downgrade_write", "down_write_killable",
)
BOOT_FORBIDDEN = (
    "boot.img", "vendor_boot.img", "dtbo.img",
    "arch/arm64/boot/Image.gz", "arch/arm64/boot/Image.gz-dtb",
    "arch/arm64/boot/Image-dtb",
)


def source_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def read_symbols(path: Path) -> tuple[list[str], list[str]]:
    if not path.is_file():
        raise ValueError("Stage86 requires Stage84 System.map from actual vmlinux")
    found: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[1] in ("T", "t", "W", "w"):
            found.add(parts[2])
    present = [name for name in SYMBOLS if name in found]
    missing = [name for name in SYMBOLS if name not in found]
    return present, missing


def preflight(kernel: Path, out: Path, stage84: Path, stage85: Path,
              clang: Path) -> dict:
    if not (kernel / ".git").is_dir():
        raise ValueError("Stage86 requires isolated E404 Git tree")
    if len(list(kernel.rglob("*.rej"))) != 64:
        raise ValueError("Stage86 requires 64 retained RT rejection files")
    image_rules = kernel / "arch/arm64/boot/Makefile"
    arch_rules = kernel / "arch/arm64/Makefile"
    head = kernel / "arch/arm64/kernel/head.S"
    for file in (image_rules, arch_rules, head):
        if not file.is_file():
            raise ValueError("Stage86 pinned ARM64 image source missing: " + str(file))
    if image_rules.read_text(encoding="utf-8").count(
        "$(obj)/Image: vmlinux FORCE"
    ) != 1:
        raise ValueError("Stage86 pinned ARM64 objcopy Image recipe drift")
    if arch_rules.read_text(encoding="utf-8").count("Image: vmlinux") != 1:
        raise ValueError("Stage86 pinned ARM64 Image target drift")
    if '.ascii\t"ARM\\x64"' not in head.read_text(encoding="utf-8"):
        raise ValueError("Stage86 pinned ARM64 Image boot header drift")
    if not all((clang / exe).is_file() for exe in
               ("clang", "ld.lld", "llvm-objcopy")):
        raise ValueError("Stage86 pinned Clang21 or llvm-objcopy missing")
    config = out / ".config"
    if not config.is_file():
        raise ValueError("Stage86 missing actual RT .config")
    options = set(config.read_text(encoding="utf-8").splitlines())
    if "CONFIG_PREEMPT_RT_FULL=y" not in options:
        raise ValueError("Stage86 requires PREEMPT_RT_FULL config")
    linked = READ(stage84)
    repair = READ(stage85)
    vmlinux = out / "vmlinux"
    if not (
        linked.get("stage") == M84["STAGE"]
        and linked.get("target") == "vmlinux"
        and linked.get("attempted") is True
        and linked.get("exit_code") == 0
        and linked.get("timed_out") is False
        and linked.get("vmlinux_created") is True
        and linked.get("vmlinux_elf_verified") is True
        and type(linked.get("vmlinux_bytes")) is int
        and linked["vmlinux_bytes"] > 4096
        and linked.get("remaining_rejected_files") == 64
        and linked.get("boot_image_generated") is False
        and linked.get("flash_performed") is False
        and linked.get("flash_ready") is False
        and vmlinux.is_file()
        and vmlinux.stat().st_size == linked["vmlinux_bytes"]
        and vmlinux.open("rb").read(4) == b"\x7fELF"
    ):
        raise ValueError("Stage86 actual linked vmlinux provenance failed")
    if not (
        repair.get("stage") == M85["STAGE"]
        and repair.get("applied") is True
        and repair.get("rt_public_wrapper_count") == 9
        and repair.get("rt_public_symbols") == list(M85["PUBLIC_FUNCS"])
        and repair.get("non_rt_vendor_rwsem_not_linked") is True
        and repair.get("idr_preload_end_uses_local_unlock") is True
        and repair.get("idr_preload_lock_pair_preserved") is True
        and repair.get("rt_rwsem_lowlevel_preserved") is True
        and repair.get("rejected_files_remaining") == 64
        and repair.get("full_kernel_link_performed") is False
        and repair.get("kernel_built") is False
        and repair.get("flash_ready") is False
    ):
        raise ValueError("Stage86 Stage85 RWSEM and IDR ABI provenance failed")
    for path, digest in (repair.get("source_sha256") or {}).items():
        if path not in (M85["MAKE"], M85["API"], M85["RADIX"]):
            raise ValueError("Stage86 unexpected Stage85 source path")
        src = kernel / path
        if not src.is_file() or source_sha256(src) != digest:
            raise ValueError("Stage86 Stage85 source hash mismatch: " + path)
    if set((repair.get("source_sha256") or {}).keys()) != {
        M85["MAKE"], M85["API"], M85["RADIX"]
    }:
        raise ValueError("Stage86 incomplete Stage85 source SHA provenance")
    if (out / RAW_IMAGE).exists():
        raise ValueError("Stage86 requires no stale preexisting raw Image")
    forbidden = [name for name in BOOT_FORBIDDEN if (out / name).exists()]
    if forbidden:
        raise ValueError("Stage86 forbidden packaged/compressed boot artifacts: " +
                         ", ".join(forbidden))
    present, missing = read_symbols(out / "System.map")
    return {
        "public_link_symbols_verified": present,
        "public_link_symbols_missing": missing,
        "all_previous_unresolved_symbols_restored": not missing,
    }


def execute(kernel: Path, out: Path, report: Path, stage84: Path,
            stage85: Path, clang: Path, timeout: int) -> dict:
    if timeout < 60 or timeout > 600:
        raise ValueError("Stage86 timeout outside 60..600 seconds")
    pre = preflight(kernel, out, stage84, stage85, clang)
    if not pre["all_previous_unresolved_symbols_restored"]:
        raise ValueError(
            "Stage86 remaining public RT symbols absent in System.map: " +
            ", ".join(pre["public_link_symbols_missing"])
        )
    report.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PATH"] = str(clang) + os.pathsep + env.get("PATH", "")
    env.update({"ARCH": "arm64", "CC": "clang", "LD": "ld.lld",
                "HOSTCC": "gcc", "LLVM_IAS": "1"})
    cmd = [
        "make", "-C", str(kernel), "O=" + str(out),
        "ARCH=arm64", "CC=clang", "LD=ld.lld", "HOSTCC=gcc",
        "CROSS_COMPILE=aarch64-linux-gnu-",
        "CLANG_TRIPLE=aarch64-linux-gnu-", "OBJCOPY=llvm-objcopy",
        "-j2", "Image",
    ]
    log = report / "raw_arm64_Image_make.log"
    with log.open("w", encoding="utf-8") as stream:
        try:
            rc = subprocess.run(
                cmd, env=env, stdout=stream, stderr=subprocess.STDOUT,
                timeout=timeout, check=False,
            ).returncode
        except subprocess.TimeoutExpired:
            rc = 124
            stream.write("\nEXP76_STAGE86_ARM64_IMAGE_TIMEOUT\n")
    errors, context = M84["STAGE50"]["failure_extract"](
        log.read_text(encoding="utf-8", errors="replace")
    )
    raw = out / RAW_IMAGE
    present = raw.is_file()
    size = raw.stat().st_size if present else 0
    header = b""
    if present:
        with raw.open("rb") as stream:
            stream.seek(0x38)
            header = stream.read(4)
    valid = bool(rc == 0 and size > 4096 and header == b"ARM\x64")
    if rc == 0 and not valid:
        errors.append("make Image succeeded but ARM64 raw header magic invalid")
    forbidden = [name for name in BOOT_FORBIDDEN if (out / name).exists()]
    if forbidden:
        raise ValueError("Stage86 unexpected packaged boot artifact: " +
                         ", ".join(forbidden))
    if len(list(kernel.rglob("*.rej"))) != 64:
        raise ValueError("Stage86 unexpectedly altered original RT rejects")
    status = {
        "stage": STAGE,
        "target": "Image",
        "raw_image_path": RAW_IMAGE,
        "prior_vmlinux_link_proven": True,
        "prior_rt_rwsem_idr_link_proven": True,
        **pre,
        "attempted": True,
        "exit_code": rc,
        "timed_out": rc == 124,
        "raw_image_created": present,
        "raw_image_bytes": size,
        "raw_arm64_magic_hex": header.hex(),
        "raw_arm64_header_valid": valid,
        "raw_image_sha256": source_sha256(raw) if present else None,
        "image_artifact_uploaded": False,
        "packaged_boot_image_generated": False,
        "flash_performed": False,
        "remaining_rejected_files": 64,
        "rt_semantic_review_complete": False,
        "runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
        "first_compiler_errors": errors[:20],
        "first_failure_context": context[:24],
    }
    (report / REPORT).write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8"
    )
    return status


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kernel", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--stage84-report", required=True, type=Path)
    parser.add_argument("--stage85-report", required=True, type=Path)
    parser.add_argument("--clang-bin", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=480)
    args = parser.parse_args()
    result = execute(
        args.kernel.resolve(), args.output.resolve(), args.report.resolve(),
        args.stage84_report.resolve(), args.stage85_report.resolve(),
        args.clang_bin.resolve(), args.timeout,
    )
    print(json.dumps({
        "stage": result["stage"],
        "linked_symbols_verified": len(result["public_link_symbols_verified"]),
        "exit_code": result["exit_code"],
        "raw_arm64_header_valid": result["raw_arm64_header_valid"],
        "raw_image_bytes": result["raw_image_bytes"],
        "raw_image_sha256": result["raw_image_sha256"],
        "remaining_rejected_files": 64,
        "flash_ready": False,
    }, indent=2))


if __name__ == "__main__":
    main()
