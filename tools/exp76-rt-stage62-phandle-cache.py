#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage62 E404 OF phandle-cache lifetime / NO FLASH
"""Complete the partial RT of_populate_phandle_cache() free-path contract.

The RT patch moves kfree(shadow) outside devtree_lock but the E404 helper
__of_free_phandle_cache() still returns void and frees under the raw lock.
Return the retired cache pointer and defer only its kfree; keep the node
reference puts and devtree_lock-protected detach exactly as before.
This script edits a pinned isolated trial tree, never EXP75 or boot output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

FILE = "drivers/of/base.c"
PENDING = "kernel/sched/cpupri.c.rej"

OLD_FREE = (
    "static void __of_free_phandle_cache(void)\n"
    "{\n"
    "\tu32 cache_entries = phandle_cache_mask + 1;\n"
    "\tu32 k;\n\n"
    "\tif (!phandle_cache)\n"
    "\t\treturn;\n\n"
    "\tfor (k = 0; k < cache_entries; k++)\n"
    "\t\tof_node_put(phandle_cache[k]);\n\n"
    "\tkfree(phandle_cache);\n"
    "\tphandle_cache = NULL;\n"
    "}\n"
)
NEW_FREE = (
    "static struct device_node **__of_free_phandle_cache(void)\n"
    "{\n"
    "\tstruct device_node **shadow = phandle_cache;\n"
    "\tu32 cache_entries = phandle_cache_mask + 1;\n"
    "\tu32 k;\n\n"
    "\tif (!shadow)\n"
    "\t\treturn NULL;\n\n"
    "\tfor (k = 0; k < cache_entries; k++)\n"
    "\t\tof_node_put(shadow[k]);\n\n"
    "\tphandle_cache = NULL;\n"
    "\treturn shadow;\n"
    "}\n"
)
RT_CALL = (
    "\traw_spin_lock_irqsave(&devtree_lock, flags);\n\n"
    "\tshadow = __of_free_phandle_cache();\n"
)
RT_UNLOCK_FREE = (
    "out:\n"
    "\traw_spin_unlock_irqrestore(&devtree_lock, flags);\n"
    "\tkfree(shadow);\n"
)
RT_ALLOC_UNLOCK = (
    "\tif (!phandles)\n"
    "\t\tgoto out;\n"
    "\traw_spin_unlock_irqrestore(&devtree_lock, flags);\n\n"
    "\tcache_entries = roundup_pow_of_two(phandles);\n"
)
RT_ALLOC_RELOCK = (
    "\tphandle_cache = kcalloc(cache_entries, sizeof(*phandle_cache),\n"
    "\t\t\t\tGFP_ATOMIC);\n"
    "\traw_spin_lock_irqsave(&devtree_lock, flags);\n"
)


def one(source: str, fragment: str, name: str) -> None:
    occurrences = source.count(fragment)
    if occurrences != 1:
        raise ValueError(f"{name}: expected exactly 1 pinned fragment, saw {occurrences}")


def prepare(tree: Path) -> tuple[dict[str, str], dict]:
    if not (tree / ".git").is_dir():
        raise ValueError("Stage62 requires isolated E404 trial git checkout")
    if not (tree / FILE).is_file() or not (tree / PENDING).is_file():
        raise ValueError("Required E404 source and pinned RT reject missing")
    rejects = len(list(tree.rglob("*.rej")))
    if rejects != 64:
        raise ValueError(f"Expected 64 outstanding RT reject files, found {rejects}")
    original = (tree / FILE).read_text(encoding="utf-8")
    one(original, OLD_FREE, "E404 unmodified cache release helper")
    one(original, RT_CALL, "Partially applied RT shadow-cache call")
    one(original, RT_UNLOCK_FREE, "RT deferred shadow kfree")
    one(original, RT_ALLOC_UNLOCK, "RT unlocked allocation entry")
    one(original, RT_ALLOC_RELOCK, "RT allocation re-lock")
    one(original, "\tstruct device_node **shadow;\n",
        "RT caller cache pointer declaration")
    one(original, "\tfor_each_of_allnodes(np)\n",
        "E404 first device-tree enumeration") if original.count(
            "\tfor_each_of_allnodes(np)\n"
        ) == 1 else require_two_enumerations(original)
    if "static struct device_node **__of_free_phandle_cache(void)" in original:
        raise ValueError("Stage62 already applied")
    updated = original.replace(OLD_FREE, NEW_FREE, 1)
    one(updated, NEW_FREE, "Correct detached cache lifetime")
    one(updated, RT_UNLOCK_FREE, "Free only outside raw spinlock")
    if OLD_FREE in updated or "\tkfree(phandle_cache);\n" in updated:
        raise ValueError("Old cache free under raw spinlock survived")
    if updated.count("__of_free_phandle_cache();") != 1:
        raise ValueError("Unexpected OF cache helper call sites")
    return {FILE: updated}, {
        "stage": "EXP76_STAGE62_OF_PHANDLE_CACHE_DEFERRED_KFREE_NONFLASH",
        "rt_shadow_assignment_type_reconciled": True,
        "phandle_cache_detach_under_raw_lock": True,
        "cache_node_references_released_as_before": True,
        "retired_cache_kfree_after_unlock": True,
        "rt_allocation_unlock_relock_preserved": True,
        "outstanding_rt_rejects": 64,
        "full_kernel_link_performed": False,
        "runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
        "original_sha256": hashlib.sha256(original.encode()).hexdigest(),
        "patched_sha256": hashlib.sha256(updated.encode()).hexdigest(),
    }


def require_two_enumerations(text: str) -> None:
    if text.count("\tfor_each_of_allnodes(np)\n") != 2:
        raise ValueError("Expected both OF phandle node enumerations")


def execute(tree: Path, report: Path, mode: str) -> dict:
    if mode not in ("verify", "apply"):
        raise ValueError("Stage62 accepts verify/apply only")
    changes, result = prepare(tree)
    if mode == "apply":
        for path, content in changes.items():
            (tree / path).write_text(content, encoding="utf-8")
        for path, content in changes.items():
            if (tree / path).read_text(encoding="utf-8") != content:
                raise ValueError("Stage62 post-write source integrity mismatch")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage62 changed unresolved RT rejection evidence")
    result["applied"] = mode == "apply"
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage62-status.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = p.parse_args()
    print(json.dumps(execute(args.tree.resolve(), args.report.resolve(), args.mode), indent=2))


if __name__ == "__main__":
    main()
