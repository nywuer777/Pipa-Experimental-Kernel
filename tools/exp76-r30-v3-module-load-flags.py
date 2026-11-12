#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 GitHub Actions / E404 RT140 V3-only remove forced module compatibility overrides / NO FLASH
"""Restore module loader's normal caller flags for actual RT spinlock probe.

The pinned E404 kernel/module.c sets IGNORE_MODVERSIONS and IGNORE_VERMAGIC
unconditionally inside load_module(). With CONFIG_MODULE_FORCE_LOAD=n,
check_modinfo() treats modmagic as absent and rejects module with -ENOEXEC.
The replacement leaves all ELF/vermagic/modversion checks active; it does
not change any kernel Kconfig nor the validated Stage82 mm/page_alloc fix.
"""
import argparse
import difflib
import hashlib
import json
import subprocess
from pathlib import Path

FILE = "kernel/module.c"
OLD = "\t//FIXME\n\tflags |= MODULE_INIT_IGNORE_MODVERSIONS;\n\tflags |= MODULE_INIT_IGNORE_VERMAGIC;\n"
NEW = "\t/* Honor only the module init flags supplied by the caller. */\n"

def digest(data):
    return hashlib.sha256(data.encode()).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    tree = args.tree.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    target = tree / FILE
    before = target.read_text()
    assert before.count(OLD) == 1, "expected exactly one pinned vendor module force-load override"
    assert "if (flags & MODULE_INIT_IGNORE_VERMAGIC)" in before
    assert "return -ENOEXEC;" in before
    start = before.index("static int load_module(")
    end = before.index("SYSCALL_DEFINE3(init_module", start)
    chunk = before[start:end]
    assert chunk.count(OLD) == 1, "forced flags must reside in load_module"
    after = before.replace(OLD, NEW, 1)
    target.write_text(after)
    assert after.count("flags |= MODULE_INIT_IGNORE_VERMAGIC;") == 0
    assert after.count("flags |= MODULE_INIT_IGNORE_MODVERSIONS;") == 0
    diff = "".join(difflib.unified_diff(
        before.splitlines(True), after.splitlines(True),
        fromfile="a/" + FILE, tofile="b/" + FILE
    ))
    patch = out / "normal-module-flags.patch"
    patch.write_text(diff)
    subprocess.run(["git", "-C", str(tree), "diff", "--check"], check=True)
    data = {
        "schema_version": 1, "stage": "EXP76_R30_V3_NORMAL_MODULE_FLAGS",
        "target": FILE, "source_sha256_before": digest(before),
        "source_sha256_after": digest(after), "patch_sha256": digest(diff),
        "removed_forced_flags": ["MODULE_INIT_IGNORE_MODVERSIONS", "MODULE_INIT_IGNORE_VERMAGIC"],
        "flags_preserved_from_caller": True,
        "force_load_enabled": False, "vermagic_check_bypassed": False,
        "modversion_check_bypassed": False, "source_kernel_config_changed": False,
        "page_alloc_stage82_changed": False,
        "prior_gdb_run_id": 43262106875,
        "prior_gdb_failure_exit": "load_module+0x4ac returns -ENOEXEC on vermagic modinfo",
        "flash_ready": False
    }
    (out / "normal-module-flags.json").write_text(json.dumps(data, indent=2) + "\n")
    print("EXP76_R30_V3_NORMAL_MODULE_FLAGS", json.dumps(data, indent=2), flush=True)

if __name__ == "__main__":
    main()
