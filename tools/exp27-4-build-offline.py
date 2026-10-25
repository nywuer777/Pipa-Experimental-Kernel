#!/usr/bin/env python3
"""EXP27.4: offline Android Boot v3 candidate packer, no ADB/Fastboot/flash access.

Requires the user's locally verified STOCK compact boot and the pinned EXP27.1
GitHub Actions ZIP. Never uploads or modifies a source or device.
"""
import argparse
import hashlib
import json
import struct
import sys
import zipfile
from pathlib import Path

PAGE = 4096
BOOT_HEADER_SIZE = 1580
STOCK_COMPACT_SHA = "202aaaf67fe5c0a963965c4e29f67866b509916e0bdff15dde38ef55b3d321e7"
STOCK_KERNEL_SHA = "a72fff8f285419f6f45c7e3d1c43fb1fe5958878b5ce53ab9291148ad9b7acdd"
STOCK_RAMDISK_SHA = "d2a62b4ca809b28ddd0ae25388af051c874fbacfecb6b965243b7d6b81465ee9"
NEW_KERNEL_SHA = "a14b536b471c97db877482afe97bcbeb97daa74ebc48a3a344d90ead57d56967"
UPSTREAM_R8152_BLOB = "92b51c4c46f57b660f3053804ba74f6df9e71c76"
STOCK_SIZE = 32206848
STOCK_KERNEL_SIZE = 30349336
STOCK_RAMDISK_SIZE = 1849345
KERNEL_ZIP_PATH = "exp06-work/out/arch/arm64/boot/Image"
SOURCE_ZIP_PATH = "exp27-r8152-stage-gate.txt"
LINK_ZIP_PATH = "exp24-rtl8153-link-gate.txt"
TOUCH_ZIP_PATH = "exp25-touch-final-gate.log"
OUTPUT_NAME = "EXP27.4-RTL8153-NOT-FOR-FLASH.candidate.bin"
REPORT_NAME = "EXP27.4-offline-audit.json"

def sha(data):
    return hashlib.sha256(data).hexdigest()

def align(v):
    return (v + PAGE - 1) // PAGE * PAGE

def verify_stock(data, *, expected_hash=STOCK_COMPACT_SHA,
                 expected_kernel_hash=STOCK_KERNEL_SHA,
                 expected_ramdisk_hash=STOCK_RAMDISK_SHA,
                 require_pinned_layout=True):
    if sha(data) != expected_hash:
        raise ValueError("original compact stock SHA256 mismatch")
    if len(data) != (STOCK_SIZE if require_pinned_layout else len(data)):
        raise ValueError("original compact stock size mismatch")
    if len(data) < PAGE or data[:8] != b"ANDROID!":
        raise ValueError("not a compact Android Boot v3 header")
    kernel_size, ramdisk_size, os_version, hsize = struct.unpack_from("<4I", data, 8)
    version = struct.unpack_from("<I", data, 40)[0]
    if hsize != BOOT_HEADER_SIZE or version != 3:
        raise ValueError("Android Boot header version/size not v3/1580")
    if kernel_size < 64 or ramdisk_size < 8:
        raise ValueError("invalid stock kernel/ramdisk size")
    if require_pinned_layout and (kernel_size != STOCK_KERNEL_SIZE or
                                 ramdisk_size != STOCK_RAMDISK_SIZE):
        raise ValueError("stock kernel/ramdisk sizes differ from audited control")
    k_off = PAGE
    r_off = k_off + align(kernel_size)
    end = r_off + align(ramdisk_size)
    if len(data) != end:
        raise ValueError("unexpected original compact boot trailing bytes")
    kernel = data[k_off:k_off + kernel_size]
    ramdisk = data[r_off:r_off + ramdisk_size]
    if sha(kernel) != expected_kernel_hash or sha(ramdisk) != expected_ramdisk_hash:
        raise ValueError("original stock kernel or generic ramdisk hash mismatch")
    if kernel[56:60] != b"ARM\x64" or ramdisk[:2] != b"\x1f\x8b":
        raise ValueError("stock ARM64 Image or gzip ramdisk signature mismatch")
    if (any(data[k_off + kernel_size:r_off])
            or any(data[r_off + ramdisk_size:end])):
        raise ValueError("stock padding is not canonical zero")
    if any(data[BOOT_HEADER_SIZE:PAGE]):
        raise ValueError("unexpected non-zero stock header padding")
    return {
        "kernel_size": kernel_size,
        "ramdisk_size": ramdisk_size,
        "os_version_word": os_version,
        "header_size": hsize,
        "header_version": version,
        "ramdisk": ramdisk,
        "cmdline": data[44:1580],
        "header": data[:PAGE],
        "stock_compact_sha256": sha(data),
    }

def read_exp27_zip(path, *, expected_image_hash=NEW_KERNEL_SHA):
    if path.stat().st_size > 160 * 1024 * 1024:
        raise ValueError("candidate CI ZIP exceeds safety limit")
    with zipfile.ZipFile(path) as z:
        for name in (KERNEL_ZIP_PATH, SOURCE_ZIP_PATH, LINK_ZIP_PATH,
                     TOUCH_ZIP_PATH):
            found = [i for i in z.infolist() if i.filename == name and not i.is_dir()]
            if len(found) != 1:
                raise ValueError("CI archive missing/duplicate expected entry: " + name)
            if found[0].file_size > 70 * 1024 * 1024:
                raise ValueError("CI entry size exceeds safety limit: " + name)
        image = z.read(KERNEL_ZIP_PATH)
        provenance = z.read(SOURCE_ZIP_PATH).decode("utf-8")
        link = z.read(LINK_ZIP_PATH).decode("utf-8")
        touch = z.read(TOUCH_ZIP_PATH).decode("utf-8")
    if sha(image) != expected_image_hash:
        raise ValueError("EXP27.1 Image SHA256 mismatch")
    if not (27_000_000 < len(image) < 36_000_000):
        raise ValueError("unexpected candidate kernel Image size")
    if image[56:60] != b"ARM\x64":
        raise ValueError("EXP27 Image ARM64 signature missing")
    if b"v1.10.11" not in image:
        raise ValueError("compiled EXP27 Image lacks pinned driver version")
    if ("R8152_TARGET=v1.10.11" not in provenance or
            UPSTREAM_R8152_BLOB not in provenance or
            "EXP24_RTL8153_LINK_PASS" not in link or
            "EXP25A_NVT_IRQ_GATE=PASS" not in touch):
        raise ValueError("EXP27 CI source/link/touch integrity gates missing")
    return image

