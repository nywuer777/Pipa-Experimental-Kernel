#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 RT stage2 ARM64 lazy preemption field and locking review
"""Resolve one verified ARM64 RT reject; capture locking APIs without changing them."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

REJECT_SHA = "363e0aa915ba38addedbc1d8423a0fb369fe2b4686bb1e89eeb4e71c738c981f"
SOURCE = "arch/arm64/include/asm/thread_info.h"
NEEDLE = "\tint\t\t\tpreempt_count;\t/* 0 => preemptable, <0 => bug */\n"
ADDITION = "\tint\t\t\tpreempt_lazy_count; /* 0 => preemptable, <0 => bug */\n"


def validate(root: Path) -> tuple[Path, Path, str]:
    source = root / SOURCE
    rejected = root / (SOURCE + ".rej")
    kconfig = root / "arch/arm64/Kconfig"
    if not source.is_file() or not rejected.is_file() or not kconfig.is_file():
        raise ValueError("Stage2 required ARM64 source, reject or Kconfig missing")
    actual = hashlib.sha256(rejected.read_bytes()).hexdigest()
    if actual != REJECT_SHA:
        raise ValueError("Unexpected ARM64 rejected hunk sha: " + actual)
    cfg = kconfig.read_text(encoding="utf-8")
    if cfg.count("\tselect HAVE_PREEMPT_LAZY\n") != 1:
        raise ValueError("Missing EXP76 Stage1 HAVE_PREEMPT_LAZY select")
    current = source.read_text(encoding="utf-8")
    if current.count(NEEDLE) != 1 or "preempt_lazy_count;" in current:
        raise ValueError("Missing unique preempt_count or preempt_lazy_count already added")
    if current.count("struct thread_info {") != 1 or current.count("#ifdef CONFIG_SHADOW_CALL_STACK") < 1:
        raise ValueError("Vendor ARM64 thread_info layout unrecognized")
    if "#define TIF_NEED_RESCHED_LAZY" not in current:
        raise ValueError("RT lazy scheduling flag not present from upstream accepted hunks")
    return source, rejected, current


def capture(root: Path, report: Path) -> None:
    """Read-only review excerpt; no automatic rtmutex or spinlock changes."""
    tasks = [
        ("kernel/locking/rtmutex.c", (
            "rt_mutex_slowlock(", "rt_mutex_handle_deadlock(",
            "__rt_mutex_slowlock(", "ww_mutex_account_lock(")),
        ("kernel/locking/spinlock.c", (
            "#ifndef CONFIG_INLINE_READ_TRYLOCK",
            "#ifndef CONFIG_PREEMPT_RT_FULL",
            "#endif /* !CONFIG_PREEMPT_RT_FULL */")),
    ]
    lines = ["EXP76 RT LOCKING API REVIEW (SOURCE ONLY, NO FIX)\n"]
    for relative, tokens in tasks:
        file = root / relative
        if not file.is_file():
            raise ValueError("Missing locking source: " + relative)
        body = file.read_text(encoding="utf-8", errors="replace")
        ls = body.splitlines()
        lines.append("=== " + relative + " ===")
        lines.append("sha256=" + hashlib.sha256(file.read_bytes()).hexdigest())
        for token in tokens:
            matches = [i for i, ln in enumerate(ls) if token in ln]
            lines.append("TOKEN=" + token + " COUNT=" + str(len(matches)))
            for i in matches[:5]:
                begin, end = max(0, i-5), min(len(ls), i+15)
                lines.append("\n".join(f"{j+1}: {ls[j]}" for j in range(begin, end)))
                lines.append("---")
    (report / "locking-source-excerpts.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--mode", choices=("apply", "verify"), required=True)
    a = parser.parse_args()
    root = a.tree.resolve()
    report = a.report.resolve()
    file, rej, before = validate(root)
    report.mkdir(parents=True, exist_ok=True)
    capture(root, report)
    after = before.replace(NEEDLE, NEEDLE + ADDITION, 1)
    if a.mode == "apply":
        file.write_text(after, encoding="utf-8")
        rej.unlink()
    remaining = sorted(str(p.relative_to(root)) for p in root.rglob("*.rej"))
    result = {
        "stage": "EXP76_RT_STAGE2_PARTIAL_ONLY",
        "file": SOURCE,
        "hunk_sha256": REJECT_SHA,
        "applied": a.mode == "apply",
        "remaining_rejected_files": len(remaining),
        "rt_config_enabled": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    (report / "stage2-result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if a.mode == "apply" and len(remaining) != 79:
        raise SystemExit("FAIL_CLOSED: expected 79 remaining rejected files")


if __name__ == "__main__":
    main()
