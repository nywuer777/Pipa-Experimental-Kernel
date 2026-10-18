#!/usr/bin/env python3
"""EXP10: read-only forensic diff of immutable EXP06 and EXP09 artifacts.

This is NOT a compatibility test, boot packer, FPS benchmark, or flashing tool.
Only pinned successful GitHub Actions artifact ZIPs are accepted.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct
import zipfile

INPUTS = {
    "EXP06": {
        "zip_sha256": "e32af6b61163fba4724211986823fc4ffab759956d213ef15b7fcda042241402",
        "image_sha256": "7b3c971a6bd92e8e609e4c56fb6e33df78a7668463e9bcfc342aa1cdee9a0033",
        "prefix": "exp06-work/out",
    },
    "EXP09": {
        "zip_sha256": "f65ec9512217e29dd85419a78420173c81ff83017b51cdc123d4476356273fd6",
        "image_sha256": "0f526f5d70266d4348ddddea592b9f6078e73cd4cfb56163d45b53aaf9633317",
        "prefix": "exp09-work/out",
    },
}
KNOWN_DTB = "9b92c1aa019fffdfaf3bfe36dcd84c2858c804109c100b684e08f62228881117"
KNOWN_DTBO = "6a0e109590742ce67713d738aef1320e015e9abc6b509d5be7f6e9ed46dd4f9c"

def sha(data):
    return hashlib.sha256(data).hexdigest()

def read_package(path, name):
    props = INPUTS[name]
    if sha(path.read_bytes()) != props["zip_sha256"]:
        raise ValueError(f"{name}: pinned artifact ZIP hash mismatch")
    with zipfile.ZipFile(path) as z:
        prefix = props["prefix"]
        def take(key):
            return z.read(f"{prefix}/{key}")
        img = take("arch/arm64/boot/Image")
        if sha(img) != props["image_sha256"] or img[56:60] != b"ARMd":
            raise ValueError(f"{name}: ARM64 Image hash or magic mismatch")
        if len(img) != 30349336:
            raise ValueError(f"{name}: unexpected ARM64 Image size")
        cfg = take(".config").decode("utf-8")
        dtb, dtbo = take("arch/arm64/boot/dtb"), take("arch/arm64/boot/dtbo.img")
        if sha(dtb) != KNOWN_DTB or sha(dtbo) != KNOWN_DTBO:
            raise ValueError(f"{name}: DTB or DTBO does not match backed-up device")
        return {"image": img, "config": cfg, "dtb": dtb, "dtbo": dtbo}

def parse_config(content):
    cfg = {}
    for line in content.splitlines():
        m = re.match(r"^(CONFIG_[A-Z0-9_]+)=(.*)$", line)
        if m:
            cfg[m.group(1)] = m.group(2)
        m = re.match(r"^# (CONFIG_[A-Z0-9_]+) is not set$", line)
        if m:
            cfg[m.group(1)] = "n"
    return cfg

def get_diff_runs(indices):
    if not indices:
        return []
    runs = []
    begin = end = indices[0]
    for i in indices[1:]:
        if i != end + 1:
            runs.append({"offset": begin, "bytes": end - begin + 1})
            begin = i
        end = i
    runs.append({"offset": begin, "bytes": end - begin + 1})
    return runs

def timestamp_ranges(img):
    found = {}
    pattern = rb"#[0-9]+ SMP PREEMPT [A-Za-z]{3} [A-Za-z]{3} +[0-9]{1,2} [0-9:]{8} UTC [0-9]{4}"
    for m in re.finditer(pattern, img):
        found[m.start()] = img[m.start():m.end()].decode("ascii")
    return found

def build_id_ranges(img):
    sig = struct.pack("<III", 4, 20, 3) + b"GNU\x00"
    result = {}
    start = 0
    while True:
        i = img.find(sig, start)
        if i < 0:
            break
        result[i + len(sig)] = img[i + len(sig):i + len(sig) + 20].hex()
        start = i + 1
    return result

def cpio_mtime(img, pos):
    # newc: 6 byte ASCII header, 5 eight-byte fields before mtime
    magic = img.rfind(b"070701", max(0, pos - 110), pos + 1)
    if magic < 0 or not 46 <= (pos - magic) < 54:
        return None
    h = img[magic + 46:magic + 54]
    if not re.fullmatch(rb"[0-9A-Fa-f]{8}", h):
        return None
    return magic, h.decode("ascii")

def movz_instruction(a, b, pos):
    off = (pos // 4) * 4
    if off + 4 > len(a):
        return None
    x = struct.unpack_from("<I", a, off)[0]
    y = struct.unpack_from("<I", b, off)[0]
    # AArch64 MOVZ (32-bit register), same destination/shift/opcode.
    imm_mask = 0xFFFF << 5
    if (x & 0x7F800000) != 0x52800000:
        return None
    if (x & ~imm_mask) != (y & ~imm_mask):
        return None
    ia, ib = (x >> 5) & 0xFFFF, (y >> 5) & 0xFFFF
    if (ia, ib) != (1500, 2000):
        return None
    return {"offset": off, "register": "w" + str(x & 0x1F),
            "experimental_immediate": ia, "control_immediate": ib,
            "experimental_instruction_hex": hex(x), "control_instruction_hex": hex(y)}

def audit(exp06, exp09):
    a, b = exp06["image"], exp09["image"]
    ca, cb = parse_config(exp06["config"]), parse_config(exp09["config"])
    conf_diff = [
        {"symbol": k, "exp06": ca.get(k, "<not listed>"), "exp09": cb.get(k, "<not listed>")}
        for k in sorted(ca.keys() | cb.keys())
        if ca.get(k) != cb.get(k)
    ]
    diffs = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
    ta, tb = timestamp_ranges(a), timestamp_ranges(b)
    ida, idb = build_id_ranges(a), build_id_ranges(b)
    classes = {}
    moves = {}
    mtimes = {}
    for i in diffs:
        marked = False
        for start in (set(ta) & set(tb)):
            if start <= i < start + len(ta[start]):
                classes[i] = "build_timestamp"
                marked = True
                break
        if marked:
            continue
        for start in (set(ida) & set(idb)):
            if start <= i < start + 20:
                classes[i] = "gnu_build_id"
                marked = True
                break
        if marked:
            continue
        c1, c2 = cpio_mtime(a, i), cpio_mtime(b, i)
        if c1 and c2 and c1[0] == c2[0]:
            classes[i] = "initramfs_cpio_mtime"
            mtimes[c1[0]] = {"offset": c1[0], "exp06": c1[1], "exp09": c2[1]}
            continue
        insn = movz_instruction(a, b, i)
        if insn:
            classes[i] = "schedutil_movz_instruction"
            moves[insn["offset"]] = insn
            continue
        classes[i] = "UNCLASSIFIED"
    by_type = dict(sorted(Counter(classes.values()).items()))
    # Intentionally pin the expected diff to detect any future artifact drift.
    if conf_diff != [
        {"symbol": "CONFIG_PIPA_EXP_SUGOV", "exp06": "y", "exp09": "<not listed>"},
        {"symbol": "CONFIG_PIPA_EXP_SUGOV_RATE_LIMIT_US", "exp06": "1500", "exp09": "<not listed>"},
    ]:
        raise ValueError(f"Unexpected config differences: {conf_diff}")
    if len(diffs) != 39 or "UNCLASSIFIED" in by_type or len(moves) != 1:
        raise ValueError("Diff is not the expected 39-byte classified baseline")
    if by_type != {"build_timestamp": 8, "gnu_build_id": 20, "initramfs_cpio_mtime": 9,
                   "schedutil_movz_instruction": 2}:
        raise ValueError(f"Unexpected byte-difference classes: {by_type}")
    return {
        "status": "PASS_NONFLASHABLE_FORENSIC_COMPARISON",
        "flash_ready": False,
        "source": "Two immutable, SHA-256-verified GitHub Actions successful build artifacts",
        "image_length_bytes": len(a),
        "image_sha256": {"EXP06": sha(a), "EXP09": sha(b)},
        "images_equal_length": len(a) == len(b),
        "arm64_headers_equal": a[:64] == b[:64],
        "different_bytes": len(diffs),
        "different_percentage": round(100.0 * len(diffs) / len(a), 8),
        "changed_pages_4k": sorted({i // 4096 for i in diffs}),
        "changed_blocks_1m": sorted({i // (1024 * 1024) for i in diffs}),
        "runs": get_diff_runs(diffs),
        "classification_byte_counts": by_type,
        "schedutil_immediate": list(moves.values()),
        "build_timestamps": {
            "EXP06": list(ta.values()),
            "EXP09": list(tb.values()),
        },
        "gnu_build_ids": {"EXP06": ida, "EXP09": idb},
        "cpio_mtimes": list(mtimes.values()),
        "config_difference_count": len(conf_diff),
        "config_differences": conf_diff,
        "dtb_hash": sha(exp06["dtb"]),
        "dtbo_hash": sha(exp06["dtbo"]),
        "disclaimers": [
            "Binary equivalence outside classified changes does not establish device bootability.",
            "Code change is an immediate from 2000 to 1500; runtime governor behavior and FPS are not tested.",
            "Independent builds contain timestamp/embedded cpio mtime and GNU build-id noise.",
            "Do not flash this output or any raw Image."
        ],
    }

def make_markdown(d):
    cs = d["classification_byte_counts"]
    move = d["schedutil_immediate"][0]
    return f"""# EXP10 — Comparison of clean E404 control and experimental schedutil

