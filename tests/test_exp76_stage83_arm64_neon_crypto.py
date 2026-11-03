#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage83 NEON Kconfig tests / NO FLASH
"""Verify pinned RT Kconfig two-line backport, preservation and fail-closed drift."""
from __future__ import annotations

import hashlib
import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(
    str(ROOT / "tools/exp76-rt-stage83-arm64-neon-crypto.py"),
    run_name="exp76_stage83_fixture",
)
REJECT = (
    "diff --git a/arch/arm64/crypto/Kconfig b/arch/arm64/crypto/Kconfig\n"
    "--- a/arch/arm64/crypto/Kconfig\n"
    "+++ b/arch/arm64/crypto/Kconfig\n"
    "@@ -107,13 +107,13 @@ config CRYPTO_AES_ARM64_NEON_BLK\n"
    " config CRYPTO_CHACHA20_NEON\n"
    "-\tdepends on KERNEL_MODE_NEON\n"
    "+\tdepends on KERNEL_MODE_NEON && !PREEMPT_RT_BASE\n"
    " config CRYPTO_POLY1305_NEON\n"
    "-\tdepends on KERNEL_MODE_NEON\n"
    "+\tdepends on KERNEL_MODE_NEON && !PREEMPT_RT_BASE\n"
)
ORIGINAL_SHA = "313a186927a334940aca6e6ce944adb63d2f0f4ced59ff57f761af3bd28c82c8"


