#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage82 RT reject inventory / NO FLASH
"""Index all outstanding E404/4.19.325-rt140 rejected hunks, without edits.

Collect SHA-256, exact source paths, hunk headers, +/- line counts and bounded
source excerpts. Compare with the immutable initial rejection manifest.
Priorities are triage hints only: no hunk is marked applied or resolved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

STAGE = "EXP76_STAGE82_OUTSTANDING_RT_REJECT_HUNK_INVENTORY_NONFLASH"
REPORT_JSON = "RT_REJECT_HUNK_INVENTORY.json"
REPORT_MD = "RT_REJECT_HUNK_INVENTORY.md"
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")
EXPECTED_REJECT_COUNT = 64
SENTINEL = "kernel/sched/cpupri.c.rej"


def classification(source: str) -> tuple[str, int]:
    if source.startswith(("include/linux/spinlock_types", "include/linux/preempt",
                          "kernel/sched/", "kernel/locking/")):
        return "locking_scheduler", 90
    if source.startswith(("kernel/rcu/", "include/linux/rcu",
                          "include/linux/rcutree")):
        return "rcu", 85
    if source.startswith(("arch/arm64/", "arch/arm/", "arch/x86/")):
        return "architecture", 80
    if source.startswith(("kernel/irq/", "kernel/time/", "kernel/softirq")):
        return "interrupt_timers", 75
    if source.startswith(("mm/", "kernel/", "include/linux/")):
        return "kernel_mm_headers", 70
    if source.startswith(("drivers/", "net/", "fs/", "block/", "crypto/")):
        return "subsystem", 50
    return "other", 35


def parse_reject(content: str) -> tuple[list[dict], list[str]]:
    hunks: list[dict] = []
    issues: list[str] = []
    active: dict | None = None
    for line in content.splitlines():
        if line.startswith("@@ "):
            match = HUNK_RE.fullmatch(line)
            if not match:
                issues.append("Unrecognized hunk header: " + line[:160])
                active = None
                continue
            active = {
                "header": line[:240],
                "old_start": int(match.group(1)),
                "old_count": int(match.group(2) or 1),
                "new_start": int(match.group(3)),
                "new_count": int(match.group(4) or 1),
                "added_lines": 0,
                "removed_lines": 0,
                "context_lines": 0,
                "change_excerpt": [],
            }
            hunks.append(active)
            continue
        if active is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            active["added_lines"] += 1
        elif line.startswith("-") and not line.startswith("---"):
            active["removed_lines"] += 1
        elif line.startswith(" "):
            active["context_lines"] += 1
        else:
            continue
        if line.startswith(("+", "-")) and len(active["change_excerpt"]) < 6:
            active["change_excerpt"].append(line[:180])
    if not hunks:
        issues.append("No parseable unified-diff hunk headers")
    return hunks, issues


def index_rejects(tree: Path, manifest: Path) -> dict:
    if not (tree / ".git").is_dir():
        raise ValueError("Stage82 requires isolated E404 Git trial tree")
    if not (tree / SENTINEL).is_file():
        raise ValueError("Stage82 scheduler reject sentinel missing")
    if not manifest.is_file():
        raise ValueError("Stage82 requires original immutable rejected-path manifest")
    rejected = sorted(p for p in tree.rglob("*.rej") if p.is_file())
    if len(rejected) != EXPECTED_REJECT_COUNT:
        raise ValueError(
            f"Stage82 expected 64 RT reject files, found {len(rejected)}"
        )
    raw_paths = manifest.read_text(encoding="utf-8").splitlines()
    original = [
        line.strip() for line in raw_paths if line.strip()
    ]
    if not original or len(set(original)) != len(original):
        raise ValueError("Stage82 original reject manifest empty or duplicated")
    entries = []
    for path in rejected:
        relative = path.relative_to(tree).as_posix()
        source = relative[:-4]
        category, base_priority = classification(source)
        raw = path.read_bytes()
        content = raw.decode("utf-8", errors="replace")
        hunks, issues = parse_reject(content)
        entries.append({
            "reject": relative,
            "source": source,
            "source_exists": (tree / source).is_file(),
            "reject_bytes": len(raw),
            "reject_sha256": hashlib.sha256(raw).hexdigest(),
            "review_category": category,
            "review_score": min(100, base_priority + min(10, len(hunks))),
            "hunk_count": len(hunks),
            "added_lines": sum(h["added_lines"] for h in hunks),
            "removed_lines": sum(h["removed_lines"] for h in hunks),
            "parse_issues": issues,
            "hunks": hunks,
            "semantic_status": "unresolved_manual_review_required",
        })
    priorities = sorted(
        entries, key=lambda x: (
            -x["review_score"], -x["hunk_count"], x["source"]
        )
    )
    remaining = {item["source"] for item in entries}
    original_set = set(original)
    categories = Counter(e["review_category"] for e in entries)
    result = {
        "stage": STAGE,
        "source": "pinned_e404_trial_overlay_after_stage48",
        "original_manifest": "exp76-rt-report/overlay/rejected-paths.txt",
        "initial_rejected_path_count": len(original),
        "remaining_rejected_files": len(entries),
        "remaining_in_initial_manifest": len(remaining & original_set),
        "remaining_not_in_initial_manifest": sorted(remaining - original_set),
        "initial_paths_no_longer_rejected": sorted(original_set - remaining),
        "total_rejected_hunks": sum(e["hunk_count"] for e in entries),
        "total_added_lines": sum(e["added_lines"] for e in entries),
        "total_removed_lines": sum(e["removed_lines"] for e in entries),
        "unparseable_reject_files": [
            e["reject"] for e in entries if e["parse_issues"]
        ],
        "missing_source_files": [
            e["source"] for e in entries if not e["source_exists"]
        ],
        "categories": dict(sorted(categories.items())),
        "priority_order": [e["source"] for e in priorities],
        "entries": entries,
        "resolution_verified": False,
        "automatic_patch_apply_performed": False,
        "source_modified": False,
        "rejects_deleted": False,
        "full_kernel_link_performed": False,
        "runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    return result


def format_report(data: dict) -> str:
    lines = [
        "# EXP76 Stage82 — unresolved PREEMPT_RT rejects",
        "",
        f"- Reject files remaining: **{data['remaining_rejected_files']}**",
        f"- Rejected diff hunks: **{data['total_rejected_hunks']}**",
        f"- Rejected +/- lines: **{data['total_added_lines']} / {data['total_removed_lines']}**",
        f"- Rejected files with parse warnings: **{len(data['unparseable_reject_files'])}**",
        f"- Prior manifest paths no longer rejected: **{len(data['initial_paths_no_longer_rejected'])}**",
        "",
        "No reject has been cleared or resolved by this inventory.",
        "Review scores are heuristics, not semantic correctness claims.",
        "",
        "## Areas",
        "",
        "| Review area | Files |",
        "|---|---:|",
    ]
    lines += [
        f"| {category} | {count} |"
        for category, count in data["categories"].items()
    ]
    lookup = {entry["source"]: entry for entry in data["entries"]}
    lines += [
        "", "## All unresolved paths by triage priority", "",
        "| Priority | Source | Hunks | SHA-256 (.rej) |",
        "|---:|---|---:|---|",
    ]
    for path in data["priority_order"]:
        e = lookup[path]
        lines.append(
            f"| {e['review_score']} | \`{path}\` | {e['hunk_count']} | "
            f"\`{e['reject_sha256']}\` |"
        )
    lines += [
        "", "## Next engineering action", "",
        "Inspect the specific hunks and source context for one high-priority",
        "path at a time. Apply semantic RT compatibility changes only after",
        "source/version matching and object-level checks. Do not delete",
        "a .rej file merely because an object compiles.",
        "",
        "KERNEL_BUILT=false; FLASH_READY=false",
        "",
    ]
    return "\n".join(lines)


def execute(tree: Path, manifest: Path, report: Path) -> dict:
    result = index_rejects(tree, manifest)
    report.mkdir(parents=True, exist_ok=True)
    (report / REPORT_JSON).write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    (report / REPORT_MD).write_text(
        format_report(result), encoding="utf-8"
    )
    if len(list(tree.rglob("*.rej"))) != EXPECTED_REJECT_COUNT:
        raise ValueError("Stage82 changed reject count during reporting")
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    a = p.parse_args()
    result = execute(
        a.tree.resolve(), a.manifest.resolve(), a.report.resolve()
    )
    print(json.dumps({
        "stage": result["stage"],
        "remaining_rejected_files": result["remaining_rejected_files"],
        "total_rejected_hunks": result["total_rejected_hunks"],
        "categories": result["categories"],
        "review_first": result["priority_order"][:8],
        "unparseable_reject_files": result["unparseable_reject_files"][:8],
        "kernel_built": False, "flash_ready": False,
    }, indent=2))


if __name__ == "__main__":
    main()
