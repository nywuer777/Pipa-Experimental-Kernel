#!/usr/bin/env python3
"""EXP02 read-only gate for the compiled EXP01 Image. NEVER creates boot.img."""
import argparse
import hashlib
import json
from pathlib import Path

PINNED_SOURCE = "fed88a6024cd4d46c52eda607a95d97d7371ba81"
EXPECTED_IMAGE_SHA256 = "bb20a6a936ff730d89dab8ca354ccb0ea7fe427594b8b60d2e1c424873970b11"
REQUIRED_CONFIG = {
    "CONFIG_PIPA_EXP_SUGOV": "y",
    "CONFIG_PIPA_EXP_SUGOV_RATE_LIMIT_US": "1500",
    "CONFIG_KSU": "y",
}

def checksum(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def audit(base):
    image = base / "exp01-work/out/arch/arm64/boot/Image"
    config = base / "exp01-work/out/.config"
    digest = base / "compiled-Image.sha256"
    build_log = base / "exp01-work/build.log"
    for path in (image, config, digest, build_log):
        if not path.is_file():
            raise ValueError("Required EXP01 artifact is missing: " + str(path.relative_to(base)))
    image_size = image.stat().st_size
    if image_size < 1_000_000:
        raise ValueError("Kernel Image unexpectedly small")
    with image.open("rb") as stream:
        stream.seek(0x38)
        magic = stream.read(4)
    if magic != b"ARM\x64":
        raise ValueError("Kernel Image does not have expected ARM64 Image header")
    image_sha256 = checksum(image)
    if image_sha256 != EXPECTED_IMAGE_SHA256:
        raise ValueError("Kernel Image differs from pinned successful EXP01 build")
    digest_fields = digest.read_text(encoding="utf-8").strip().split()
    if not digest_fields or digest_fields[0].lower() != image_sha256:
        raise ValueError("Artifact Image SHA256 does not match compiled-Image.sha256")
    cfg = {}
    for line in config.read_text(encoding="utf-8").splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
            cfg[key] = value
    mismatches = {k: {"expected": v, "actual": cfg.get(k)} for k, v in REQUIRED_CONFIG.items() if cfg.get(k) != v}
    if mismatches:
        raise ValueError("Kernel config mismatch: " + json.dumps(mismatches, sort_keys=True))
    log = build_log.read_text(encoding="utf-8", errors="replace")
    if "OBJCOPY arch/arm64/boot/Image" not in log:
        raise ValueError("No ARM64 Image creation evidence in build log")
    return {
        "project": "Pipa Experimental Kernel",
        "milestone": "EXP02",
        "state": "HOST_BINARY_AUDITED_NOT_FLASHABLE",
        "source": {"repo": "kvsnr113/xiaomi_sm8250_kernel_e404",
                   "branch": "main-bpf", "commit": PINNED_SOURCE},
        "image": {"file": "exp01-work/out/arch/arm64/boot/Image",
                  "bytes": image_size, "sha256": image_sha256,
                  "header_magic": "ARM64", "compiler_build_evidence": True},
        "kernel_config": {k: cfg[k] for k in REQUIRED_CONFIG},
        "boot_partition_backup_examined": False,
        "vendor_boot_backup_examined": False,
        "dtbo_backup_examined": False,
        "vbmeta_backup_examined": False,
        "dtb_output_in_exp01_artifact": False,
        "flash_ready": False,
        "root_preservation_proven": False,
        "rom_boot_compatibility_proven": False,
        "missing_gates": [
            "Read-only headers audit of the locally backed up boot_b/vendor_boot_b/dtbo_b/vbmeta_b partitions",
            "Determine boot header version and kernel/DTB placement of the installed ROM",
            "Validate exact DTB/DTBO and vendor modules for the installed pipa crDroid 16 build",
            "Validate root integration and verified boot constraints",
            "Repacking, rollback procedure and boot-test approval"
        ],
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=Path("exp02-compatibility-report.json"))
    args = parser.parse_args()
    result = audit(args.artifact_root)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    print("PASS: EXP01 Image matches pinned ARM64 build. No boot image produced.")

if __name__ == "__main__":
    main()