def put(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")


def fixture(root: Path) -> tuple[Path, Path, Path]:
    tree = root / "trial"
    (tree / ".git").mkdir(parents=True, exist_ok=True)
    content = (
        'config CRYPTO_AES_ARM64_NEON_BLK\n'
        '\ttristate "AES using NEON"\n'
        '\tdepends on KERNEL_MODE_NEON\n'
        '\tselect CRYPTO_SIMD\n'
        '\n'
        + M["BLOCKS"]["CRYPTO_CHACHA20_NEON"] +
        '\tselect CRYPTO_BLKCIPHER\n'
        '\n'
        + M["BLOCKS"]["CRYPTO_POLY1305_NEON"] +
        '\tselect CRYPTO_HASH\n'
        '\n'
        'config CRYPTO_SHA1_ARM64_CE\n'
        '\ttristate "SHA1 using extensions"\n'
        '\tdepends on KERNEL_MODE_NEON\n'
    )
    put(tree / M["SOURCE"], content)
    put(tree / M["REJECT"], REJECT)
    for i in range(63):
        put(tree / f"pending/rt-{i:02d}.c.rej", "@@ -1 +1 @@\n-old\n+new\n")
    inventory = root / "stage82.json"
    put(inventory, json.dumps({
        "stage": "EXP76_STAGE82_OUTSTANDING_RT_REJECT_HUNK_INVENTORY_NONFLASH",
        "remaining_rejected_files": 64,
        "source_modified": False,
        "rejects_deleted": False,
        "entries": [{
            "source": M["SOURCE"],
            "reject_sha256": hashlib.sha256(REJECT.encode()).hexdigest(),
            "hunk_count": 1,
        }],
    }))
    return tree, inventory, root / "stage83"


def reject(fn, expected: str) -> None:
    try:
        fn()
    except ValueError as exc:
        assert expected in str(exc), str(exc)
    else:
        raise AssertionError("Expected Stage83 reject: " + expected)


def main() -> None:
    assert M["REJECT_SHA"] == ORIGINAL_SHA
    # Synthetic diff bytes have a different hash from the actual official
    # reject. Override only in this fixture's own loaded namespace.
    globals_ = M["verify"].__globals__
    original_sha = globals_["REJECT_SHA"]
    globals_["REJECT_SHA"] = hashlib.sha256(REJECT.encode()).hexdigest()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tree, inventory, report = fixture(root / "good")
            before = (tree / M["SOURCE"]).read_bytes()
            rejection = (tree / M["REJECT"]).read_bytes()
            dry = M["execute"](tree, inventory, report, "verify")
            assert dry["applied"] is False
            assert (tree / M["SOURCE"]).read_bytes() == before
            applied = M["execute"](tree, inventory, report, "apply")
            patched = (tree / M["SOURCE"]).read_text()
            assert applied["applied"] is True
            assert applied["config_dependencies_patched"] == [
                "CRYPTO_CHACHA20_NEON", "CRYPTO_POLY1305_NEON",
            ]
            assert applied["rejected_hunks_reviewed"] == 1
            assert applied["reject_audit_file_retained"] is True
            assert applied["semantic_backport_review_pending"] is True
            assert applied["remaining_rejected_files"] == 64
            assert (tree / M["REJECT"]).read_bytes() == rejection
            assert patched.count(
                "\tdepends on KERNEL_MODE_NEON && !PREEMPT_RT_BASE"
            ) == 2
            assert patched.count("\tdepends on KERNEL_MODE_NEON\n") == 2
            assert "config CRYPTO_SHA1_ARM64_CE" in patched
            assert (tree / "pending/rt-00.c.rej").is_file()
            assert json.loads((report / M["STATUS"]).read_text()) == applied
            assert not applied["kernel_built"] and not applied["flash_ready"]
            reject(lambda: M["verify"](tree, inventory), "source config block drift")

            missing_git = fixture(root / "missing-git")
            (missing_git[0] / ".git").rmdir()
            reject(lambda: M["verify"](*missing_git[:2]), "isolated RT Git")

            missing_rej = fixture(root / "missing-rej")
            (missing_rej[0] / M["REJECT"]).unlink()
            reject(lambda: M["verify"](*missing_rej[:2]), "original RT reject")

            altered_hash = fixture(root / "modified-reject")
            p = altered_hash[0] / M["REJECT"]
            put(p, p.read_text() + "changed\n")
            reject(lambda: M["verify"](*altered_hash[:2]), "SHA256 mismatch")

            altered_hunk = fixture(root / "bad-hunk")
            p = altered_hunk[0] / M["REJECT"]
            broken = p.read_text().replace(
                "KERNEL_MODE_NEON && !PREEMPT_RT_BASE",
                "KERNEL_MODE_NEON && !PREEMPT_RT_FULL",
            )
            put(p, broken)
            sha = globals_["REJECT_SHA"]
            globals_["REJECT_SHA"] = hashlib.sha256(broken.encode()).hexdigest()
            try:
                reject(lambda: M["verify"](*altered_hunk[:2]), "plus-lines changed")
            finally:
                globals_["REJECT_SHA"] = sha

            changed_source = fixture(root / "source-drift")
            p = changed_source[0] / M["SOURCE"]
            put(p, p.read_text().replace(
                '\ttristate "Poly1305 hash function using scalar or NEON instructions"',
                '\ttristate "Poly1305 vendor-specific variant"',
            ))
            reject(lambda: M["verify"](*changed_source[:2]), "source config block drift")

            missing_manifest = fixture(root / "missing-inventory")
            missing_manifest[1].unlink()
            reject(lambda: M["verify"](*missing_manifest[:2]), "Stage82 immutable")

            bad_manifest = fixture(root / "inventory-drift")
            put(bad_manifest[1], json.dumps({
                "stage": "EXP76_STAGE82_OUTSTANDING_RT_REJECT_HUNK_INVENTORY_NONFLASH",
                "remaining_rejected_files": 64,
                "source_modified": False, "rejects_deleted": False,
                "entries": [{
                    "source": M["SOURCE"], "reject_sha256": "0" * 64,
                    "hunk_count": 1,
                }],
            }))
            reject(lambda: M["verify"](*bad_manifest[:2]), "provenance mismatch")

            extra_rej = fixture(root / "extra-reject")
            put(extra_rej[0] / "unexpected.rej", "+unexpected")
            reject(lambda: M["verify"](*extra_rej[:2]), "exactly 64")

            wrong_mode = fixture(root / "mode")
            reject(lambda: M["execute"](*wrong_mode, "flash"), "verify or apply")
    finally:
        globals_["REJECT_SHA"] = original_sha
    print(
        "EXP76_STAGE83_ARM64_NEON_CRYPTO_REGRESSIONS=10_PASS; "
        "REJECTS_RETAINED=64; KERNEL_BUILT=false; FLASH_READY=false"
    )


if __name__ == "__main__":
    main()