def build(stock, kernel, *, expected_stock_sha=STOCK_COMPACT_SHA,
          expected_old_kernel_sha=STOCK_KERNEL_SHA,
          expected_ramdisk_sha=STOCK_RAMDISK_SHA,
          expected_new_sha=NEW_KERNEL_SHA, pinned=True):
    info = verify_stock(stock, expected_hash=expected_stock_sha,
                        expected_kernel_hash=expected_old_kernel_sha,
                        expected_ramdisk_hash=expected_ramdisk_sha,
                        require_pinned_layout=pinned)
    if sha(kernel) != expected_new_sha or kernel[56:60] != b"ARM\x64":
        raise ValueError("new kernel SHA or ARM64 signature mismatch")
    if not (64 < len(kernel) < 64 * 1024 * 1024):
        raise ValueError("invalid replacement kernel size")
    hdr = bytearray(info["header"])
    struct.pack_into("<I", hdr, 8, len(kernel))
    ramdisk = info["ramdisk"]
    candidate = (bytes(hdr) + kernel +
                 bytes(align(len(kernel)) - len(kernel)) +
                 ramdisk + bytes(align(len(ramdisk)) - len(ramdisk)))
    off = PAGE + align(len(kernel))
    if (candidate[:8] != b"ANDROID!" or
            struct.unpack_from("<I", candidate, 40)[0] != 3 or
            candidate[44:1580] != info["cmdline"] or
            candidate[off:off + len(ramdisk)] != ramdisk or
            sha(candidate[PAGE:PAGE + len(kernel)]) != expected_new_sha):
        raise ValueError("candidate postbuild invariants failed")
    if candidate[:8] + candidate[12:PAGE] != stock[:8] + stock[12:PAGE]:
        raise ValueError("header bytes changed outside kernel-size field")
    return candidate, {
        "cycle": "EXP27.4",
        "result": "OFFLINE_CANDIDATE_CREATED_UNTESTED",
        "baseline_stock_sha256": info["stock_compact_sha256"],
        "source_exp27_image_sha256": expected_new_sha,
        "candidate_sha256": sha(candidate),
        "candidate_bytes": len(candidate),
        "stock_header_version": 3,
        "stock_header_size": info["header_size"],
        "candidate_kernel_size": len(kernel),
        "ramdisk_sha256": sha(ramdisk),
        "ramdisk_identical": True,
        "cmdline_identical": True,
        "os_version_word_identical": True,
        "header_other_bytes_identical": True,
        "stock_canonical_layout": True,
        "device_partitions_modified": False,
        "boot_tested": False,
        "recovery_verified": False,
        "temporary_boot_authorized": False,
        "flash_ready": False,
    }

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stock", type=Path, required=True,
                   help="Local previously verified stock compact boot control (not full partition)")
    p.add_argument("--artifact", type=Path, required=True,
                   help="Official pinned EXP27.1 Actions artifact ZIP (run 40152429269)")
    p.add_argument("--output-dir", type=Path, required=True,
                   help="New non-existing destination directory; never overwritten")
    args = p.parse_args(argv)
    try:
        if not args.stock.is_file() or not args.artifact.is_file():
            raise ValueError("local stock control or CI artifact not found")
        stock = args.stock.read_bytes()
        candidate_kernel = read_exp27_zip(args.artifact)
        candidate, report = build(stock, candidate_kernel)
        if args.output_dir.exists():
            raise ValueError("destination directory already exists (refuse overwrite)")
        resolved_out = args.output_dir.resolve()
        if resolved_out in (args.stock.resolve(), args.artifact.resolve()):
            raise ValueError("destination aliases an input")
        args.output_dir.mkdir(parents=True, exist_ok=False)
        out_path = args.output_dir / OUTPUT_NAME
        with out_path.open("xb") as f:
            f.write(candidate)
        if sha(out_path.read_bytes()) != report["candidate_sha256"]:
            raise ValueError("candidate on-disk SHA differs after creation")
        report_path = args.output_dir / REPORT_NAME
        with report_path.open("x", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print("EXP27.4_RESULT=OFFLINE_CANDIDATE_CREATED_UNTESTED")
        print("CANDIDATE_SHA256=" + report["candidate_sha256"])
        print("CANDIDATE_BYTES=" + str(report["candidate_bytes"]))
        print("OUTPUT=" + str(out_path))
        print("AUDIT=" + str(report_path))
        print("NO_DEVICE_ACCESS; TEMP_BOOT_AUTHORIZED=false; FLASH_READY=false")
        return 0
    except (OSError, ValueError, zipfile.BadZipFile, UnicodeError) as exc:
        print("EXP27.4_GATE=FAIL: " + str(exc), file=sys.stderr)
        print("NO_DEVICE_ACCESS; TEMP_BOOT_AUTHORIZED=false; FLASH_READY=false",
              file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
