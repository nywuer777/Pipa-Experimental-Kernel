#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 GitHub Actions / EXP76 Stage91 PID atomic include regressions / NO FLASH
"""Verify a single source-only RT hunk with strict SHA and E404 ABI invariants."""
from __future__ import annotations

import hashlib
import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(
    str(ROOT / "tools/exp76-stage91-pid-atomic-header.py"),
    run_name="stage91_regression_fixture",
)
REJECT_SOURCE = (
    "diff --git a/include/linux/pid.h b/include/linux/pid.h\n"
    "--- a/include/linux/pid.h\n"
    "+++ b/include/linux/pid.h\n"
    "@@ -3,6 +3,7 @@\n"
    " #define _LINUX_PID_H\n"
    " \n"
    "+#include <linux/atomic.h>\n"
    " #include <linux/rculist.h>\n"
    " #include <linux/wait.h>\n"
)
PID_SOURCE = (
    "/* SPDX-License-Identifier: GPL-2.0 */\n"
    "#ifndef _LINUX_PID_H\n#define _LINUX_PID_H\n\n"
    "#include <linux/rculist.h>\n#include <linux/wait.h>\n"
    "struct pid {\n\tatomic_t count;\n\twait_queue_head_t wait_pidfd;\n};\n"
    "static inline struct pid *get_pid(struct pid *pid)\n{\n"
    "\tif (pid)\n\t\tatomic_inc(&pid->count);\n"
    "\treturn pid;\n}\n#endif\n"
)
ATOMIC_SOURCE = (
    "/* atomic API */\n#ifndef _LINUX_ATOMIC_H\n"
    "#define _LINUX_ATOMIC_H\n#include <asm/atomic.h>\n"
    "typedef int atomic_t;\n#endif\n"
)