**Status:** {d['status']} — **not flashable**.

| Measure | Observed |
|---|---|
| Image size | {d['image_length_bytes']:,} bytes (both) |
| Different bytes | {d['different_bytes']} ({d['different_percentage']}%) |
| Modified 4-KiB pages | {len(d['changed_pages_4k'])} |
| Distinct contiguous diff runs | {len(d['runs'])} |
| Kconfig differences | {d['config_difference_count']} |
| DTB | identical; SHA256 {d['dtb_hash']} |
| DTBO | identical; SHA256 {d['dtbo_hash']} |

## Forensic classification of the 39 differing bytes

- **2 bytes, schedutil immediate:** the complete 32-bit ARM64 \`MOVZ {move['register']}\` at file offset **{move['offset']}** changes from \`#{move['control_immediate']}\` (EXP09) to \`#{move['experimental_immediate']}\` (EXP06). The instruction class and destination register are unchanged. This is direct evidence of the patched default rate-limit constant.
- **{cs['build_timestamp']} bytes:** two embedded kernel build timestamps.
- **{cs['gnu_build_id']} bytes:** GNU ELF build ID note, which reflects differences in output binaries.
- **{cs['initramfs_cpio_mtime']} bytes:** three embedded newc CPIO archive modification-time fields. This does **not** mean the contents of a user's ramdisk were changed; these bytes are inside compiled Image build data.

The only differing kernel configuration keys are:
- \`CONFIG_PIPA_EXP_SUGOV\`: EXP06 \`y\`, EXP09 not listed.
- \`CONFIG_PIPA_EXP_SUGOV_RATE_LIMIT_US\`: EXP06 \`1500\`, EXP09 not listed.

\`CONFIG_MODULES\`, \`CONFIG_KSU\`, and the other common kernel configuration values match between the two builds.

This comparison distinguishes the immediate change from known build noise. It does **not** prove boot success, root compatibility, performance benefit, battery behavior or thermal stability. No boot.img is generated and no partition is written.

## Source

- EXP06: GitHub Actions #39136149722, artifact pipa-exp06-clang21-1.
- EXP09: GitHub Actions #39140258202, artifact pipa-exp09-clean-control-1.
- Both use Android Clang 21 build 14054515 and E404 commit fed88a6024cd4d46c52eda607a95d97d7371ba81.
"""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exp06", type=Path, required=True)
    parser.add_argument("--exp09", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("exp10-report"))
    args = parser.parse_args()
    result = audit(read_package(args.exp06, "EXP06"), read_package(args.exp09, "EXP09"))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "EXP10-differential.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    (args.out / "EXP10-differential.md").write_text(make_markdown(result), encoding="utf-8")
    print(f"EXP10 PASS: {result['different_bytes']} bytes in {len(result['changed_pages_4k'])} pages; "
          f"{result['config_difference_count']} Kconfig differences; "
          f"{result['classification_byte_counts']}")
    print("No boot.img, no flash, no device access. NONFLASHABLE.")

if __name__ == "__main__":
    main()
