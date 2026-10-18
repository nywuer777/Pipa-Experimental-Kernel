#!/usr/bin/env python3
"""EXP11: canonical, NON-FLASHABLE digest and audit of EXP06 vs EXP09 Images.

Reuses the SHA-pinned EXP10 forensic verifier. Never writes normalized Image bytes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import exp10_forensic_diff as prior


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonicalize(exp06, exp09):
    # EXP10 raises on unexpected hash, bytes, configuration or classification.
    verified = prior.audit(exp06, exp09)
    src_a, src_b = exp06["image"], exp09["image"]
    a, b = bytearray(src_a), bytearray(src_b)
    differing = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
    assert len(differing) == 39
    move = verified["schedutil_immediate"]
    assert len(move) == 1 and move[0]["offset"] == 538488
    opcode = move[0]["offset"]
    # MOVZ w9 #1500 (EXP06) and MOVZ w9 #2000 (EXP09); only 2 encoded bytes differ.
    actual_code = [i for i in differing if opcode <= i < opcode + 4]
    assert actual_code == [538488, 538489]
    noise = sorted(set(differing) - set(actual_code))
    assert len(noise) == 37

    # Validate all individual noise offsets using structural EXP10 markers.
    timestamps_a, timestamps_b = prior.timestamp_ranges(src_a), prior.timestamp_ranges(src_b)
    ids_a, ids_b = prior.build_id_ranges(src_a), prior.build_id_ranges(src_b)
    allowed = set()
    classes = {}
    def mark(pos, cls):
        if pos not in actual_code:
            if pos in classes and classes[pos] != cls:
                raise ValueError("Ambiguous metadata classification")
            classes[pos] = cls
            allowed.add(pos)

    for start in sorted(set(timestamps_a) & set(timestamps_b)):
        if len(timestamps_a[start]) != len(timestamps_b[start]):
            raise ValueError("Kernel timestamp length mismatch")
        for i in range(start, start + len(timestamps_a[start])):
            if src_a[i] != src_b[i]:
                mark(i, "build_timestamp")

    for start in sorted(set(ids_a) & set(ids_b)):
        for i in range(start, start + 20):
            if src_a[i] != src_b[i]:
                mark(i, "gnu_build_id")

    for i in noise:
        ca, cb = prior.cpio_mtime(src_a, i), prior.cpio_mtime(src_b, i)
        if ca is not None and cb is not None and ca[0] == cb[0]:
            mark(i, "cpio_newc_mtime")

    if sorted(allowed) != noise:
        raise ValueError(f"Unclassified noncode offsets: {sorted(set(noise)-allowed)}")
    counts = {v: list(classes.values()).count(v) for v in sorted(set(classes.values()))}
    if counts != {"build_timestamp": 8, "cpio_newc_mtime": 9, "gnu_build_id": 20}:
        raise ValueError(f"Unexpected metadata classes: {counts}")

    # Canonical digest: in-memory only, mask exactly 37 known changed metadata bytes.
    for p in noise:
        a[p] = b[p] = 0
    canonical_a, canonical_b = sha(a), sha(b)
    assert canonical_a == "4caa2897c7ef654fe9d2d53abc9632882f67f50975397113d1ae4ee27e22185c"
    assert canonical_b == "4e2f82ddeea8bb663e229a390f7d672012d193e77903291a7401f8d70c7a5d2d"
    remaining = [i for i,(x,y) in enumerate(zip(a,b)) if x != y]
    assert remaining == actual_code

    for p in remaining:
        a[p] = b[p] = 0
    common = sha(a)
    if common != sha(b):
        raise ValueError("Unexpected difference outside normalized metadata and MOVZ immediate")
    assert common == "2f87ad47c3c42e9236cece6fc1bd09ee2b72785ac8b25c9beeddae56f914f5ee"
    return {
        "status": "PASS_CANONICAL_NONFLASHABLE",
        "flash_ready": False,
        "images_original_sha256": verified["image_sha256"],
        "images_bytes_each": len(src_a),
        "changed_bytes_original": len(differing),
        "metadata_bytes_normalized": len(noise),
        "metadata_categories": counts,
        "different_bytes_after_metadata_normalization": len(remaining),
        "remaining_offsets": remaining,
        "instruction": move[0],
        "sha256_after_metadata_normalization": {"EXP06": canonical_a, "EXP09": canonical_b},
        "sha256_after_also_masking_two_instruction_bytes": common,
        "other_differences": 0,
        "dtb_sha256": verified["dtb_hash"],
        "dtbo_sha256": verified["dtbo_hash"],
        "method": "Only difference positions recognized by verified EXP10 structures are zeroed in RAM; no canonical Image emitted.",
        "limitations": [
            "Canonical digests are analysis artifacts, not new boot images or independently reproducible builds.",
            "Same compiled code except one MOVZ immediate does not establish startup, root, governor selection, FPS or stability.",
            "No private tablet partition images uploaded; no flash commands or boot.img created.",
        ],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exp06", type=Path, required=True)
    ap.add_argument("--exp09", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    result = canonicalize(prior.read_package(args.exp06, "EXP06"), prior.read_package(args.exp09, "EXP09"))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "EXP11-canonical-digests.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print("EXP11 PASS: normalized 37 metadata bytes; exactly 2 instruction bytes remain.")
    print("SHA after also masking code change:", result["sha256_after_also_masking_two_instruction_bytes"])
    print("NO BOOT IMAGE, NO FLASH, NO MODIFIED KERNEL IMAGE FILE")


if __name__ == "__main__":
    main()
