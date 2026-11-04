#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 GitHub Actions / EXP76 Stage90 RT UTS_VERSION regressions / NO FLASH
"""Exercise pinned RT hunks, compiler metadata and real shell UTS output."""
from __future__ import annotations
import hashlib
import json
import os
import runpy
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT / "tools/exp76-stage90-rt-uts-version.py"), run_name="stage90_test_helpers")
MK_REJ = (
    "diff --git a/init/Makefile b/init/Makefile\n"
    "--- a/init/Makefile\n+++ b/init/Makefile\n"
    "@@ -34,4 +34,4 @@ $(obj)/version.o: include/generated/compile.h\n"
    '-\t"$(UTS_MACHINE)" "$(CONFIG_SMP)" "$(CONFIG_PREEMPT)" "$(CC) $(KBUILD_CFLAGS)"\n'
    '+\t"$(UTS_MACHINE)" "$(CONFIG_SMP)" "$(CONFIG_PREEMPT)" "$(CONFIG_PREEMPT_RT_FULL)" "$(CC) $(KBUILD_CFLAGS)"\n'
)
SH_REJ = (
    "diff --git a/scripts/mkcompile_h b/scripts/mkcompile_h\n"
    "--- a/scripts/mkcompile_h\n+++ b/scripts/mkcompile_h\n"
    "@@ -5,7 +5,8 @@ TARGET=$1\n-CC=$5\n+RT=$5\n+CC=$6\n"
)
SH = r'''#!/bin/sh
TARGET=$1
ARCH=$2
SMP=$3
PREEMPT=$4
CC_VERSION="$5"
LD=$6
UTS_VERSION="#7"
CONFIG_FLAGS=""
if [ -n "$SMP" ] ; then CONFIG_FLAGS="SMP"; fi
if [ -n "$PREEMPT" ] ; then CONFIG_FLAGS="$CONFIG_FLAGS PREEMPT"; fi
TIMESTAMP="2026-11-04"
UTS_VERSION="$UTS_VERSION $CONFIG_FLAGS $TIMESTAMP"
LD_VERSION=$($LD -v | head -n1)
echo \#define UTS_MACHINE \"$ARCH\" > "$TARGET"
echo \#define UTS_VERSION \"$UTS_VERSION\" >> "$TARGET"
printf '#define LINUX_COMPILER "%s"\n' "$CC_VERSION, $LD_VERSION" >> "$TARGET"
'''
MK = (
    "include/generated/compile.h: FORCE\n"
    "\t$(Q)$(CONFIG_SHELL) $(srctree)/scripts/mkcompile_h $@\t\\\n"
    + M["MAKE_OLD"] + '\t$(CONFIG_CC_VERSION_TEXT) "$(LD)"\n'
)


