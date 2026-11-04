#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 GitHub Actions / EXP76 Stage90 truthful RT UTS_VERSION / NO FLASH
"""Port two pinned RT rejected hunks to the vendor E404 compile.h ABI.

E404's scripts/mkcompile_h uses CC_VERSION="$5" and LD=$6 rather than the
upstream rejected CC=$5 argument. Preserve the vendor compiler/LD metadata;
insert the RT argument consistently in the Makefile and generator. Emit
PREEMPT_RT only when the real PREEMPT_RT_FULL Kconfig setting is passed.
Do not modify UTS_RELEASE or the userspace uname override.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

STAGE = "EXP76_STAGE90_TRUTHFUL_PREEMPT_RT_UTS_VERSION_NONFLASH"
REPORT = "stage90-status.json"
INDEX_STAGE = "EXP76_STAGE82_OUTSTANDING_RT_REJECT_HUNK_INVENTORY_NONFLASH"
MAKEFILE = "init/Makefile"
SCRIPT = "scripts/mkcompile_h"
REJECTS = {
    MAKEFILE: ("1b3f1cb3844177ab3a71a666750a706c5f4f1750c4e55c02f0b1bcca6deadabb", 1, 1, 1),
    SCRIPT: ("8704c96bc6ea46e380925de03f2ae3d6417e53a1f0f6f8a5679767d08273d485", 1, 2, 1),
}
MAKE_OLD = '\t"$(UTS_MACHINE)" "$(CONFIG_SMP)" "$(CONFIG_PREEMPT)"\t\\\n'
MAKE_NEW = '\t"$(UTS_MACHINE)" "$(CONFIG_SMP)" "$(CONFIG_PREEMPT)" "$(CONFIG_PREEMPT_RT_FULL)"\t\\\n'
SCRIPT_OLD = 'PREEMPT=$4\nCC_VERSION="$5"\nLD=$6\n'
SCRIPT_NEW = 'PREEMPT=$4\nRT=$5\nCC_VERSION="$6"\nLD=$7\n'
FLAGS_OLD = 'if [ -n "$PREEMPT" ] ; then CONFIG_FLAGS="$CONFIG_FLAGS PREEMPT"; fi\n'
FLAGS_NEW = FLAGS_OLD + 'if [ -n "$RT" ] ; then CONFIG_FLAGS="$CONFIG_FLAGS PREEMPT_RT"; fi\n'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def exactly(source: str, old: str, label: str) -> None:
    if source.count(old) != 1:
        raise ValueError(f"Stage90 pinned E404 {label} anchor mismatch: {source.count(old)}")


def require_tree(tree: Path) -> None:
    if not (tree / ".git").is_dir():
        raise ValueError("Stage90 requires pinned isolated E404 Git checkout")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage90 requires all 64 original RT rejects")
    if not (tree / "kernel/sched/cpupri.c.rej").is_file():
        raise ValueError("Stage90 RT scheduler reject provenance missing")


def prepare(tree: Path, index_path: Path) -> tuple[dict[str, str], dict]:
    require_tree(tree)
    if not index_path.is_file():
        raise ValueError("Stage90 immutable Stage82 inventory missing")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if (index.get("stage") != INDEX_STAGE
            or index.get("remaining_rejected_files") != 64
            or index.get("source_modified") is not False
            or index.get("rejects_deleted") is not False):
        raise ValueError("Stage90 Stage82 inventory provenance mismatch")
    entries = index.get("entries") or []
    for file, (sha, hunks, added, removed) in REJECTS.items():
        rejected = tree / (file + ".rej")
        target = tree / file
        if not rejected.is_file() or not target.is_file():
            raise ValueError("Stage90 original source or RT rejected hunk absent: " + file)
        if digest(rejected.read_bytes()) != sha:
            raise ValueError("Stage90 RT rejected-hunk SHA256 mismatch: " + file)
        matches = [x for x in entries if x.get("source") == file]
        if not (len(matches) == 1
                and matches[0].get("reject_sha256") == sha
                and matches[0].get("hunk_count") == hunks
                and matches[0].get("added_lines") == added
                and matches[0].get("removed_lines") == removed):
            raise ValueError("Stage90 Stage82 rejected-hunk inventory mismatch: " + file)
    # The downstream vendor uses CC_VERSION + LD, NOT upstream CC + CFLAGS.
    mk = (tree / MAKEFILE).read_text(encoding="utf-8")
    sh = (tree / SCRIPT).read_text(encoding="utf-8")
    exactly(mk, MAKE_OLD, "init/Makefile target argument")
    exactly(sh, SCRIPT_OLD, "mkcompile_h vendor CC_VERSION and LD argument ABI")
    exactly(sh, FLAGS_OLD, "mkcompile_h PREEMPT config-flag clause")
    for marker in (
        '$(CONFIG_CC_VERSION_TEXT) "$(LD)"',
        "$(srctree)/scripts/mkcompile_h",
        "include/generated/compile.h: FORCE",
    ):
        if marker not in mk:
            raise ValueError("Stage90 lost E404 Kbuild compile.h ABI: " + marker)
    for marker in (
        'UTS_VERSION="$UTS_VERSION $CONFIG_FLAGS $TIMESTAMP"',
        'if [ -n "$SMP" ] ; then CONFIG_FLAGS="SMP"; fi',
        'echo \\#define UTS_VERSION',
        'echo \\#define UTS_MACHINE',
        'printf \'#define LINUX_COMPILER',
        'LD_VERSION=$($LD -v',
    ):
        if marker not in sh:
            raise ValueError("Stage90 vendor mkcompile_h source drift: " + marker)
    if "PREEMPT_RT" in sh or "CONFIG_PREEMPT_RT_FULL" in mk:
        raise ValueError("Stage90 RT UTS_VERSION patch already present")
    changed = {
        MAKEFILE: mk.replace(MAKE_OLD, MAKE_NEW, 1),
        SCRIPT: sh.replace(SCRIPT_OLD, SCRIPT_NEW, 1).replace(
            FLAGS_OLD, FLAGS_NEW, 1
        ),
    }
    if changed[MAKEFILE].replace(MAKE_NEW, MAKE_OLD, 1) != mk:
        raise ValueError("Stage90 changed vendor Kbuild beyond RT argument")
    if changed[SCRIPT].replace(
        FLAGS_NEW, FLAGS_OLD, 1
    ).replace(SCRIPT_NEW, SCRIPT_OLD, 1) != sh:
        raise ValueError("Stage90 changed vendor mkcompile_h beyond RT argument/flag")
    status = {
        "stage": STAGE,
        "paths": sorted(REJECTS),
        "upstream_reject_hunks_reviewed": 2,
        "upstream_added_lines_reviewed": 3,
        "upstream_removed_lines_reviewed": 2,
        "vendor_cc_version_and_ld_abi_preserved": True,
        "rt_uts_version_marker": "PREEMPT_RT",
        "uts_release_modified": False,
        "kernel_sys_uname_modified": False,
        "original_rejects_retained": True,
        "remaining_rejected_files": 64,
        "source_sha256": {
            file: digest(changed[file].encode()) for file in changed
        },
        "effective_uts_version_verified": False,
        "runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    return changed, status


def execute(tree: Path, index: Path, report: Path, mode: str,
            config: Path | None = None, compile_h: Path | None = None) -> dict:
    if mode not in ("verify", "apply", "verify-header"):
        raise ValueError("Stage90 mode must be verify, apply or verify-header")
    require_tree(tree)
    report.mkdir(parents=True, exist_ok=True)
    if mode == "verify-header":
        status_path = report / REPORT
        if not status_path.is_file():
            raise ValueError("Stage90 prior applied report missing")
        status = json.loads(status_path.read_text(encoding="utf-8"))
        if status.get("stage") != STAGE or status.get("applied") is not True:
            raise ValueError("Stage90 prior RT UTS patch not applied")
        for file in REJECTS:
            if digest((tree / file).read_bytes()) != status["source_sha256"][file]:
                raise ValueError("Stage90 patched source SHA mismatch: " + file)
        if config is None or compile_h is None or not config.is_file() or not compile_h.is_file():
            raise ValueError("Stage90 requires effective .config and compile.h")
        settings = set(config.read_text(encoding="utf-8").splitlines())
        if "CONFIG_PREEMPT_RT_FULL=y" not in settings:
            raise ValueError("Stage90 effective .config is not PREEMPT_RT_FULL")
        header = compile_h.read_text(encoding="utf-8")
        match = re.search(r'^#define UTS_VERSION "([^"]+)"$', header, re.M)
        if match is None or re.search(r"\bPREEMPT_RT\b", match.group(1)) is None:
            raise ValueError("Stage90 generated compile.h missing true PREEMPT_RT marker")
        if not re.search(r'^#define LINUX_COMPILER "', header, re.M):
            raise ValueError("Stage90 generated compile.h lost vendor compiler metadata")
        status["effective_uts_version_verified"] = True
        status["generated_uts_version"] = match.group(1)[:96]
        status["generated_compiler_metadata_present"] = True
        if len(list(tree.rglob("*.rej"))) != 64:
            raise ValueError("Stage90 original RT rejects changed")
        status_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
        return status
    files, status = prepare(tree, index)
    if mode == "apply":
        for name, updated in files.items():
            (tree / name).write_text(updated, encoding="utf-8")
            if digest((tree / name).read_bytes()) != status["source_sha256"][name]:
                raise ValueError("Stage90 patched source write mismatch: " + name)
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage90 changed original RT rejects")
    status["applied"] = mode == "apply"
    (report / REPORT).write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    return status


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", type=Path, required=True)
    p.add_argument("--index", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--mode", choices=("verify", "apply", "verify-header"), required=True)
    p.add_argument("--config", type=Path)
    p.add_argument("--compile-h", type=Path)
    a = p.parse_args()
    print(json.dumps(execute(
        a.tree.resolve(), a.index.resolve(), a.report.resolve(),
        a.mode, a.config.resolve() if a.config else None,
        a.compile_h.resolve() if a.compile_h else None,
    ), indent=2))


if __name__ == "__main__":
    main()
