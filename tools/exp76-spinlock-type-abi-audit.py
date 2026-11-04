#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 RT spinlock ABI read-only inspection
"""Check vendor lockdep wait types before replacing spinlock_types.h."""
import argparse
import hashlib
import json
from pathlib import Path

FILES = (
    "include/linux/spinlock_types.h",
    "include/linux/spinlock_types_raw.h",
    "include/linux/spinlock_types_nort.h",
    "include/linux/spinlock_types_rt.h",
    "include/linux/rwlock_types_rt.h",
)
TOKENS = (
    "typedef struct raw_spinlock", "typedef struct spinlock",
    "RAW_SPIN_DEP_MAP_INIT", "SPIN_DEP_MAP_INIT", "LD_WAIT_SPIN",
    "LD_WAIT_CONFIG", "__RAW_SPIN_LOCK_INITIALIZER",
    "__SPIN_LOCK_INITIALIZER", "DEFINE_SPINLOCK", "CONFIG_PREEMPT_RT_FULL",
)


def analyze(tree, report):
    data = {}
    snapshots = {}
    for path in FILES:
        file = tree / path
        if not file.is_file():
            raise ValueError("Required RT spinlock header missing: " + path)
        body = file.read_text(encoding="utf-8")
        data[path] = body
        snapshots[path] = {
            "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
            "tokens": {key: body.count(key) for key in TOKENS},
        }
    vendor = data[FILES[0]]
    checks = {
        "vendor_spinlock_lockdep_inner_spin": "LD_WAIT_SPIN" in vendor,
        "vendor_spinlock_lockdep_config": "LD_WAIT_CONFIG" in vendor,
        "vendor_raw_lockdep_initializer": "RAW_SPIN_DEP_MAP_INIT" in vendor,
        "split_raw_spinlock_type_present": "raw_spinlock" in data[FILES[1]],
        "split_nort_spinlock_type_present": "spinlock" in data[FILES[2]],
        "split_rt_spinlock_type_present": "spinlock" in data[FILES[3]],
        "vendor_header_reject_unresolved": (tree / (FILES[0] + ".rej")).is_file(),
    }
    if not all(checks.values()):
        raise ValueError("RT spinlock ABI evidence incomplete: " + json.dumps(checks))
    report.mkdir(parents=True, exist_ok=True)
    (report / "headers-contract.json").write_text(json.dumps({
        "checks": checks, "snapshots": snapshots
    }, indent=2) + "\n")
    lines = [
        "# EXP76 RT spinlock-types ABI review",
        "",
        "Source-only audit. No header replacement or RT build.",
        "The E404 header uses LD_WAIT_SPIN for raw locks and LD_WAIT_CONFIG",
        "for regular locks. Moving these to upstream split headers must",
        "preserve lockdep semantics and initializer layout.",
        "",
    ]
    for path in FILES:
        lines += ["## " + path, ""]
        body = data[path].splitlines()
        hits = sorted({
            j for i, line in enumerate(body) if any(key in line for key in TOKENS)
            for j in range(max(0, i-2), min(len(body), i+4))
        })
        lines += [str(i+1).rjust(5) + " " + body[i] for i in hits]
        lines += [""]
    lines += ["Header integration blocked until manual semantic review.",
              "FLASH_READY=false", ""]
    (report / "HEADER_ABI_REVIEW.md").write_text("\n".join(lines))
    return checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    checks = analyze(args.tree.resolve(), args.report.resolve())
    print(json.dumps(checks, indent=2))
    print("EXP76_SPINLOCK_TYPES_ABI_AUDIT=PASS; HEADER_PORT=BLOCKED; FLASH_READY=false")


if __name__ == "__main__":
    main()
