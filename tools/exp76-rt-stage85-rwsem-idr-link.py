#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage85 RT rwsem and IDR ABI link repair / NO FLASH
"""Restore public rwsem entry points and preload-end local unlock in the RT tree.

The E404 upstream-vendor rwsem.c bundles non-RT internals with the public
wrappers. Stage7 correctly removed that implementation under PREEMPT_RT_FULL
but also removed its public API. Extract the vendor's generic wrapper block,
omitting only down_read_interruptible (RT low-level lacks this interface), and
build it as rwsem-rt-api.o alongside upstream rwsem-rt.o. Restore the missing
idr_preload_end() next to idr_preload() using the same RT local lock.
Keep all 64 rejects. Never link an ordinary semaphore implementation under RT.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

STAGE = "EXP76_STAGE85_RWSEM_RT_PUBLIC_API_IDR_PRELOAD_END_NONFLASH"
REPORT = "stage85-status.json"
MAKE = "kernel/locking/Makefile"
VENDOR_RWSEM = "kernel/locking/rwsem.c"
RT_RWSEM = "kernel/locking/rwsem-rt.c"
RT_HEADER = "include/linux/rwsem_rt.h"
API = "kernel/locking/rwsem-rt-api.c"
RADIX = "lib/radix-tree.c"
IDR = "include/linux/idr.h"
ANCHOR = "obj-$(CONFIG_PREEMPT_RT_FULL) += mutex-rt.o rwsem-rt.o rwlock-rt.o\n"
NEW_KBUILD = ANCHOR + "obj-$(CONFIG_PREEMPT_RT_FULL) += rwsem-rt-api.o\n"
PUBLIC_START = "void __sched down_read(struct rw_semaphore *sem)\n"
PUBLIC_END = "#ifdef CONFIG_DEBUG_LOCK_ALLOC\n"
EXCLUDED_START = "int __sched down_read_interruptible(struct rw_semaphore *sem)\n"
EXCLUDED_END = "int __sched down_read_killable(struct rw_semaphore *sem)\n"
PUBLIC_FUNCS = (
    "down_read", "down_read_killable", "down_read_trylock",
    "down_write", "down_write_killable", "down_write_trylock",
    "up_read", "up_write", "downgrade_write",
)
LOWLEVEL = (
    "__down_read", "__down_read_killable", "__down_read_trylock",
    "__down_write", "__down_write_killable", "__down_write_trylock",
    "__up_read", "__up_write", "__downgrade_write",
)
PRELOAD_ANCHOR = "EXPORT_SYMBOL(idr_preload);\n"
PRELOAD_END = (
    "\nvoid idr_preload_end(void)\n"
    "{\n"
    "\tlocal_unlock(radix_tree_preloads_lock);\n"
    "}\n"
    "EXPORT_SYMBOL(idr_preload_end);\n"
)
HEAD = (
    "// SPDX-License-Identifier: GPL-2.0\n"
    "/* EXP76: public rwsem API calls backed by PREEMPT_RT implementation. */\n"
    "#include <linux/types.h>\n"
    "#include <linux/kernel.h>\n"
    "#include <linux/sched.h>\n"
    "#include <linux/sched/debug.h>\n"
    "#include <linux/export.h>\n"
    "#include <linux/rwsem.h>\n"
    "#include <linux/atomic.h>\n"
    "#include \"rwsem.h\"\n\n"
    "#ifndef CONFIG_PREEMPT_RT_FULL\n"
    "#error \"rwsem-rt-api.c is exclusively for PREEMPT_RT_FULL\"\n"
    "#endif\n\n"
)


def once(source: str, anchor: str, name: str) -> None:
    if source.count(anchor) != 1:
        raise ValueError(
            f"Stage85 {name} anchor mismatch: {source.count(anchor)}"
        )


def prepare(tree: Path) -> tuple[dict[str, str], dict]:
    if not (tree / ".git").is_dir():
        raise ValueError("Stage85 requires E404 isolated trial Git tree")
    required = (MAKE, VENDOR_RWSEM, RT_RWSEM, RT_HEADER, RADIX, IDR)
    for path in required:
        if not (tree / path).is_file():
            raise ValueError("Stage85 required pinned source missing: " + path)
    if (tree / API).exists():
        raise ValueError("Stage85 RT public API already present")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage85 requires 64 outstanding PREEMPT_RT rejects")
    make = (tree / MAKE).read_text(encoding="utf-8")
    once(make, ANCHOR, "RT Kbuild object list")
    if "rwsem-rt-api.o" in make:
        raise ValueError("Stage85 duplicate RWSEM API object")
    rt = (tree / RT_RWSEM).read_text(encoding="utf-8")
    header = (tree / RT_HEADER).read_text(encoding="utf-8")
    for item in LOWLEVEL:
        if not re.search(r"\b" + re.escape(item) + r"\s*\(", rt):
            raise ValueError("Stage85 RT lower-level implementation missing: " + item)
        if f"{item}(struct rw_semaphore *sem)" not in header:
            raise ValueError("Stage85 RT header signature missing: " + item)
    vendor = (tree / VENDOR_RWSEM).read_text(encoding="utf-8")
    once(vendor, PUBLIC_START, "E404 down_read wrapper")
    # Source is E404 at end of file, not a copied 4.19.325 generic rwsem.
    first = vendor.index(PUBLIC_START)
    stop = vendor.find(PUBLIC_END, first)
    if stop < first:
        raise ValueError("Stage85 E404 public wrapper section missing")
    shared = vendor[first:stop]
    once(shared, EXCLUDED_START, "non-RT-only interruptible wrapper")
    once(shared, EXCLUDED_END, "RT-supported killable wrapper")
    start = shared.index(EXCLUDED_START)
    end = shared.index(EXCLUDED_END, start)
    skip = shared[start:end]
    if "EXPORT_SYMBOL(down_read_interruptible);" not in skip:
        raise ValueError("Stage85 interruptible wrapper block drift")
    shared = shared[:start] + shared[end:]
    for func in PUBLIC_FUNCS:
        once(shared, f"EXPORT_SYMBOL({func});", func)
    if "rwsem_set_owner(" in shared or "rwsem_clear_owner(" in shared:
        raise ValueError("Stage85 vendor-only rwsem owner calls in public wrappers")
    public = HEAD + shared.rstrip() + "\n"

    radix = (tree / RADIX).read_text(encoding="utf-8")
    idr = (tree / IDR).read_text(encoding="utf-8")
    once(radix, PRELOAD_ANCHOR, "idr_preload export")
    once(idr, "void idr_preload_end(void);", "RT idr header declaration")
    if "void idr_preload_end(void)\n{" in radix:
        raise ValueError("Stage85 idr_preload_end implementation already present")
    for x in (
        "static DEFINE_LOCAL_IRQ_LOCK(radix_tree_preloads_lock);",
        "local_lock(radix_tree_preloads_lock);",
        "local_unlock(radix_tree_preloads_lock);",
        "#include <linux/locallock.h>",
    ):
        if x not in radix:
            raise ValueError("Stage85 radix-tree RT local_lock ABI missing: " + x)
    new_radix = radix.replace(PRELOAD_ANCHOR, PRELOAD_ANCHOR + PRELOAD_END, 1)
    new_make = make.replace(ANCHOR, NEW_KBUILD, 1)
    if new_radix.replace(PRELOAD_ANCHOR + PRELOAD_END, PRELOAD_ANCHOR, 1) != radix:
        raise ValueError("Stage85 unexpected radix-tree source change")
    if new_make.replace(NEW_KBUILD, ANCHOR, 1) != make:
        raise ValueError("Stage85 unexpected locking Kbuild change")
    files = {MAKE: new_make, RADIX: new_radix, API: public}
    result = {
        "stage": STAGE,
        "files_patched": sorted(files),
        "rt_public_wrapper_count": len(PUBLIC_FUNCS),
        "rt_public_symbols": list(PUBLIC_FUNCS),
        "non_rt_vendor_rwsem_not_linked": True,
        "idr_preload_end_uses_local_unlock": True,
        "idr_preload_lock_pair_preserved": True,
        "rt_rwsem_lowlevel_preserved": True,
        "rejected_files_remaining": 64,
        "source_sha256": {
            name: hashlib.sha256(content.encode()).hexdigest()
            for name, content in files.items()
        },
        "full_kernel_link_performed": False,
        "runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    return files, result


def execute(tree: Path, report: Path, mode: str) -> dict:
    if mode not in ("verify", "apply"):
        raise ValueError("Stage85 mode must be verify or apply")
    files, status = prepare(tree)
    if mode == "apply":
        for path, content in files.items():
            p = tree / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            if p.read_text(encoding="utf-8") != content:
                raise ValueError("Stage85 source write integrity failure: " + path)
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage85 altered RT rejection files")
    status["applied"] = mode == "apply"
    report.mkdir(parents=True, exist_ok=True)
    (report / REPORT).write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    return status


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    p.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = p.parse_args()
    print(json.dumps(
        execute(args.tree.resolve(), args.report.resolve(), args.mode),
        indent=2,
    ))


if __name__ == "__main__":
    main()
