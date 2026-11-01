#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 RT stage4 spinlock.c guard reconciliation
"""Add the missing RT guard to legacy rwlock functions, exact rejected hunk only.

Requires an already-applied matching closing #endif from upstream RT patch.
Does not touch spinlock_types.h and is NOT a complete RT port.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

TARGET = "kernel/locking/spinlock.c"
REJECT_SHA = "024a58992bd98d88b635d2692e3be4f32daa7529e75e48faeeb47681feed03c1"
PREFIX = "#ifndef CONFIG_PREEMPT_RT_FULL\n\n"
START = "#ifndef CONFIG_INLINE_READ_TRYLOCK\n"
STOP = "#ifdef CONFIG_DEBUG_LOCK_ALLOC\n"
PRECEDING = "EXPORT_SYMBOL(_raw_spin_unlock_bh);\n#endif\n\n"
LAST = "EXPORT_SYMBOL(_raw_write_unlock_bh);\n#endif\n"
DEPENDENCIES = (
    "include/linux/spinlock_types_raw.h",
    "include/linux/spinlock_types_nort.h",
    "include/linux/spinlock_types_rt.h",
    "include/linux/rwlock_types_rt.h",
)


def directive_depth(lines: str):
    depth = 0
    smallest = 0
    for line in lines.splitlines():
        stripped = line.strip()
        if re.match(r"^#\s*(if|ifdef|ifndef)\b", stripped):
            depth += 1
        elif re.match(r"^#\s*endif\b", stripped):
            depth -= 1
        smallest = min(smallest, depth)
    return depth, smallest


def plan(tree: Path):
    source = tree / TARGET
    reject = tree / (TARGET + ".rej")
    if not source.is_file() or not reject.is_file():
        raise ValueError("Missing spinlock source or matching rejected hunk")
    actual = hashlib.sha256(reject.read_bytes()).hexdigest()
    if actual != REJECT_SHA:
        raise ValueError("Unexpected rejected hunk SHA256: " + actual)
    for dep in DEPENDENCIES:
        if not (tree / dep).is_file():
            raise ValueError("Missing upstream RT prerequisite: " + dep)
    body = source.read_text(encoding="utf-8")
    if body.count(START) != 1 or body.count(STOP) != 1:
        raise ValueError("Unexpected rwlock guard layout in spinlock.c")
    start = body.index(START)
    end = body.index(STOP, start)
    before = body[:start]
    if not before.endswith(PRECEDING):
        raise ValueError("Legacy read-lock region does not follow raw spin unlock")
    region = body[start:end]
    if region.count(LAST) != 1 or region.count("#ifndef CONFIG_PREEMPT_RT_FULL") != 0:
        raise ValueError("Unexpected rwlock region boundaries")
    if not re.search(r"(?m)^#endif(?:\s*/\*.*\*/)?\s*$", region.rstrip().splitlines()[-1]):
        raise ValueError("Upstream closing endif missing after legacy rwlock helpers")
    depth, minimum = directive_depth(region)
    if depth != -1 or minimum != -1:
        raise ValueError("Expected one orphan upstream closing endif; got depth="
                         + str(depth) + " min=" + str(minimum))
    final = body[:start] + PREFIX + body[start:]
    corrected = final[final.index(PREFIX, start):final.index(STOP, start)]
    d, m = directive_depth(corrected)
    if d != 0 or m < 0:
        raise ValueError("RT conditional guard remains unbalanced")
    if final.count(PREFIX) != 1:
        raise ValueError("RT guard not unique")
    return source, reject, final, actual


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = parser.parse_args()
    tree = args.tree.resolve()
    path, rej, output, sha = plan(tree)
    if args.mode == "apply":
        path.write_text(output, encoding="utf-8")
        rej.unlink()
    remaining = len(list(tree.rglob("*.rej")))
    result = {
        "stage": "EXP76_RT_STAGE4_SOURCE_ONLY",
        "file": TARGET, "rejected_hunk_sha256": sha,
        "ported": args.mode == "apply",
        "rwlock_non_rt_guard_balanced": True,
        "spinlock_types_header_ported": False,
        "remaining_rejected_files": remaining,
        "kernel_built": False,
        "config_preempt_rt_enabled": False,
        "flash_ready": False,
    }
    args.report.mkdir(parents=True, exist_ok=True)
    (args.report / "stage4-result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    if args.mode == "apply" and remaining != 77:
        raise SystemExit("FAIL_CLOSED: expected 77 remaining RT reject files")


if __name__ == "__main__":
    main()