def put(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def fixture(root: Path) -> tuple[Path, ...]:
    tree = root / "trial"
    (tree / ".git").mkdir(parents=True)
    put(tree / M["MAKEFILE"], MK)
    put(tree / M["SCRIPT"], SH)
    put(tree / (M["MAKEFILE"] + ".rej"), MK_REJ)
    put(tree / (M["SCRIPT"] + ".rej"), SH_REJ)
    for i in range(61):
        put(tree / f"pending/rej-{i:02d}.c.rej", "@@ -1 +1 @@\n-old\n+new\n")
    put(tree / "kernel/sched/cpupri.c.rej", "@@ -1 +1 @@\n-old\n+new\n")
    inventory = root / "stage82.json"
    entries = []
    for path in M["REJECTS"]:
        _hash, hunks, added, removed = M["REJECTS"][path]
        entries.append({
            "source": path,
            "reject_sha256": hashlib.sha256((tree / (path + ".rej")).read_bytes()).hexdigest(),
            "hunk_count": hunks, "added_lines": added, "removed_lines": removed,
        })
    put(inventory, json.dumps({
        "stage": M["INDEX_STAGE"], "remaining_rejected_files": 64,
        "source_modified": False, "rejects_deleted": False, "entries": entries,
    }))
    config = root / ".config"
    put(config, "CONFIG_PREEMPT_RT_FULL=y\n")
    return tree, inventory, root / "report", config, root / "compile.h"


def invoke(args: tuple[Path, ...], mode: str) -> dict:
    return M["execute"](*args[:3], mode, args[3], args[4])


def run_shell(args: tuple[Path, ...], rt: bool, preempt: bool = False) -> str:
    tree, _, _, _, target = args
    subprocess.run([
        "/bin/sh", str(tree / M["SCRIPT"]), str(target),
        "aarch64", "y", "y" if preempt else "", "y" if rt else "",
        "Android Clang 21.0.0", "/bin/echo",
    ], cwd=tree, env=dict(os.environ), check=True, capture_output=True, text=True)
    return target.read_text(encoding="utf-8")


def reject(fn, message: str) -> None:
    try:
        fn()
    except ValueError as error:
        assert message in str(error), (message, str(error))
    else:
        raise AssertionError("Stage90 accepted invalid input: " + message)


def main() -> None:
    original = dict(M["REJECTS"])
    try:
        for p, content in ((M["MAKEFILE"], MK_REJ), (M["SCRIPT"], SH_REJ)):
            old, hunks, plus, minus = M["REJECTS"][p]
            M["REJECTS"][p] = (hashlib.sha256(content.encode()).hexdigest(),
                               hunks, plus, minus)
        assert len(M["REJECTS"]) == 2
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            good = fixture(root / "good")
            initial = {
                f: (good[0] / f).read_bytes() for f in M["REJECTS"]
            }
            rejects_before = {
                f: (good[0] / (f + ".rej")).read_bytes() for f in M["REJECTS"]
            }
            dry = invoke(good, "verify")
            assert dry["applied"] is False
            assert all((good[0] / f).read_bytes() == initial[f] for f in initial)
            applied = invoke(good, "apply")
            assert applied["applied"] is True
            assert applied["upstream_reject_hunks_reviewed"] == 2
            assert applied["vendor_cc_version_and_ld_abi_preserved"]
            assert applied["uts_release_modified"] is False
            assert applied["kernel_sys_uname_modified"] is False
            assert not applied["effective_uts_version_verified"]
            assert applied["remaining_rejected_files"] == 64
            assert all((good[0] / (f + ".rej")).read_bytes() == rejects_before[f]
                       for f in rejects_before)
            assert len(list(good[0].rglob("*.rej"))) == 64
            rt_output = run_shell(good, True)
            assert '#define UTS_MACHINE "aarch64"' in rt_output
            assert "SMP PREEMPT_RT" in rt_output
            assert "Android Clang 21.0.0, -v" in rt_output
            checked = invoke(good, "verify-header")
            assert checked["effective_uts_version_verified"]
            assert "PREEMPT_RT" in checked["generated_uts_version"]
            assert checked["generated_compiler_metadata_present"]
            assert json.loads((good[2] / M["REPORT"]).read_text()) == checked
            assert not checked["kernel_built"] and not checked["flash_ready"]
            reject(lambda: invoke(good, "apply"), "anchor mismatch")

            non_rt = fixture(root / "non-rt")
            invoke(non_rt, "apply")
            regular_output = run_shell(non_rt, False, True)
            assert "SMP PREEMPT " in regular_output
            assert "PREEMPT_RT" not in regular_output
            put(non_rt[3], "CONFIG_PREEMPT=y\n")
            reject(lambda: invoke(non_rt, "verify-header"), "not PREEMPT_RT_FULL")

            no_marker = fixture(root / "no-marker")
            invoke(no_marker, "apply")
            run_shell(no_marker, False)
            reject(lambda: invoke(no_marker, "verify-header"), "missing true PREEMPT_RT")

            corrupted = fixture(root / "corrupted")
            invoke(corrupted, "apply")
            run_shell(corrupted, True)
            put(corrupted[4], corrupted[4].read_text().replace(
                "#define LINUX_COMPILER", "#define INVALID_COMPILER"))
            reject(lambda: invoke(corrupted, "verify-header"), "compiler metadata")

            modified = fixture(root / "modified")
            invoke(modified, "apply")
            put(modified[0] / M["SCRIPT"], (modified[0] / M["SCRIPT"]).read_text() + "# drift\n")
            run_shell(modified, True)
            reject(lambda: invoke(modified, "verify-header"), "source SHA mismatch")

            unsupported_vendor = fixture(root / "vendor")
            p = unsupported_vendor[0] / M["SCRIPT"]
            put(p, p.read_text().replace('CC_VERSION="$5"', "CC=$5"))
            reject(lambda: invoke(unsupported_vendor, "apply"), "vendor CC_VERSION")

            corrupted_reject = fixture(root / "reject")
            p = corrupted_reject[0] / (M["SCRIPT"] + ".rej")
            put(p, p.read_text() + "# corruption\n")
            reject(lambda: invoke(corrupted_reject, "apply"), "SHA256 mismatch")

            wrong_inventory = fixture(root / "inventory")
            d = json.loads(wrong_inventory[1].read_text())
            d["entries"][1]["removed_lines"] = 9
            put(wrong_inventory[1], json.dumps(d))
            reject(lambda: invoke(wrong_inventory, "apply"), "inventory mismatch")

            fewer = fixture(root / "fewer")
            (fewer[0] / "pending/rej-00.c.rej").unlink()
            reject(lambda: invoke(fewer, "apply"), "64 original")

            no_git = fixture(root / "no-git")
            (no_git[0] / ".git").rmdir()
            reject(lambda: invoke(no_git, "apply"), "isolated E404")

            missing_report = fixture(root / "report")
            reject(lambda: invoke(missing_report, "verify-header"), "prior applied report")

            wrong_mode = fixture(root / "mode")
            reject(lambda: invoke(wrong_mode, "flash"), "verify, apply or verify-header")
    finally:
        M["REJECTS"].clear()
        M["REJECTS"].update(original)
    print("EXP76_STAGE90_TRUTHFUL_RT_UTS_VERSION_REGRESSIONS=12_PASS; REJECTS=64; FLASH_READY=false")


if __name__ == "__main__":
    main()
