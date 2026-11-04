#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage16 scheduler affinity ABI audit / NO FLASH
"""Find RT-140 cpus_ptr and cpus_mask drift against E404 task_struct.

Read-only. The old RT cpus_ptr change to cpupri.c is NOT an independent fix:
partial RT source already references fields missing from E404 task_struct.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

REJ = "kernel/sched/cpupri.c.rej"
REJ_SHA256 = "46229fc23a4543f28fac12bad645f582a160086cc6d5cb6056b7909c01e53052"
CRITICAL_FILES = ("kernel/sched/core.c", "kernel/fork.c")


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], text=True, encoding="utf-8",
        errors="replace", capture_output=True, check=True,
    ).stdout


def added_member_references(root: Path) -> dict[str, list[dict]]:
    diff = git(root, "diff", "--no-ext-diff", "--no-color", "-U0", "HEAD", "--")
    current = ""
    hits: dict[str, list[dict]] = {}
    for line in diff.splitlines():
        if line.startswith("diff --git a/"):
            match = re.match(r"diff --git a/(.*?) b/(.*?)$", line)
            if not match or match.group(1) != match.group(2):
                raise ValueError("Unexpected rename in RT source diff")
            current = match.group(2)
            continue
        if not current or not line.startswith("+") or line.startswith("+++"):
            continue
        body = line[1:]
        tokens = [x for x in ("->cpus_ptr", "->cpus_mask") if x in body]
        if tokens:
            hits.setdefault(current, []).append({
                "tokens": tokens, "line": body.strip(),
            })
    return hits


def verify(root: Path) -> dict:
    if not (root / ".git").exists():
        raise ValueError("Expected E404 source Git worktree")
    cpupri = root / "kernel/sched/cpupri.c"
    rej = root / REJ
    sched = root / "include/linux/sched.h"
    if not all(x.is_file() for x in (cpupri, rej, sched)):
        raise ValueError("Missing scheduler source, task header or RT reject")
    digest = hashlib.sha256(rej.read_bytes()).hexdigest()
    if digest != REJ_SHA256:
        raise ValueError("cpupri RT reject hash changed: " + digest)
    patch = rej.read_text(encoding="utf-8")
    if len(re.findall(r"(?m)^@@ -\d+", patch)) != 1:
        raise ValueError("Expected one cpupri RT reject hunk")
    required = (
        ("-", "cpumask_any_and(&p->cpus_allowed, vec->mask)"),
        ("+", "cpumask_any_and(p->cpus_ptr, vec->mask)"),
        ("-", "cpumask_and(lowest_mask, &p->cpus_allowed, vec->mask)"),
        ("+", "cpumask_and(lowest_mask, p->cpus_ptr, vec->mask)"),
    )
    for sign, fragment in required:
        if sum(line.startswith(sign) and fragment in line
               for line in patch.splitlines()) != 1:
            raise ValueError("Unexpected cpupri hunk content: " + fragment)
    original = cpupri.read_text(encoding="utf-8")
    if original.count("&p->cpus_allowed") != 2 or "p->cpus_ptr" in original:
        raise ValueError("E404 cpupri task affinity ABI changed")

    header = sched.read_text(encoding="utf-8")
    if "struct task_struct {" not in header:
        raise ValueError("task_struct definition missing")
    if not re.search(r"(?m)^\s*cpumask_t\s+cpus_allowed\s*;", header):
        raise ValueError("E404 task_struct cpus_allowed missing")
    missing = [
        name for name in ("cpus_ptr", "cpus_mask")
        if not re.search(r"\b" + name + r"\s*;", header)
    ]
    if len(missing) != 2:
        raise ValueError("Task affinity ABI changed; re-audit instead of skipping")
    affected = added_member_references(root)
    if not all(name in affected for name in CRITICAL_FILES):
        raise ValueError("Expected core and fork RT affinity references absent")
    if not any("->cpus_ptr" in h["tokens"]
               for h in affected["kernel/sched/core.c"]):
        raise ValueError("RT core missing expected cpus_ptr reference")
    if not any("->cpus_mask" in h["tokens"]
               for h in affected["kernel/sched/core.c"]):
        raise ValueError("RT core missing expected cpus_mask reference")
    if len(affected) < 6:
        raise ValueError("Suspiciously small affinity ABI impact")
    rejected_count = len(list(root.rglob("*.rej")))
    if rejected_count != 66:
        raise ValueError("Expected Stage15 tree with 66 rejects, got "
                         + str(rejected_count))
    counts = Counter(token for rows in affected.values() for row in rows
                     for token in row["tokens"])
    return {
        "stage": "EXP76_RT_STAGE16_SCHED_AFFINITY_AUDIT",
        "e404_task_struct_field": "cpus_allowed",
        "missing_rt_task_fields": missing,
        "cpupri_reject_sha256": digest,
        "cpupri_reject_preserved": True,
        "affected_files_count": len(affected),
        "added_affinity_references": dict(counts),
        "affected_files": affected,
        "classification": "COMPILE_BLOCKER_UNTIL_AFFINITY_ABI_RECONCILED",
        "blind_rename_permitted": False,
        "remaining_rejected_files": rejected_count,
        "kernel_compiled": False,
        "rt_enabled": False,
        "flash_ready": False,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    data = verify(args.tree.resolve())
    report = args.report.resolve()
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage16-affinity-abi.json").write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# EXP76 Stage16: scheduler affinity ABI mismatch",
        "",
        "This is a blocking diagnostic, not a kernel build or a port.",
        "E404 task_struct stores cpus_allowed; it does not declare cpus_ptr",
        "or cpus_mask, while partial RT source uses both.",
        "The cpupri.c reject is deliberately retained.",
        "",
        "| Affected source path | Newly added member references |",
        "| --- | ---: |",
    ]
    for path, rows in sorted(data["affected_files"].items()):
        lines.append("| " + path + " | " + str(len(rows)) + " |")
    lines.extend([
        "",
        "Reconcile task initialization, fork, set_cpus_allowed, cpusets,",
        "scheduler classes, tracing and dependent consumers as a unit.",
        "Do not blindly replace cpus_ptr or claim a successful RT build.",
        "FLASH_READY=false",
        "",
    ])
    (report / "AFFINITY_ABI_BLOCKER.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    print(json.dumps({
        "classification": data["classification"],
        "affected_files_count": data["affected_files_count"],
        "added_affinity_references": data["added_affinity_references"],
        "remaining_rejected_files": data["remaining_rejected_files"],
    }, indent=2))
    print("EXP76_RT_STAGE16=AFFINITY_ABI_BLOCKER_IDENTIFIED; KERNEL_BUILT=false; FLASH_READY=false")


if __name__ == "__main__":
    main()
