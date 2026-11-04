#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage89 proc swait regressions / NO FLASH
"""Verify exact source-only swait include port and original reject retention."""
from __future__ import annotations

import hashlib
import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(
    str(ROOT / "tools/exp76-stage89-proc-swait.py"),
    run_name="exp76_stage89_synthetic_test",
)


def put(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def fixture(root: Path) -> tuple[Path, Path, Path]:
    tree = root / "trial"
    (tree / ".git").mkdir(parents=True)
    put(tree / M["TARGET"],
        "#include <linux/sched.h>\n"
        "#include <linux/posix-timers.h>\n"
        "#include <linux/cpufreq_times.h>\n"
        "\n#ifdef CONFIG_E404_ATTRIBUTES\n"
        "/* E404 vendor proc extension */\n"
        "#endif\n"
        "void proc_test(void) {}\n"
    )
    put(tree / M["HEADER"],
        "struct swait_queue_head {\n"
        "  int lock;\n"
        "};\n"
        "#define swait_event_interruptible_exclusive(wq, c) (0)\n"
    )
    reject = (
        "diff --git a/fs/proc/base.c b/fs/proc/base.c\n"
        "--- a/fs/proc/base.c\n"
        "+++ b/fs/proc/base.c\n"
        "@@ -95,6 +95,7 @@\n"
        " #include <linux/posix-timers.h>\n"
        "+#include <linux/swait.h>\n"
        " #include <linux/cpufreq_times.h>\n"
    )
    put(tree / M["REJECT"], reject)
    for i in range(63):
        put(tree / f"other/conflict-{i:02d}.rej", "@@ -1 +1 @@\n-old\n+new\n")
    digest = hashlib.sha256(reject.encode()).hexdigest()
    inventory = root / "stage82.json"
    put(inventory, json.dumps({
        "stage": M["STAGE82"],
        "remaining_rejected_files": 64,
        "source_modified": False,
        "rejects_deleted": False,
        "entries": [{
            "source": M["TARGET"],
            "reject_sha256": digest,
            "hunk_count": 1,
            "added_lines": 1,
            "removed_lines": 0,
        }],
    }))
    return tree, inventory, root / "report"


def pin(fx: tuple[Path, Path, Path]) -> None:
    M["verify"].__globals__["HASH"] = hashlib.sha256(
        (fx[0] / M["REJECT"]).read_bytes()
    ).hexdigest()


def reject(fn, description: str) -> None:
    try:
        fn()
    except ValueError as e:
        assert description in str(e), str(e)
    else:
        raise AssertionError("Stage89 accepted invalid fixture: " + description)


def execute(fx: tuple[Path, Path, Path], mode: str) -> dict:
    return M["execute"](*fx, mode)


def main() -> None:
    original_hash = M["verify"].__globals__["HASH"]
    assert original_hash == (
        "417c207cb7d9d129fbbe31fedf0959d6a983d726d524af48cd40fa9e06225719"
    )
    try:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            valid = fixture(root / "valid")
            pin(valid)
            source_before = (valid[0] / M["TARGET"]).read_bytes()
            reject_before = (valid[0] / M["REJECT"]).read_bytes()
            read_only = execute(valid, "verify")
            assert not read_only["applied"]
            assert (valid[0] / M["TARGET"]).read_bytes() == source_before
            applied = execute(valid, "apply")
            assert applied["applied"]
            assert applied["upstream_hunks_reviewed"] == 1
            assert applied["upstream_includes_added"] == 1
            assert applied["rt_swait_api_present"]
            assert applied["vendor_e404_code_preserved"]
            assert applied["original_reject_retained"]
            assert applied["remaining_rejected_files"] == 64
            assert not applied["scheduler_semantic_review_complete"]
            assert not applied["kernel_built"] and not applied["flash_ready"]
            text = (valid[0] / M["TARGET"]).read_text()
            assert text.count(M["NEW"]) == 1
            assert "CONFIG_E404_ATTRIBUTES" in text
            assert text.replace(M["ANCHOR"] + M["NEW"], M["ANCHOR"], 1).encode() == source_before
            assert (valid[0] / M["REJECT"]).read_bytes() == reject_before
            assert json.loads((valid[2] / M["REPORT"]).read_text()) == applied
            reject(lambda: execute(valid, "apply"), "already included")

            missing_git = fixture(root / "missing-git")
            pin(missing_git)
            (missing_git[0] / ".git").rmdir()
            reject(lambda: execute(missing_git, "apply"), "isolated E404")

            missing_header = fixture(root / "no-header")
            pin(missing_header)
            (missing_header[0] / M["HEADER"]).unlink()
            reject(lambda: execute(missing_header, "apply"), "source, reject and RT swait")

            changed_hash = fixture(root / "wrong-hash")
            pin(changed_hash)
            p = changed_hash[0] / M["REJECT"]
            put(p, p.read_text() + "# corruption\n")
            reject(lambda: execute(changed_hash, "apply"), "SHA256 mismatch")

            changed_hunk = fixture(root / "wrong-hunk")
            p = changed_hunk[0] / M["REJECT"]
            put(p, p.read_text().replace(
                "+#include <linux/swait.h>", "+#include <linux/wait.h>"
            ))
            pin(changed_hunk)
            reject(lambda: execute(changed_hunk, "apply"), "upstream swait")

            missing_inventory = fixture(root / "no-inventory")
            pin(missing_inventory)
            missing_inventory[1].unlink()
            reject(lambda: execute(missing_inventory, "apply"), "immutable reject inventory")

            stale_inventory = fixture(root / "wrong-inventory")
            pin(stale_inventory)
            data = json.loads(stale_inventory[1].read_text())
            data["entries"][0]["hunk_count"] = 2
            put(stale_inventory[1], json.dumps(data))
            reject(lambda: execute(stale_inventory, "apply"), "provenance mismatch")

            source_drift = fixture(root / "source")
            pin(source_drift)
            p = source_drift[0] / M["TARGET"]
            put(p, p.read_text().replace(M["ANCHOR"], ""))
            reject(lambda: execute(source_drift, "apply"), "include anchor mismatch")

            incomplete_header = fixture(root / "header")
            pin(incomplete_header)
            put(incomplete_header[0] / M["HEADER"], "struct swait_queue_head {};\n")
            reject(lambda: execute(incomplete_header, "apply"), "header API incomplete")

            fewer_rejects = fixture(root / "fewer")
            pin(fewer_rejects)
            (fewer_rejects[0] / "other/conflict-00.rej").unlink()
            reject(lambda: execute(fewer_rejects, "apply"), "exactly 64")

            bad_mode = fixture(root / "mode")
            pin(bad_mode)
            reject(lambda: execute(bad_mode, "flash"), "verify or apply")
    finally:
        M["verify"].__globals__["HASH"] = original_hash
    print(
        "EXP76_STAGE89_PROC_SWAIT_REGRESSIONS=11_PASS; "
        "REJECTS_RETAINED=64; FLASH_READY=false"
    )


if __name__ == "__main__":
    main()
