#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 GitHub Actions / EXP76 Stage96 offline Boot V3 layout budget / NO FLASH
"""Estimate EXP76 ARM64 Image's compact Boot V3 layout against pinned stock.

Use the exact stock-control metadata from EXP27.4 and check the actual Stage86
Image bytes, SHA-256 and ARM64 header. This is deliberately NOT a repacker:
the private stock boot control and its ramdisk are not available in CI.
A size-budget pass does not establish bootability, DTB provenance, Android
AVB policy, physical partition capacity, runtime correctness or recovery.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import runpy
from pathlib import Path

STAGE = "EXP76_STAGE96_BOOT_V3_OFFLINE_LAYOUT_BUDGET_NONFLASH"
STAGE86 = "EXP76_STAGE86_RAW_ARM64_IMAGE_AND_RT_SYMBOL_DIAGNOSTIC_NONFLASH"
STAGE95 = "EXP76_STAGE95_RCU_INTERNAL_HEADER_GENERATION_AUDIT_NONFLASH"
REPORT = "stage96-status.json"
RAW_IMAGE = "arch/arm64/boot/Image"
# Public, previously audited EXP27.4 Windows stock-control metadata only.
STOCK_COMPACT_SHA = "202aaaf67fe5c0a963965c4e29f67866b509916e0bdff15dde38ef55b3d321e7"
STOCK_KERNEL_SHA = "a72fff8f285419f6f45c7e3d1c43fb1fe5958878b5ce53ab9291148ad9b7acdd"
STOCK_RAMDISK_SHA = "d2a62b4ca809b28ddd0ae25388af051c874fbacfecb6b965243b7d6b81465ee9"
STOCK_KERNEL_SIZE = 30349336
STOCK_RAMDISK_SIZE = 1849345
STOCK_COMPACT_SIZE = 32206848
PAGE = 4096
BOOT_HEADER_SIZE = 1580
FORBIDDEN_OUTPUTS = ("boot.img", "vendor_boot.img", "dtbo.img")


def sha(file: Path) -> str:
    h = hashlib.sha256()
    with file.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def align(size: int) -> int:
    return ((size + PAGE - 1) // PAGE) * PAGE


def json_report(file: Path, expected_stage: str) -> dict:
    if not file.is_file():
        raise ValueError("Stage96 required prior CI report missing")
    data = json.loads(file.read_text(encoding="utf-8"))
    if data.get("stage") != expected_stage:
        raise ValueError("Stage96 prior CI evidence stage mismatch")
    return data


def canonical_stock_contract(project: Path) -> dict:
    script = project / "tools/exp27-4-build-offline.py"
    if not script.is_file():
        raise ValueError("Stage96 canonical EXP27.4 stock Boot V3 packer missing")
    original = runpy.run_path(str(script), run_name="exp76_stage96_exp27_audited_helper")
    expected = {
        "PAGE": PAGE, "BOOT_HEADER_SIZE": BOOT_HEADER_SIZE,
        "STOCK_COMPACT_SHA": STOCK_COMPACT_SHA,
        "STOCK_KERNEL_SHA": STOCK_KERNEL_SHA,
        "STOCK_RAMDISK_SHA": STOCK_RAMDISK_SHA,
        "STOCK_SIZE": STOCK_COMPACT_SIZE,
        "STOCK_KERNEL_SIZE": STOCK_KERNEL_SIZE,
        "STOCK_RAMDISK_SIZE": STOCK_RAMDISK_SIZE,
    }
    for name, value in expected.items():
        if original.get(name) != value:
            raise ValueError("Stage96 audited EXP27.4 Boot V3 stock-control drift: " + name)
    if not callable(original.get("verify_stock")) or not callable(original.get("build")):
        raise ValueError("Stage96 canonical EXP27.4 packer API missing")
    if (PAGE + align(STOCK_KERNEL_SIZE) + align(STOCK_RAMDISK_SIZE)
            != STOCK_COMPACT_SIZE):
        raise ValueError("Stage96 pinned stock compact Boot V3 arithmetic mismatch")
    return {"canonical_packer_sha256": sha(script), "pinned_stock_layout": True}


def execute(project: Path, kernel: Path, output: Path, stage86_path: Path,
            stage95_path: Path, report: Path) -> dict:
    if not (kernel / ".git").is_dir():
        raise ValueError("Stage96 requires pinned isolated E404 kernel source")
    if len(list(kernel.rglob("*.rej"))) != 64:
        raise ValueError("Stage96 requires original 64 RT rejection files")
    canonical = canonical_stock_contract(project)
    s86 = json_report(stage86_path, STAGE86)
    if not (
        s86.get("attempted") is True
        and s86.get("exit_code") == 0
        and s86.get("raw_image_created") is True
        and s86.get("raw_arm64_header_valid") is True
        and s86.get("raw_image_path") == RAW_IMAGE
        and s86.get("all_previous_unresolved_symbols_restored") is True
        and s86.get("remaining_rejected_files") == 64
        and s86.get("image_artifact_uploaded") is False
        and s86.get("packaged_boot_image_generated") is False
        and s86.get("flash_performed") is False
        and s86.get("flash_ready") is False
    ):
        raise ValueError("Stage96 previous actual ARM64 Image build not verified")
    s95 = json_report(stage95_path, STAGE95)
    if not (
        s95.get("reviewed_original_rcu_header_rejected_hunks") == 5
        and s95.get("original_rejected_files_remaining") == 64
        and s95.get("source_modified") is False
        and s95.get("rt_rcu_runtime_semantics_verified") is False
        and s95.get("flash_ready") is False
    ):
        raise ValueError("Stage96 Stage95 RT RCU audit not fully established")
    config = output / ".config"
    if not config.is_file():
        raise ValueError("Stage96 effective RT .config missing")
    settings = set(config.read_text(encoding="utf-8").splitlines())
    for option in ("CONFIG_SMP=y", "CONFIG_PREEMPT_RT_FULL=y"):
        if option not in settings:
            raise ValueError("Stage96 expected PREEMPT_RT_FULL SMP Kconfig missing: " + option)
    raw = output / RAW_IMAGE
    if not raw.is_file():
        raise ValueError("Stage96 actual raw ARM64 Image missing")
    size = raw.stat().st_size
    if size <= 4096 or not isinstance(s86.get("raw_image_bytes"), int):
        raise ValueError("Stage96 actual raw ARM64 Image bytes invalid")
    if size != s86["raw_image_bytes"]:
        raise ValueError("Stage96 actual Image size differs from Stage86 evidence")
    with raw.open("rb") as f:
        f.seek(56)
        magic = f.read(4)
    if magic != b"ARM\x64" or s86.get("raw_arm64_magic_hex") != magic.hex():
        raise ValueError("Stage96 actual ARM64 kernel image magic changed")
    digest = sha(raw)
    if digest != s86.get("raw_image_sha256"):
        raise ValueError("Stage96 actual Image SHA256 drift from Stage86 build")
    for filename in FORBIDDEN_OUTPUTS:
        if (output / filename).exists() or (project / filename).exists():
            raise ValueError("Stage96 found forbidden packaged boot artifact: " + filename)
    expected_compact = PAGE + align(size) + align(STOCK_RAMDISK_SIZE)
    capacity_budget = STOCK_COMPACT_SIZE - expected_compact
    if capacity_budget < 0:
        raise ValueError("Stage96 replacement Image exceeds audited stock compact budget")
    result = {
        "stage": STAGE,
        "canonical_exp27_packer_sha256": canonical["canonical_packer_sha256"],
        "stock_control_metadata_pinned": canonical["pinned_stock_layout"],
        "stock_compact_sha256_reference": STOCK_COMPACT_SHA,
        "stock_compact_bytes_reference": STOCK_COMPACT_SIZE,
        "stock_kernel_bytes_reference": STOCK_KERNEL_SIZE,
        "stock_ramdisk_bytes_reference": STOCK_RAMDISK_SIZE,
        "boot_header_version_reference": 3,
        "boot_header_size_bytes_reference": BOOT_HEADER_SIZE,
        "boot_page_alignment_bytes": PAGE,
        "exp76_arm64_raw_image_bytes_verified": size,
        "exp76_arm64_raw_image_sha256_verified": digest,
        "exp76_arm64_magic_verified": True,
        "estimated_offline_compact_candidate_bytes": expected_compact,
        "compact_size_budget_remaining_bytes": capacity_budget,
        "fits_pinned_stock_compact_file_size": True,
        "effective_rt_config_verified": True,
        "stage95_source_audit_proven": True,
        "original_rt_reject_files_retained": 64,
        "original_stock_boot_bytes_present": False,
        "original_ramdisk_verified_this_run": False,
        "dtb_layout_verified": False,
        "avb_policy_verified": False,
        "boot_partition_capacity_verified": False,
        "android_runtime_verified": False,
        "physical_recovery_verified": False,
        "candidate_generated": False,
        "image_artifact_uploaded": False,
        "boot_image_generated": False,
        "flash_performed": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    if len(list(kernel.rglob("*.rej"))) != 64:
        raise ValueError("Stage96 original RT rejected files were unexpectedly modified")
    report.mkdir(parents=True, exist_ok=True)
    (report / REPORT).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--project", type=Path, required=True)
    p.add_argument("--kernel", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--stage86-report", type=Path, required=True)
    p.add_argument("--stage95-report", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(execute(
        a.project.resolve(), a.kernel.resolve(), a.output.resolve(),
        a.stage86_report.resolve(), a.stage95_report.resolve(),
        a.report.resolve(),
    ), indent=2))


if __name__ == "__main__":
    main()
