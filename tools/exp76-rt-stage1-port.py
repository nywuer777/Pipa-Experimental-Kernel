#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 RT stage1 exact-hunk port, partial source only
"""Apply two verified upstream RT hunks after git apply --reject.

This is NOT a complete PREEMPT_RT integration or bootable output.
"""
import argparse
import hashlib
import json
from pathlib import Path

PORTS = (
    {
        "path": "arch/arm64/Kconfig",
        "reject_sha256": "8e081848586c4a7ebdb72533cfb2f9f40fd720aa50d1a2ea29cb0f20acb51601",
        "before": "\tselect HAVE_PERF_USER_STACK_DUMP\n",
        "after": "\tselect HAVE_PERF_USER_STACK_DUMP\n\tselect HAVE_PREEMPT_LAZY\n",
        "expected_before_absent": "select HAVE_PREEMPT_LAZY",
        "post_required": "select HAVE_PREEMPT_LAZY",
    },
    {
        "path": "kernel/sched/Makefile",
        "reject_sha256": "01f2bb2ab434204e1f31a3280ee4c9ee754a21167a78ccb9cd2f77edcb25be52",
        "before": "obj-y += wait.o wait_bit.o swait.o completion.o\n",
        "after": "obj-y += wait.o wait_bit.o swait.o swork.o completion.o\n",
        "expected_before_absent": "swait.o swork.o completion.o",
        "post_required": "swait.o swork.o completion.o",
    },
)


def patch_one(root: Path, spec: dict, apply: bool):
    rel = spec["path"]
    source = root / rel
    rejected = root / (rel + ".rej")
    if not source.is_file() or not rejected.is_file():
        raise ValueError("Missing source/rejected hunk: " + rel)
    sha = hashlib.sha256(rejected.read_bytes()).hexdigest()
    if sha != spec["reject_sha256"]:
        raise ValueError("Unexpected RT hunk revision at " + rel + ": " + sha)
    old = source.read_text(encoding="utf-8")
    if old.count(spec["before"]) != 1:
        raise ValueError("Source location ambiguous/absent: " + rel)
    if spec["expected_before_absent"] in old:
        raise ValueError("RT addition already present: " + rel)
    if rel == "kernel/sched/Makefile":
        for dep in ("kernel/sched/swork.c", "include/linux/swork.h"):
            if not (root / dep).is_file():
                raise ValueError("Missing RT swork prerequisite: " + dep)
    new = old.replace(spec["before"], spec["after"], 1)
    if new.count(spec["post_required"]) != 1:
        raise ValueError("Port not unique: " + rel)
    if apply:
        source.write_text(new, encoding="utf-8")
        rejected.unlink()
    return {"file": rel, "sha256_rejected_hunk": sha,
            "source_changed": new != old, "reject_cleared": apply}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tree", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    p.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = p.parse_args()
    tree = args.tree.resolve()
    apply = args.mode == "apply"
    # Verify every target, including prerequisite files, before modifying either.
    checked = [patch_one(tree, spec, False) for spec in PORTS]
    if apply:
        checked = [patch_one(tree, spec, True) for spec in PORTS]
    remaining = sorted(str(x.relative_to(tree)) for x in tree.rglob("*.rej"))
    result = {"stage": "EXP76_RT_STAGE1_PARTIAL_ONLY", "ported_files": len(checked),
              "ports": checked, "remaining_rejected_files": len(remaining),
              "configuration_rt_enabled": False, "kernel_built": False,
              "flash_ready": False}
    args.report.mkdir(parents=True, exist_ok=True)
    (args.report / "stage1-status.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    (args.report / "stage1-remaining.txt").write_text(
        "\n".join(remaining) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    if apply and len(remaining) == 0:
        raise SystemExit("Unexpected zero rejects; independent semantic review required")


if __name__ == "__main__":
    main()