def put(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def fixture(root: Path) -> tuple[Path, Path, Path]:
    tree = root / "trial"
    (tree / ".git").mkdir(parents=True)
    put(tree / M["TARGET"], PID_SOURCE)
    put(tree / M["HEADER"], ATOMIC_SOURCE)
    put(tree / M["REJECT"], REJECT_SOURCE)
    for i in range(63):
        put(tree / f"conflicts/{i:02d}.rej", "@@ -1 +1 @@\n-old\n+new\n")
    inventory = root / "stage82.json"
    put(inventory, json.dumps({
        "stage": M["INVENTORY_STAGE"],
        "remaining_rejected_files": 64,
        "source_modified": False,
        "rejects_deleted": False,
        "entries": [{
            "source": M["TARGET"],
            "reject_sha256": hashlib.sha256(REJECT_SOURCE.encode()).hexdigest(),
            "hunk_count": 1,
            "added_lines": 1,
            "removed_lines": 0,
        }],
    }))
    return tree, inventory, root / "report"


def check_reject(fn, message: str) -> None:
    try:
        fn()
    except ValueError as exc:
        assert message in str(exc), str(exc)
    else:
        raise AssertionError("Stage91 accepted invalid input: " + message)


def run(args: tuple[Path, Path, Path], mode: str) -> dict:
    return M["execute"](*args, mode)


def main() -> None:
    assert M["REJECT_SHA"] == (
        "bc68702b84df9b927e5753d3ea1bece48787733eab2f55b90849d39369a7c403"
    )
    original_hash = M["prepare"].__globals__["REJECT_SHA"]
    M["prepare"].__globals__["REJECT_SHA"] = hashlib.sha256(
        REJECT_SOURCE.encode()
    ).hexdigest()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = fixture(root / "valid")
            original = (good[0] / M["TARGET"]).read_bytes()
            reject = (good[0] / M["REJECT"]).read_bytes()
            dry = run(good, "verify")
            assert dry["applied"] is False
            assert (good[0] / M["TARGET"]).read_bytes() == original
            applied = run(good, "apply")
            assert applied["applied"] is True
            assert applied["rejected_hunks_reviewed"] == 1
            assert applied["header_dependencies_added"] == 1
            assert applied["pid_atomic_api_usage_preserved"] is True
            assert applied["vendor_pidfd_abi_preserved"] is True
            assert applied["source_change_only_include"] is True
            assert applied["original_reject_retained"] is True
            assert applied["remaining_rejected_files"] == 64
            assert not applied["scheduler_runtime_review_complete"]
            assert not applied["kernel_built"] and not applied["flash_ready"]
            result = (good[0] / M["TARGET"]).read_text()
            assert result.count(M["INSERT"]) == 1
            assert result.replace(M["INSERT"] + M["ANCHOR"], M["ANCHOR"], 1).encode() == original
            assert (good[0] / M["REJECT"]).read_bytes() == reject
            assert json.loads((good[2] / M["REPORT"]).read_text()) == applied
            check_reject(lambda: run(good, "apply"), "already included")

            missing_git = fixture(root / "git")
            (missing_git[0] / ".git").rmdir()
            check_reject(lambda: run(missing_git, "apply"), "isolated Git")

            missing_header = fixture(root / "no-header")
            (missing_header[0] / M["HEADER"]).unlink()
            check_reject(lambda: run(missing_header, "apply"), "sources, atomic.h")

            corrupted_hunk = fixture(root / "wrong-hunk")
            p = corrupted_hunk[0] / M["REJECT"]
            put(p, p.read_text().replace("+#include <linux/atomic.h>",
                                         "+#include <linux/types.h>"))
            M["prepare"].__globals__["REJECT_SHA"] = hashlib.sha256(p.read_bytes()).hexdigest()
            check_reject(lambda: run(corrupted_hunk, "apply"), "rejected hunk drift")
            M["prepare"].__globals__["REJECT_SHA"] = hashlib.sha256(REJECT_SOURCE.encode()).hexdigest()

            wrong_hash = fixture(root / "hash")
            put(wrong_hash[0] / M["REJECT"], REJECT_SOURCE + "# tampered\n")
            check_reject(lambda: run(wrong_hash, "apply"), "SHA256 drift")

            wrong_index = fixture(root / "index")
            obj = json.loads(wrong_index[1].read_text())
            obj["entries"][0]["added_lines"] = 2
            put(wrong_index[1], json.dumps(obj))
            check_reject(lambda: run(wrong_index, "apply"), "provenance drift")

            drift_source = fixture(root / "source")
            put(drift_source[0] / M["TARGET"], PID_SOURCE.replace(
                "\tatomic_inc(&pid->count);", "\tatomic_dec(&pid->count);"))
            check_reject(lambda: run(drift_source, "apply"), "atomic API usage drift")

            missing_pidfd = fixture(root / "pidfd")
            put(missing_pidfd[0] / M["TARGET"], PID_SOURCE.replace(
                "wait_queue_head_t wait_pidfd;", "int old_pidfd;"))
            check_reject(lambda: run(missing_pidfd, "apply"), "vendor pidfd ABI")

            incomplete_atomic = fixture(root / "atomic")
            put(incomplete_atomic[0] / M["HEADER"],
                "#ifndef _LINUX_ATOMIC_H\n#define _LINUX_ATOMIC_H\n#endif\n")
            check_reject(lambda: run(incomplete_atomic, "apply"), "atomic.h is incomplete")

            count_bad = fixture(root / "reject-count")
            (count_bad[0] / "conflicts/01.rej").unlink()
            check_reject(lambda: run(count_bad, "apply"), "64 RT rejects")

            no_manifest = fixture(root / "manifest")
            no_manifest[1].unlink()
            check_reject(lambda: run(no_manifest, "apply"), "inventory missing")

            wrong_mode = fixture(root / "mode")
            check_reject(lambda: run(wrong_mode, "flash"), "verify or apply")
    finally:
        M["prepare"].__globals__["REJECT_SHA"] = original_hash
    print(
        "EXP76_STAGE91_PINNED_PID_ATOMIC_REGRESSIONS=12_PASS; "
        "RT_REJECTS=64; FLASH_READY=false"
    )


if __name__ == "__main__":
    main()
