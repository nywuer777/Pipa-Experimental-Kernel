#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 GitHub Actions / EXP76 Stage96 bootv3 offline budget regressions / NO FLASH
"""Fail-closed regression tests for size-only EXP76 Boot V3 compact layout."""
from __future__ import annotations
import hashlib
import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(
    str(ROOT / "tools/exp76-stage96-bootv3-budget.py"),
    run_name="stage96_synthetic_helpers",
)


def put(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8")


def sample_image(size: int = 5017) -> bytes:
    image = bytearray(size)
    image[56:60] = b"ARM\x64"
    return bytes(image)


def fixture(root: Path) -> tuple[Path, ...]:
    kernel = root / "trial"
    out = root / "output"
    (kernel / ".git").mkdir(parents=True)
    for i in range(64):
        put(kernel / f"rejects/{i:02d}.rej", "@@ -1 +1 @@\n-old\n+new\n")
    put(out / ".config", "CONFIG_SMP=y\nCONFIG_PREEMPT_RT_FULL=y\n")
    img = sample_image()
    put(out / M["RAW_IMAGE"], img)
    stage86 = root / "stage86.json"
    put(stage86, json.dumps({
        "stage": M["STAGE86"], "attempted": True, "exit_code": 0,
        "raw_image_created": True, "raw_arm64_header_valid": True,
        "raw_image_path": M["RAW_IMAGE"], "raw_image_bytes": len(img),
        "raw_image_sha256": hashlib.sha256(img).hexdigest(),
        "raw_arm64_magic_hex": "41524d64",
        "all_previous_unresolved_symbols_restored": True,
        "remaining_rejected_files": 64, "image_artifact_uploaded": False,
        "packaged_boot_image_generated": False, "flash_performed": False,
        "flash_ready": False,
    }))
    stage95 = root / "stage95.json"
    put(stage95, json.dumps({
        "stage": M["STAGE95"],
        "reviewed_original_rcu_header_rejected_hunks": 5,
        "original_rejected_files_remaining": 64,
        "source_modified": False,
        "rt_rcu_runtime_semantics_verified": False,
        "flash_ready": False,
    }))
    return ROOT, kernel, out, stage86, stage95, root / "report"


def run(fx: tuple[Path, ...]) -> dict:
    return M["execute"](*fx)


def fail(fn, expected: str) -> None:
    try:
        fn()
    except ValueError as exc:
        assert expected in str(exc), (expected, str(exc))
    else:
        raise AssertionError("Stage96 accepted invalid state: " + expected)


def change_json(path: Path, name: str, value) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data[name] = value
    put(path, json.dumps(data))


def main() -> None:
    assert M["STOCK_COMPACT_SIZE"] == 32206848
    assert M["STOCK_KERNEL_SIZE"] == 30349336
    assert M["STOCK_RAMDISK_SIZE"] == 1849345
    assert M["align"](M["STOCK_RAMDISK_SIZE"]) == 1851392
    assert (
        M["PAGE"] + M["align"](M["STOCK_KERNEL_SIZE"]) +
        M["align"](M["STOCK_RAMDISK_SIZE"])
    ) == M["STOCK_COMPACT_SIZE"]
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        good = fixture(root / "good")
        img_before = (good[2] / M["RAW_IMAGE"]).read_bytes()
        result = run(good)
        assert result["stage"] == M["STAGE"]
        assert result["stock_control_metadata_pinned"] is True
        assert result["exp76_arm64_raw_image_bytes_verified"] == len(img_before)
        assert result["exp76_arm64_raw_image_sha256_verified"] == hashlib.sha256(
            img_before
        ).hexdigest()
        assert result["exp76_arm64_magic_verified"] is True
        assert result["estimated_offline_compact_candidate_bytes"] == (
            4096 + M["align"](len(img_before)) + 1851392
        )
        assert result["compact_size_budget_remaining_bytes"] == (
            M["STOCK_COMPACT_SIZE"] -
            result["estimated_offline_compact_candidate_bytes"]
        )
        assert result["fits_pinned_stock_compact_file_size"] is True
        assert result["effective_rt_config_verified"] is True
        assert result["stage95_source_audit_proven"] is True
        assert result["original_rt_reject_files_retained"] == 64
        for forbidden in (
            "original_stock_boot_bytes_present", "original_ramdisk_verified_this_run",
            "dtb_layout_verified", "avb_policy_verified",
            "boot_partition_capacity_verified", "android_runtime_verified",
            "physical_recovery_verified", "candidate_generated",
            "image_artifact_uploaded", "boot_image_generated", "flash_performed",
            "kernel_built", "flash_ready",
        ):
            assert result[forbidden] is False, forbidden
        assert (good[2] / M["RAW_IMAGE"]).read_bytes() == img_before
        assert json.loads((good[-1] / M["REPORT"]).read_text()) == result

        changed_hash = fixture(root / "hash")
        p = changed_hash[2] / M["RAW_IMAGE"]
        img = bytearray(p.read_bytes())
        img[160] ^= 1
        put(p, bytes(img))
        fail(lambda: run(changed_hash), "Image SHA256 drift")

        changed_size = fixture(root / "size")
        p = changed_size[2] / M["RAW_IMAGE"]
        put(p, p.read_bytes() + b"\0")
        fail(lambda: run(changed_size), "Image size differs")

        wrong_magic = fixture(root / "magic")
        p = wrong_magic[2] / M["RAW_IMAGE"]
        img = bytearray(p.read_bytes())
        img[56:60] = b"BAD!"
        put(p, bytes(img))
        fail(lambda: run(wrong_magic), "ARM64 kernel image magic changed")

        missing_image = fixture(root / "no-image")
        (missing_image[2] / M["RAW_IMAGE"]).unlink()
        fail(lambda: run(missing_image), "raw ARM64 Image missing")

        no_rt = fixture(root / "no-rt")
        put(no_rt[2] / ".config", "CONFIG_SMP=y\nCONFIG_PREEMPT=y\n")
        fail(lambda: run(no_rt), "PREEMPT_RT_FULL=y")

        invalid_stage86 = fixture(root / "stage86")
        change_json(invalid_stage86[3], "raw_arm64_header_valid", False)
        fail(lambda: run(invalid_stage86), "actual ARM64 Image build not verified")

        invalid_stage95 = fixture(root / "stage95")
        change_json(invalid_stage95[4], "rt_rcu_runtime_semantics_verified", True)
        fail(lambda: run(invalid_stage95), "Stage95 RT RCU audit not fully established")

        uploaded_image = fixture(root / "uploaded")
        change_json(uploaded_image[3], "image_artifact_uploaded", True)
        fail(lambda: run(uploaded_image), "actual ARM64 Image build not verified")

        no_reject = fixture(root / "rejects")
        (no_reject[1] / "rejects/00.rej").unlink()
        fail(lambda: run(no_reject), "64 RT rejection files")

        no_git = fixture(root / "git")
        (no_git[1] / ".git").rmdir()
        fail(lambda: run(no_git), "isolated E404 kernel source")

        unexpected_boot = fixture(root / "boot")
        put(unexpected_boot[2] / "boot.img", b"ANDROID!")
        fail(lambda: run(unexpected_boot), "forbidden packaged boot artifact")

        too_large = fixture(root / "budget")
        large = sample_image(34 * 1024 * 1024)
        put(too_large[2] / M["RAW_IMAGE"], large)
        change_json(too_large[3], "raw_image_bytes", len(large))
        change_json(too_large[3], "raw_image_sha256", hashlib.sha256(large).hexdigest())
        fail(lambda: run(too_large), "exceeds audited stock compact budget")

        wrong_stock_packer = root / "bad-packer"
        source = (ROOT / "tools/exp27-4-build-offline.py").read_text(encoding="utf-8")
        put(wrong_stock_packer / "tools/exp27-4-build-offline.py",
            source.replace("STOCK_SIZE = 32206848", "STOCK_SIZE = 32206849", 1))
        fail(
            lambda: M["canonical_stock_contract"](wrong_stock_packer),
            "stock-control drift",
        )

    print(
        "EXP76_STAGE96_OFFLINE_BOOTV3_BUDGET_REGRESSIONS=14_PASS; "
        "REAL_STOCK_BYTES_NOT_AVAILABLE; NO_CANDIDATE; FLASH_READY=false"
    )


if __name__ == "__main__":
    main()
