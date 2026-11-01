#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 RT Stage6 irq_work equivalence and swork include
"""Resolve three exact rejected hunks: two already implemented in vendor E404.

IRQ_WORK_HARD_IRQ bit and atomic_t initializer are already present in E404.
Only cgroup-defs.h gets a source change. Source audit only; no RT kernel build.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

REJECT_HASHES = {
    "include/linux/irq_work.h":
        "315c5687251339a17e62dc34d71294f079aff12ed953761f3d3a0bdd3166b096",
    "kernel/time/tick-sched.c":
        "a2332925e75de0447b06f3aa9caad397c99a47936ddbf134326e9d00b7f939cc",
    "include/linux/cgroup-defs.h":
        "5d66f0195fc3344cb7d64b1127e6e2eeab1a1b37079b0fadd5081f9500bb3c7e",
}
CGROUP = "include/linux/cgroup-defs.h"
OLD_INCLUDES = (
    "#include <linux/workqueue.h>\n"
    "#include <linux/bpf-cgroup.h>\n"
)
NEW_INCLUDES = (
    "#include <linux/workqueue.h>\n"
    "#include <linux/bpf-cgroup.h>\n"
    "#include <linux/swork.h>\n"
)


def verify(tree: Path):
    paths = {}
    for relative, digest in REJECT_HASHES.items():
        p = tree / relative
        reject = tree / (relative + ".rej")
        if not p.is_file() or not reject.is_file():
            raise ValueError("Required source/reject missing: " + relative)
        actual = hashlib.sha256(reject.read_bytes()).hexdigest()
        if actual != digest:
            raise ValueError("Reject SHA mismatch: " + relative + ": " + actual)
        paths[relative] = p.read_text(encoding="utf-8")

    irq = paths["include/linux/irq_work.h"]
    if irq.count("#define IRQ_WORK_HARD_IRQ\tBIT(3)") != 1:
        raise ValueError("E404 IRQ_WORK_HARD_IRQ bit not present exactly once")
    if irq.count("#define IRQ_WORK_LAZY\t\tBIT(2)") != 1:
        raise ValueError("Existing lazy flag has unexpected encoding")
    if not re.search(r"struct irq_work\s*\{\s*struct llist_node llnode;\s*"
                     r"atomic_t flags;", irq):
        raise ValueError("IRQ work flags are no longer atomic_t")

    tick = paths["kernel/time/tick-sched.c"]
    declaration = (
        "static DEFINE_PER_CPU(struct irq_work, nohz_full_kick_work) = {\n"
        "\t.func = nohz_full_kick_func,\n"
        "\t.flags = ATOMIC_INIT(IRQ_WORK_HARD_IRQ),\n"
        "};"
    )
    if tick.count(declaration) != 1:
        raise ValueError("Vendor atomic initializer not equivalent to upstream")
    if "IRQ_WORK_HARD_IRQ" not in irq:
        raise ValueError("IRQ flag dependency absent")

    cgroup = paths[CGROUP]
    if cgroup.count(OLD_INCLUDES) != 1:
        raise ValueError("Cgroup include location absent/ambiguous")
    if "#include <linux/swork.h>" in cgroup:
        raise ValueError("Cgroup header already includes swork")
    swork = tree / "include/linux/swork.h"
    if not swork.is_file() or "struct swork_event" not in swork.read_text():
        raise ValueError("Upstream RT swork.h prerequisite unavailable")
    if not (tree / "kernel/sched/swork.c").is_file():
        raise ValueError("Upstream RT swork implementation missing")
    return paths


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--mode", choices=("check", "apply"), required=True)
    args = parser.parse_args()
    tree = args.tree.resolve()
    original = verify(tree)
    proposed = original[CGROUP].replace(OLD_INCLUDES, NEW_INCLUDES, 1)
    if proposed.count("#include <linux/swork.h>") != 1:
        raise ValueError("swork header was not inserted exactly once")
    if args.mode == "apply":
        # Check all three requirements BEFORE touching the tree.
        (tree / CGROUP).write_text(proposed, encoding="utf-8")
        for relative in REJECT_HASHES:
            (tree / (relative + ".rej")).unlink()

    remaining = len(list(tree.rglob("*.rej")))
    result = {
        "stage": "EXP76_RT_STAGE6_PARTIAL_SOURCE_ONLY",
        "verified_vendor_equivalents": [
            "include/linux/irq_work.h: IRQ_WORK_HARD_IRQ=BIT(3)",
            "kernel/time/tick-sched.c: atomic_t ATOMIC_INIT(IRQ_WORK_HARD_IRQ)",
        ],
        "source_modified_only": [CGROUP] if args.mode == "apply" else [],
        "resolved_rejected_files": 3 if args.mode == "apply" else 0,
        "remaining_rejected_files": remaining,
        "rt_enabled": False,
        "kernel_compiled": False,
        "flash_ready": False,
    }
    args.report.mkdir(parents=True, exist_ok=True)
    (args.report / "stage6-status.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if args.mode == "apply" and remaining != 73:
        raise SystemExit("FAIL_CLOSED: expected exactly 73 remaining rejected files")


if __name__ == "__main__":
    main()
