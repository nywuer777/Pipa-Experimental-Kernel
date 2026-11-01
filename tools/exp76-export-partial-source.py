#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / export reproducible EXP76 partial RT source delta / NO FLASH
"""Export full tracked+new source diff, exclude reject files, validate on pinned E404.

This patch is incomplete RT source work, not a buildable image or flash candidate.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

BASE = "fed88a6024cd4d46c52eda607a95d97d7371ba81"
NAME = "EXP76-RT-PARTIAL-SOURCE-NONFLASH.patch"


def git(repo: Path, *args: str, check=True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--trial", type=Path, required=True)
    p.add_argument("--clean-base", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    a = p.parse_args()
    trial = a.trial.resolve()
    clean = a.clean_base.resolve()
    report = a.report.resolve()
    report.mkdir(parents=True, exist_ok=True)
    if trial == clean or not (trial / ".git").exists() or not (clean / ".git").exists():
        raise ValueError("Trial and clean E404 must be distinct real Git worktrees")
    if git(trial, "rev-parse", "HEAD").stdout.decode().strip() != BASE:
        raise ValueError("Trial kernel baseline drift")
    if git(clean, "rev-parse", "HEAD").stdout.decode().strip() != BASE:
        raise ValueError("Clean kernel baseline drift")
    if git(clean, "status", "--porcelain").stdout.strip():
        raise ValueError("Reference E404 worktree is not clean")

    untracked = git(trial, "ls-files", "--others", "--exclude-standard", "-z").stdout
    files = [f.decode("utf-8") for f in untracked.split(b"\0") if f]
    reject_files = sorted(f for f in files if f.endswith(".rej"))
    excluded = sorted(f for f in files if f.endswith((".rej", ".orig", ".swp", ".tmp")))
    new_sources = sorted(f for f in files if f not in excluded)
    if len(reject_files) != 65:
        raise ValueError(f"Expected 65 unresolved reject files, got {len(reject_files)}")
    # Intent-to-add makes newly created RT source files visible to git diff
    # without committing. .rej and scratch files stay excluded.
    for i in range(0, len(new_sources), 80):
        git(trial, "add", "--intent-to-add", "--", *new_sources[i:i+80])
    diff_check = git(trial, "diff", "--check", "HEAD")
    if diff_check.stdout.strip():
        raise ValueError("git diff --check emitted warnings")
    patch = git(trial, "diff", "--binary", "--full-index", "--no-ext-diff", "HEAD", "--").stdout
    if not patch or b"diff --git " not in patch:
        raise ValueError("No tracked or new source changes in RT trial checkout")
    if b".rej" in b"\n".join(line for line in patch.splitlines()
                           if line.startswith(b"diff --git ")):
        raise ValueError("Reject artifacts accidentally included in source patch")
    output = report / NAME
    output.write_bytes(patch)

    check = git(clean, "apply", "--check", str(output), check=False)
    (report / "reapply-check.log").write_bytes(check.stderr + check.stdout)
    if check.returncode != 0:
        raise ValueError("Cumulative patch did not reapply to clean pinned E404")
    stats = git(trial, "diff", "--stat", "HEAD", "--").stdout
    (report / "source-diff-stat.txt").write_bytes(stats)
    sum_hash = hashlib.sha256(patch).hexdigest()
    (report / (NAME + ".sha256")).write_text(sum_hash + "  " + NAME + "\n")
    status = {
        "stage": "EXP76_PARTIAL_SOURCE_EXPORT",
        "e404_pinned_sha": BASE,
        "nonflash_only": True,
        "unresolved_rejected_files": len(reject_files),
        "additional_new_source_files": len(new_sources),
        "cumulative_patch_sha256": sum_hash,
        "reapply_to_clean_e404": "PASS",
        "kernel_compiled": False,
        "preempt_rt_config_enabled": False,
        "flash_ready": False,
    }
    (report / "PARTIAL_SOURCE_MANIFEST.json").write_text(
        json.dumps(status, indent=2) + "\n"
    )
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
