#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 GitHub Actions / E404 RT140 V3-only mm/slub raw list_lock type reconciliation, NO FLASH
"""Repair RT raw_spinlock_t mismatches enabled by SYSFS/PROC in V3 profile.

The original QEMU boot profile compiles without CONFIG_SYSFS. V3 adds
CONFIG_SYSFS=y, exposing two additional SLUB debug-list_lock call sites.
Keep the proven Stage82 mm/page_alloc patch unchanged.
"""
import argparse
import difflib
import hashlib
import json
import re
import subprocess
from pathlib import Path

TARGET = "mm/slub.c"
HEADER = "mm/slab.h"
OLD_DECL = "unsigned long uninitialized_var(flags);"
NEW_DECL = "unsigned long flags;"
LOCK_CALL = re.compile(
    r"\b(?<!raw_)spin_(lock|unlock)(?:_irqsave|_irqrestore|_irq|_init)?"
    r"(?=\s*\(\s*&n->list_lock\b)"
)

def sha(content):
    return hashlib.sha256(content.encode()).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.tree.resolve()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    body = root / TARGET
    hdr = (root / HEADER).read_text()
    assert re.search(r"\braw_spinlock_t\s+list_lock\s*;", hdr), (
        "Expected RT140 raw_spinlock_t kmem_cache_node.list_lock; do not alter non-RT source"
    )
    before = body.read_text()
    fn_start = before.index("static noinline int free_debug_processing(")
    fn_end = before.index("\nstatic int __init setup_slub_debug(", fn_start)
    func = before[fn_start:fn_end]
    assert func.count(OLD_DECL) == 1, "exact free_debug_processing flags declaration changed"
    assert "raw_spin_unlock_irqrestore(&n->list_lock, flags);" in func, (
        "RT140 existing raw unlock missing; cannot infer paired transformation"
    )
    func = func.replace(OLD_DECL, NEW_DECL, 1)
    data = before[:fn_start] + func + before[fn_end:]
    match_names = [m.group() for m in LOCK_CALL.finditer(data)]
    expected = ["spin_lock_irqsave", "spin_lock_irqsave", "spin_unlock_irqrestore"]
    assert sorted(match_names) == sorted(expected), (
        "SLUB unmatched list_lock calls changed: " + repr(match_names)
    )
    after, count = LOCK_CALL.subn(lambda m: "raw_" + m.group(), data)
    assert count == len(expected)
    assert not LOCK_CALL.search(after), "some raw SLUB lock calls still use sleeping spin APIs"
    assert after.count(NEW_DECL) >= 1
    body.write_text(after)
    diff = "".join(difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile="a/mm/slub.c", tofile="b/mm/slub.c"
    ))
    patch = output / "slub-rt-raw-list-lock.patch"
    patch.write_text(diff)
    subprocess.run(["git", "-C", str(root), "diff", "--check"], check=True)
    result = {
        "schema_version": 1,
        "stage": "EXP76_R30_V3_SLUB_RAW_LIST_LOCK",
        "pinned_error_run_id": 42667484946,
        "source": TARGET,
        "type_checked_in": HEADER,
        "before_sha256": sha(before),
        "after_sha256": sha(after),
        "patch_sha256": sha(diff),
        "changes": {
            "uninitialized_var_to_unsigned_long": 1,
            "spin_lock_irqsave_to_raw": 2,
            "spin_unlock_irqrestore_to_raw": 1
        },
        "kernel_config_modified": False,
        "stage82_mm_page_alloc_modified": False,
        "flash_ready": False
    }
    (output / "slub-rt-raw-list-lock.json").write_text(json.dumps(result, indent=2) + "\n")
    print("R30_V3_SLUB_RECONCILED", json.dumps(result, indent=2), flush=True)

if __name__ == "__main__":
    main()
