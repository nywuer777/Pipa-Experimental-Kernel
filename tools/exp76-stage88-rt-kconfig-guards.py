#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage88 RT Kconfig dependency port / NO FLASH
"""Port three SHA-pinned RT Kconfig guards, then verify effective .config.

The RT upstream hunk disables transparent huge pages and owner spinning.
The E404 vendor RWSEM owner option uses different non-RT prerequisites than
the rejected patch; preserve E404 prerequisites and add only the RT guard.
All .rej files are kept for provenance, EXP75 is never modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

STAGE = "EXP76_STAGE88_RT_THP_MUTEX_RWSEM_KCONFIG_GUARDS_NONFLASH"
REPORT = "stage88-status.json"
INDEX_STAGE = "EXP76_STAGE82_OUTSTANDING_RT_REJECT_HUNK_INVENTORY_NONFLASH"
FILES = {
    "mm/Kconfig": {
        "sha": "25ee0e0f0549bbc990c7431db0d485f2bfa16400402bc701ae0ab8d730891574",
        "hunks": 1,
        "minus": ("\tdepends on HAVE_ARCH_TRANSPARENT_HUGEPAGE",),
        "plus": ("\tdepends on HAVE_ARCH_TRANSPARENT_HUGEPAGE && !PREEMPT_RT_FULL",),
        "dependencies": {
            "TRANSPARENT_HUGEPAGE": "\tdepends on HAVE_ARCH_TRANSPARENT_HUGEPAGE",
        },
    },
    "kernel/Kconfig.locks": {
        "sha": "da9909189354763b4db4ac0d0f1253ed343ec36173e173d12f7264b383d0765f",
        "hunks": 1,
        "minus": (
            "\tdepends on SMP && ARCH_SUPPORTS_ATOMIC_RMW",
            "       depends on SMP && RWSEM_XCHGADD_ALGORITHM && ARCH_SUPPORTS_ATOMIC_RMW",
        ),
        "plus": (
            "\tdepends on SMP && ARCH_SUPPORTS_ATOMIC_RMW && !PREEMPT_RT_FULL",
            "       depends on SMP && RWSEM_XCHGADD_ALGORITHM && ARCH_SUPPORTS_ATOMIC_RMW && !PREEMPT_RT_FULL",
        ),
        "dependencies": {
            "MUTEX_SPIN_ON_OWNER": "\tdepends on SMP && ARCH_SUPPORTS_ATOMIC_RMW",
            "RWSEM_SPIN_ON_OWNER": "       depends on SMP && ARCH_SUPPORTS_ATOMIC_RMW",
        },
    },
}
CONFIGS = ("TRANSPARENT_HUGEPAGE", "MUTEX_SPIN_ON_OWNER", "RWSEM_SPIN_ON_OWNER")
AUDIT_SENTINEL = "kernel/sched/cpupri.c.rej"


def sha_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hunk_changes(rejected: str) -> tuple[int, list[str], list[str]]:
    hunk_count = 0
    minus: list[str] = []
    plus: list[str] = []
    inside = False
    for line in rejected.splitlines():
        if line.startswith("@@ "):
            hunk_count += 1
            if not re.match(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@", line):
                raise ValueError("Stage88 RT patch hunk parse failure")
            inside = True
        elif line.startswith("diff --git "):
            inside = False
        elif inside:
            if line.startswith("-") and not line.startswith("---"):
                minus.append(line[1:])
            elif line.startswith("+") and not line.startswith("+++"):
                plus.append(line[1:])
    return hunk_count, minus, plus


def patch_config(source: str, name: str, depends: str) -> str:
    header = "config " + name + "\n"
    if source.count(header) != 1:
        raise ValueError("Stage88 config declaration mismatch: " + name)
    start = source.index(header)
    after = re.search(r"(?m)^(?:menuconfig|config|choice|endchoice|menu|endmenu)\b", source[start + len(header):])
    end = start + len(header) + after.start() if after else len(source)
    block = source[start:end]
    if block.count(depends + "\n") != 1:
        raise ValueError("Stage88 vendor dependency mismatch: " + name)
    if "!PREEMPT_RT_FULL" in block:
        raise ValueError("Stage88 RT dependency already present: " + name)
    patched = block.replace(
        depends + "\n", depends + " && !PREEMPT_RT_FULL\n", 1
    )
    if patched.replace(
        depends + " && !PREEMPT_RT_FULL\n", depends + "\n", 1
    ) != block:
        raise ValueError("Stage88 unexpected vendor config change")
    return source[:start] + patched + source[end:]


def require_tree(tree: Path) -> None:
    if not (tree / ".git").is_dir():
        raise ValueError("Stage88 requires pinned E404 isolated RT checkout")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage88 requires all 64 original RT rejects retained")
    if not (tree / AUDIT_SENTINEL).is_file():
        raise ValueError("Stage88 RT scheduler rejection audit sentinel missing")


def prepare(tree: Path, index_file: Path) -> tuple[dict[str, str], dict]:
    require_tree(tree)
    if not index_file.is_file():
        raise ValueError("Stage88 requires Stage82 immutable reject inventory")
    index = json.loads(index_file.read_text(encoding="utf-8"))
    if not (
        index.get("stage") == INDEX_STAGE
        and index.get("remaining_rejected_files") == 64
        and index.get("source_modified") is False
        and index.get("rejects_deleted") is False
    ):
        raise ValueError("Stage88 Stage82 inventory provenance mismatch")
    files: dict[str, str] = {}
    original_sha: dict[str, str] = {}
    patched_sha: dict[str, str] = {}
    for relative, spec in FILES.items():
        target = tree / relative
        rejected = tree / (relative + ".rej")
        if not target.is_file() or not rejected.is_file():
            raise ValueError("Stage88 pinned Kconfig or rejected hunk missing: " + relative)
        if sha_bytes(rejected) != spec["sha"]:
            raise ValueError("Stage88 RT rejected SHA mismatch: " + relative)
        entries = [
            x for x in index.get("entries", []) if x.get("source") == relative
        ]
        if len(entries) != 1 or entries[0].get("reject_sha256") != spec["sha"] or \
           entries[0].get("hunk_count") != spec["hunks"]:
            raise ValueError("Stage88 Stage82 Kconfig inventory mismatch: " + relative)
        hunks, minus, plus = hunk_changes(rejected.read_text(encoding="utf-8"))
        if hunks != spec["hunks"] or tuple(minus) != spec["minus"] or tuple(plus) != spec["plus"]:
            raise ValueError("Stage88 upstream Kconfig rejected hunk changed: " + relative)
        source = target.read_text(encoding="utf-8")
        patched = source
        for name, depends in spec["dependencies"].items():
            patched = patch_config(patched, name, depends)
        files[relative] = patched
        original_sha[relative] = hashlib.sha256(source.encode()).hexdigest()
        patched_sha[relative] = hashlib.sha256(patched.encode()).hexdigest()
    return files, {
        "stage": STAGE,
        "configs_patched": list(CONFIGS),
        "kconfig_files_patched": sorted(files),
        "upstream_rejected_hunks_reviewed": 2,
        "upstream_rejected_lines_reviewed": 3,
        "vendor_rwsem_prerequisites_preserved": True,
        "rt_guard": "!PREEMPT_RT_FULL",
        "original_source_sha256": original_sha,
        "patched_source_sha256": patched_sha,
        "original_reject_sha256": {
            relative: spec["sha"] for relative, spec in FILES.items()
        },
        "original_rejects_retained": True,
        "remaining_rejected_files": 64,
        "effective_config_verified": False,
        "rt_semantic_review_complete": False,
        "runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }


def execute(tree: Path, index: Path, report: Path, mode: str,
            config: Path | None = None) -> dict:
    if mode not in ("verify", "apply", "verify-config"):
        raise ValueError("Stage88 expected verify, apply or verify-config")
    require_tree(tree)
    if mode == "verify-config":
        status_file = report / REPORT
        if not status_file.is_file() or config is None or not config.is_file():
            raise ValueError("Stage88 requires applied report and generated .config")
        status = json.loads(status_file.read_text(encoding="utf-8"))
        if status.get("stage") != STAGE or status.get("applied") is not True:
            raise ValueError("Stage88 only validates a previously applied patch")
        for relative in FILES:
            if sha_bytes(tree / relative) != status["patched_source_sha256"][relative]:
                raise ValueError("Stage88 patched Kconfig source hash mismatch")
        settings = set(config.read_text(encoding="utf-8").splitlines())
        if "CONFIG_PREEMPT_RT_FULL=y" not in settings:
            raise ValueError("Stage88 effective config lacks PREEMPT_RT_FULL=y")
        enabled = [name for name in CONFIGS if "CONFIG_" + name + "=y" in settings]
        if enabled:
            raise ValueError("Stage88 RT incompatible Kconfig options remain enabled: " +
                             ",".join(enabled))
        status["effective_config_verified"] = True
        status["effective_config_disabled"] = list(CONFIGS)
        if len(list(tree.rglob("*.rej"))) != 64:
            raise ValueError("Stage88 altered original RT rejects")
        status_file.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
        return status
    files, status = prepare(tree, index)
    if mode == "apply":
        for relative, text in files.items():
            (tree / relative).write_text(text, encoding="utf-8")
            if sha_bytes(tree / relative) != status["patched_source_sha256"][relative]:
                raise ValueError("Stage88 RT Kconfig post-write hash mismatch")
    status["applied"] = mode == "apply"
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage88 removed RT reject evidence")
    report.mkdir(parents=True, exist_ok=True)
    (report / REPORT).write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    return status


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", required=True, type=Path)
    p.add_argument("--index", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    p.add_argument("--mode", choices=("verify", "apply", "verify-config"), required=True)
    p.add_argument("--config", type=Path)
    a = p.parse_args()
    print(json.dumps(execute(
        a.tree.resolve(), a.index.resolve(), a.report.resolve(), a.mode,
        a.config.resolve() if a.config else None,
    ), indent=2))


if __name__ == "__main__":
    main()
