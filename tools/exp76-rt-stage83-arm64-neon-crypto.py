#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage83 ARM64 crypto Kconfig RT port / NO FLASH
"""Port one SHA-pinned PREEMPT_RT rejected hunk to ARM64 crypto Kconfig.

Disable ChaCha20-NEON and Poly1305-NEON under PREEMPT_RT_BASE exactly as
the upstream 4.19.325-rt140 hunk requests. Never touch other crypto choices.
Retain the rejected .rej as historical evidence until semantic review; this
tool does NOT claim full RT integration or resolve the remaining 64 files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SOURCE = "arch/arm64/crypto/Kconfig"
REJECT = SOURCE + ".rej"
REJECT_SHA = "313a186927a334940aca6e6ce944adb63d2f0f4ced59ff57f761af3bd28c82c8"
STAGE = "EXP76_STAGE83_ARM64_NEON_CRYPTO_RT_KCONFIG_HUNK_NONFLASH"
STATUS = "stage83-status.json"
BLOCKS = {
    "CRYPTO_CHACHA20_NEON": (
        'config CRYPTO_CHACHA20_NEON\n'
        '\ttristate "ChaCha20, XChaCha20, and XChaCha12 stream ciphers using NEON instructions"\n'
        '\tdepends on KERNEL_MODE_NEON\n'
    ),
    "CRYPTO_POLY1305_NEON": (
        'config CRYPTO_POLY1305_NEON\n'
        '\ttristate "Poly1305 hash function using scalar or NEON instructions"\n'
        '\tdepends on KERNEL_MODE_NEON\n'
    ),
}


def verify(tree: Path, index: Path) -> tuple[str, dict]:
    if not (tree / ".git").is_dir():
        raise ValueError("Stage83 requires E404 isolated RT Git trial checkout")
    source_path = tree / SOURCE
    reject_path = tree / REJECT
    if not source_path.is_file() or not reject_path.is_file():
        raise ValueError("Stage83 requires ARM64 crypto source and original RT reject")
    rejected = sorted(tree.rglob("*.rej"))
    if len(rejected) != 64:
        raise ValueError("Stage83 requires exactly 64 original RT rejects")
    digest = hashlib.sha256(reject_path.read_bytes()).hexdigest()
    if digest != REJECT_SHA:
        raise ValueError("Stage83 rejected hunk SHA256 mismatch: " + digest)
    rejection = reject_path.read_text(encoding="utf-8")
    if rejection.count("@@ -107,13 +107,13 @@") != 1:
        raise ValueError("Stage83 pinned rejected hunk header drift")
    if rejection.count("-\tdepends on KERNEL_MODE_NEON\n") != 2:
        raise ValueError("Stage83 upstream minus-lines changed")
    if rejection.count("+\tdepends on KERNEL_MODE_NEON && !PREEMPT_RT_BASE\n") != 2:
        raise ValueError("Stage83 upstream plus-lines changed")
    if not index.is_file():
        raise ValueError("Stage83 requires Stage82 immutable reject inventory")
    data = json.loads(index.read_text(encoding="utf-8"))
    matching = [
        e for e in data.get("entries", [])
        if e.get("source") == SOURCE
    ]
    if (data.get("stage") !=
        "EXP76_STAGE82_OUTSTANDING_RT_REJECT_HUNK_INVENTORY_NONFLASH"
        or data.get("remaining_rejected_files") != 64
        or len(matching) != 1
        or matching[0].get("reject_sha256") != REJECT_SHA
        or matching[0].get("hunk_count") != 1
        or data.get("source_modified") is not False
        or data.get("rejects_deleted") is not False):
        raise ValueError("Stage83 Stage82 inventory provenance mismatch")
    source = source_path.read_text(encoding="utf-8")
    patched = source
    for name, old in BLOCKS.items():
        if source.count(old) != 1:
            raise ValueError(f"Stage83 source config block drift: {name}")
        modified = old.replace(
            "\tdepends on KERNEL_MODE_NEON\n",
            "\tdepends on KERNEL_MODE_NEON && !PREEMPT_RT_BASE\n",
        )
        if old == modified:
            raise ValueError("Stage83 missing RT Kconfig guard")
        if modified in source:
            raise ValueError(f"Stage83 source already ported: {name}")
        patched = patched.replace(old, modified, 1)
    rt_neon_guard = "depends on KERNEL_MODE_NEON && !PREEMPT_RT_BASE"
    if patched.count(rt_neon_guard) - source.count(rt_neon_guard) != len(BLOCKS):
        raise ValueError("Stage83 expected exactly two new RT crypto guards")
    if source.count("config CRYPTO_CHACHA20_NEON") != 1:
        raise ValueError("Stage83 duplicate ChaCha20 config")
    if source.count("config CRYPTO_POLY1305_NEON") != 1:
        raise ValueError("Stage83 duplicate Poly1305 config")
    return patched, {
        "stage": STAGE,
        "target": SOURCE,
        "rejected_hunk_sha256": digest,
        "rejected_hunks_reviewed": 1,
        "config_dependencies_patched": sorted(BLOCKS),
        "rt_guard": "!PREEMPT_RT_BASE",
        "nonrt_kernel_mode_neon_preserved": True,
        "unrelated_arm64_crypto_config_preserved": True,
        "reject_audit_file_retained": True,
        "remaining_rejected_files": 64,
        "original_source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "patched_source_sha256": hashlib.sha256(patched.encode()).hexdigest(),
        "semantic_backport_review_pending": True,
        "full_kernel_link_performed": False,
        "runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }


def execute(tree: Path, index: Path, report: Path, mode: str) -> dict:
    if mode not in ("verify", "apply"):
        raise ValueError("Stage83 mode must be verify or apply")
    patched, status = verify(tree, index)
    if mode == "apply":
        (tree / SOURCE).write_text(patched, encoding="utf-8")
        if (tree / SOURCE).read_text(encoding="utf-8") != patched:
            raise ValueError("Stage83 source post-write verification failed")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage83 altered original RT reject evidence")
    status["applied"] = mode == "apply"
    report.mkdir(parents=True, exist_ok=True)
    (report / STATUS).write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    return status


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", required=True, type=Path)
    p.add_argument("--index", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    p.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = p.parse_args()
    result = execute(
        args.tree.resolve(), args.index.resolve(), args.report.resolve(),
        args.mode,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
