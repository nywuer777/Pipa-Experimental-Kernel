#!/usr/bin/env python3
"""EXP11 local/offline *read-only* Android boot v3 structural preflight.

Reads pinned private slot-B backups on user's computer; never outputs
boot.img, vendor_boot.img, patched images, recovery scripts, or flash commands.
No device, Internet, ADB or root is accessed.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import exp10_forensic_diff as verified

EXPECTED = {
    "boot_b.img": "31f57cded5fa4b37426b4387b58c1c7330703a1c1a8a5aa584b348fcbb78c2f4",
    "vendor_boot_b.img": "a24ea921db6014a49f9895cc5c18efbb6c6674d697f25cde3b7a1670a643c28c",
    "dtbo_b.img": "f4168f76d092362ac438543d74938d83e3e567a37abb16e4d61fe7ba764588e2",
    "vbmeta_b.img": "86d703c2ea2f73a55aa86374329bd89ffd975c0e95e33645a156cfdc343889ff",
}
ORIGINAL_KERNEL_HASH = "a72fff8f285419f6f45c7e3d1c43fb1fe5958878b5ce53ab9291148ad9b7acdd"
ORIGINAL_VENDOR_RAMDISK_HASH = "8e0841f5271c164654b0a43561671a7a9e2364430ee1d650c114c8f55144c8e6"
ORIGINAL_GENERIC_RAMDISK_HASH = "d2a62b4ca809b28ddd0ae25388af051c874fbacfecb6b965243b7d6b81465ee9"
EXPECTED_DTB_HASH = verified.KNOWN_DTB
EXPECTED_DTBO_PAYLOAD_HASH = verified.KNOWN_DTBO

def sha_stream(file, start=0, size=None):
    file.seek(start)
    hasher = hashlib.sha256()
    remaining = size
    while True:
        n = 1024 * 1024 if remaining is None else min(1024 * 1024, remaining)
        if n == 0:
            break
        chunk = file.read(n)
        if not chunk:
            if remaining is not None:
                raise ValueError("Premature end of file while hashing")
            break
        hasher.update(chunk)
        if remaining is not None:
            remaining -= len(chunk)
    return hasher.hexdigest()

def bounded_read(file, start, count):
    file.seek(0, 2)
    total = file.tell()
    if start < 0 or count <= 0 or start + count > total:
        raise ValueError(f"Invalid span offset={start}, length={count}, total={total}")
    file.seek(start)
    data = file.read(count)
    if len(data) != count:
        raise ValueError("Short read")
    return data

def align(x, page):
    if page < 2048 or page > 65536 or page & (page - 1):
        raise ValueError("Unsupported page alignment")
    return (x + page - 1) & ~(page - 1)

def boot_v3(f):
    head = bounded_read(f, 0, 4096)
    if head[:8] != b"ANDROID!":
        raise ValueError("Invalid Android boot magic")
    ksize, rsize, os_version, hsize = struct.unpack_from("<IIII", head, 8)
    version, = struct.unpack_from("<I", head, 40)
    if version != 3 or hsize != 1580:
        raise ValueError(f"Unsupported Android Boot header version={version} size={hsize}")
    ko = 4096
    ro = ko + align(ksize, 4096)
    if ksize < 64 or rsize < 8:
        raise ValueError("Kernel or generic ramdisk unexpectedly small")
    if bounded_read(f, ko+56, 4) != b"ARMd":
        raise ValueError("Missing ARM64 kernel magic")
    if bounded_read(f, ro, 2) != b"\x1f\x8b":
        raise ValueError("Unrecognized generic ramdisk compression (expected gzip)")
    return {
        "version": 3, "header_size": hsize, "page_size": 4096,
        "kernel_offset": ko, "kernel_size": ksize,
        "generic_ramdisk_offset": ro, "generic_ramdisk_size": rsize,
        "original_kernel_sha256": sha_stream(f, ko, ksize),
        "generic_ramdisk_sha256": sha_stream(f, ro, rsize),
    }

def vendor_boot_v3(f):
    head = bounded_read(f, 0, 4096)
    if head[:8] != b"VNDRBOOT":
        raise ValueError("Invalid vendor boot magic")
    version, page = struct.unpack_from("<II", head, 8)
    ramdisk_size, = struct.unpack_from("<I", head, 24)
    header_size, dtb_size = struct.unpack_from("<II", head, 2096)
    if version != 3 or header_size != 2112:
        raise ValueError("Unsupported vendor_boot version/header size")
    ro = align(header_size, page)
    do = ro + align(ramdisk_size, page)
    if ramdisk_size < 8 or dtb_size < 40:
        raise ValueError("Invalid vendor ramdisk or DTB size")
    if bounded_read(f, ro, 2) != b"\x1f\x8b":
        raise ValueError("Unrecognized vendor ramdisk compression")
    dtb = bounded_read(f, do, 8)
    if dtb[:4] != b"\xd0\x0d\xfe\xed" or struct.unpack(">I", dtb[4:8])[0] != dtb_size:
        raise ValueError("Device tree FDT header/size mismatch")
    return {
        "version": version, "header_size": header_size, "page_size": page,
        "vendor_ramdisk_offset": ro, "vendor_ramdisk_size": ramdisk_size,
        "dtb_offset": do, "dtb_size": dtb_size,
        "vendor_ramdisk_sha256": sha_stream(f, ro, ramdisk_size),
        "dtb_sha256": sha_stream(f, do, dtb_size),
    }

def dtbo_table(f):
    head = bounded_read(f, 0, 32)
    values = struct.unpack(">8I", head)
    magic, total, hsize, entrysize, count, entries_off, page, version = values
    if magic != 0xD7B7AB1E or total < 64 or count not in range(1, 257):
        raise ValueError("Bad DTBO table header")
    if hsize < 32 or entrysize < 32 or entries_off < hsize or entries_off + count * entrysize > total:
        raise ValueError("DTBO table dimensions inconsistent")
    if version != 0:
        raise ValueError("Only DTBO table v0 supported")
    bounded_read(f, total-1, 1)
    for n in range(count):
        entry = bounded_read(f, entries_off + n*entrysize, 8)
        size, offset = struct.unpack(">II", entry)
        if size < 40 or offset+size > total:
            raise ValueError("DTBO entry invalid")
        fdt = bounded_read(f, offset, 8)
        if fdt[:4] != b"\xd0\x0d\xfe\xed" or struct.unpack(">I", fdt[4:])[0] != size:
            raise ValueError("DTBO entry FDT magic/size mismatch")
    return {
        "version": version, "table_size": total, "count": count,
        "table_sha256": sha_stream(f, 0, total),
    }

def vbmeta_header(f):
    head = bounded_read(f, 0, 256)
    if head[:4] != b"AVB0":
        raise ValueError("Invalid vbmeta magic")
    major, minor = struct.unpack_from(">II", head, 4)
    auth, aux = struct.unpack_from(">QQ", head, 12)
    algo = struct.unpack_from(">I", head, 28)[0]
    flags = struct.unpack_from(">I", head, 120)[0]
    bounded_read(f, 255+auth+aux, 1)
    return {
        "version": f"{major}.{minor}", "algorithm_id": algo, "flags": flags,
        "signature_chain_cryptographically_verified": False,
    }

def audit_local(backups: Path, artifact: Path):
    # Fail closed on any private source or exact non-flashable EXP06 ZIP hash mismatch.
    with artifact.open("rb") as f:
        if sha_stream(f) != verified.INPUTS["EXP06"]["zip_sha256"]:
            raise ValueError("EXP06 artifact ZIP hash mismatch")
    for name, required in EXPECTED.items():
        path = backups/name
        if not path.is_file():
            raise ValueError(f"Missing private backup file: {name}")
        with path.open("rb") as f:
            if sha_stream(f) != required:
                raise ValueError(f"Backup SHA-256 mismatch: {name}")

    with (backups/"boot_b.img").open("rb") as f:
        boot = boot_v3(f)
    with (backups/"vendor_boot_b.img").open("rb") as f:
        vendor = vendor_boot_v3(f)
    with (backups/"dtbo_b.img").open("rb") as f:
        dtbo = dtbo_table(f)
    with (backups/"vbmeta_b.img").open("rb") as f:
        vbmeta = vbmeta_header(f)

    with __import__("zipfile").ZipFile(artifact) as z:
        image = z.read("exp06-work/out/arch/arm64/boot/Image")
        if hashlib.sha256(image).hexdigest() != verified.INPUTS["EXP06"]["image_sha256"]:
            raise ValueError("Experimental kernel hash mismatch")
        if image[56:60] != b"ARMd":
            raise ValueError("Experimental kernel ARM64 magic mismatch")

    if boot["original_kernel_sha256"] != ORIGINAL_KERNEL_HASH:
        raise ValueError("Original kernel payload has changed")
    if boot["generic_ramdisk_sha256"] != ORIGINAL_GENERIC_RAMDISK_HASH:
        raise ValueError("Original generic ramdisk has changed")
    if vendor["vendor_ramdisk_sha256"] != ORIGINAL_VENDOR_RAMDISK_HASH:
        raise ValueError("Original vendor ramdisk has changed")
    if vendor["dtb_sha256"] != EXPECTED_DTB_HASH:
        raise ValueError("Original vendor DTB differs from compiled device tree")
    if dtbo["table_sha256"] != EXPECTED_DTBO_PAYLOAD_HASH:
        raise ValueError("Original DTBO differs from compiled device overlays")
    if boot["kernel_size"] != len(image):
        raise ValueError("Not layout-preserving: candidate differs in kernel size")

    # Only calculate hypothetical kernel span. Do not create a modified boot.img.
    return {
        "status": "PASS_OFFLINE_STRUCTURE_ONLY",
        "flash_ready": False,
        "boot_image_created": False,
        "original_backup_slot": "_b",
        "private_backups_all_full_sha256_verified": True,
        "candidate_exp06_image_sha256": verified.INPUTS["EXP06"]["image_sha256"],
        "hypothetical_kernel_span": {"offset": boot["kernel_offset"], "bytes": boot["kernel_size"]},
        "hypothetical_layout_preserved": True,
        "boot": boot, "vendor_boot": vendor, "dtbo": dtbo, "vbmeta": vbmeta,
        "required_before_any_hardware_test": [
            "Independent recovery and rollback plan validated for Xiaomi Pad 6; preserve original slot B images.",
            "Check AVB/vbmeta policy and boot chain without guessing from flags alone.",
            "Check actual recovery/bootloader access and whether slot A is safe; do not overwrite unknown partitions.",
            "Build and independently validate a flashable image separately, after explicit hardware-test decision.",
            "Document KernelSU root retention and thermal/frequency governor risks.",
        ],
        "limitations": [
            "Metadata/header/hash equality does not prove that experimental kernel boots.",
            "No AVB signature or rollback index chain verification.",
            "No I/O sent to the device; no kernel image or boot.img output.",
        ],
    }

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--backup-dir", type=Path, required=True, help="Local directory containing four *original* slot-B .img backups")
    ap.add_argument("--exp06-zip", type=Path, required=True, help="Original SHA-pinned GitHub Actions EXP06 artifact ZIP")
    ap.add_argument("--report", type=Path, help="Optional report JSON path; never a .img or .zip output")
    args = ap.parse_args()
    if args.report and args.report.suffix.lower() != ".json":
        raise SystemExit("Only a small JSON audit report may be written")
    result = audit_local(args.backup_dir, args.exp06_zip)
    print("EXP11 OFFLINE PREFLIGHT PASS - NO BOOT IMAGE CREATED, NO FLASH")
    print(f"Original kernel span: +{result['hypothetical_kernel_span']['offset']} / {result['hypothetical_kernel_span']['bytes']} bytes")
    print("Hashes validated: boot_b, vendor_boot_b, dtbo_b, vbmeta_b, kernel, ramdisks, DTB, DTBO and EXP06 Image.")
    print("AVB cryptographic verification and recovery prerequisites NOT satisfied.")
    print("FLASH_READY=false")
    if args.report:
        args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Report (not an image): {args.report}")


if __name__ == "__main__":
    main()
