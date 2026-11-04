#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage82 inventory tests / NO FLASH
"""Validate real diff-hunk extraction, manifest comparisons and no source edits."""
from __future__ import annotations

import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(
    str(ROOT / "tools/exp76-stage82-rt-reject-inventory.py"),
    run_name="stage82_fixture",
)
DIFF = (
    "diff --git a/kernel/sched/cpupri.c b/kernel/sched/cpupri.c\n"
    "--- a/kernel/sched/cpupri.c\n"
    "+++ b/kernel/sched/cpupri.c\n"
    "@@ -12,3 +12,4 @@ static void test(void)\n"
    " context line\n"
    "-old();\n"
    "+new();\n"
    "+another();\n"
    " end context\n"
    "@@ -100 +101 @@\n"
    "-old_two();\n"
    "+new_two();\n"
)


def put(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def fixture(base: Path) -> tuple[Path, Path, Path]:
    tree = base / "kernel"
    (tree / ".git").mkdir(parents=True)
    put(tree / M["SENTINEL"], DIFF)
    put(tree / "kernel/sched/cpupri.c", "unmodified kernel source\n")
    put(tree / "kernel/rcu/tree.c.rej", (
        "@@ -2,2 +2,2 @@\n unchanged\n-old_rcu();\n+new_rcu();\n"
    ))
    put(tree / "kernel/rcu/tree.c", "rcu source\n")
    put(tree / "include/linux/spinlock_types.h.rej", (
        "@@ -5 +5 @@\n-old_lock();\n+new_lock();\n"
    ))
    put(tree / "include/linux/spinlock_types.h", "source untouched\n")
    for i in range(61):
        rel = f"drivers/vendor/rejected_{i:02d}.c"
        put(tree / (rel + ".rej"), f"@@ -{i + 1} +{i + 1} @@\n-old();\n+rt();\n")
        put(tree / rel, "original driver source\n")
    manifest = base / "original-rejected-paths.txt"
    paths = sorted(
        p.relative_to(tree).as_posix()[:-4] for p in tree.rglob("*.rej")
    )
    put(manifest, "\n".join(paths + ["kernel/locking/already-ported.c"]) + "\n")
    return tree, manifest, base / "out"


def reject(fn, expected: str) -> None:
    try:
        fn()
    except ValueError as exc:
        assert expected in str(exc), str(exc)
    else:
        raise AssertionError("Expected Stage82 rejection: " + expected)


def main() -> None:
    hunks, issues = M["parse_reject"](DIFF)
    assert not issues and len(hunks) == 2
    assert hunks[0]["old_start"] == 12
    assert hunks[0]["old_count"] == 3
    assert hunks[0]["new_start"] == 12
    assert hunks[0]["new_count"] == 4
    assert hunks[0]["added_lines"] == 2
    assert hunks[0]["removed_lines"] == 1
    assert hunks[0]["context_lines"] == 2
    assert hunks[1]["added_lines"] == 1
    assert hunks[1]["removed_lines"] == 1
    bad, warnings = M["parse_reject"]("@@ broken\n+something\n")
    assert bad == [] and len(warnings) == 2

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        tree, manifest, report = fixture(root / "good")
        before_source = (tree / "kernel/sched/cpupri.c").read_bytes()
        before_rej = (tree / M["SENTINEL"]).read_bytes()
        result = M["execute"](tree, manifest, report)
        assert result["remaining_rejected_files"] == 64
        assert result["initial_rejected_path_count"] == 65
        assert result["remaining_in_initial_manifest"] == 64
        assert result["remaining_not_in_initial_manifest"] == []
        assert result["initial_paths_no_longer_rejected"] == [
            "kernel/locking/already-ported.c",
        ]
        assert result["total_rejected_hunks"] == 65
        assert result["total_added_lines"] == 66
        assert result["total_removed_lines"] == 65
        assert result["categories"]["locking_scheduler"] == 2
        assert result["categories"]["rcu"] == 1
        assert result["categories"]["subsystem"] == 61
        assert result["priority_order"][0] in (
            "kernel/sched/cpupri.c", "include/linux/spinlock_types.h",
        )
        assert len(result["entries"]) == 64
        assert result["unparseable_reject_files"] == []
        assert result["missing_source_files"] == []
        assert not result["source_modified"] and not result["rejects_deleted"]
        assert not result["resolution_verified"]
        assert not result["kernel_built"] and not result["flash_ready"]
        assert (tree / "kernel/sched/cpupri.c").read_bytes() == before_source
        assert (tree / M["SENTINEL"]).read_bytes() == before_rej
        assert json.loads((report / M["REPORT_JSON"]).read_text()) == result
        md = (report / M["REPORT_MD"]).read_text()
        assert "64" in md and "kernel/sched/cpupri.c" in md
        assert "No reject has been cleared" in md

        missing_sentinel = fixture(root / "missing-sentinel")
        (missing_sentinel[0] / M["SENTINEL"]).unlink()
        reject(lambda: M["index_rejects"](*missing_sentinel[:2]),
               "scheduler reject sentinel")

        count_drift = fixture(root / "count-drift")
        (count_drift[0] / "drivers/vendor/rejected_00.c.rej").unlink()
        reject(lambda: M["index_rejects"](*count_drift[:2]),
               "expected 64 RT reject files")

        missing_manifest = fixture(root / "missing-manifest")
        missing_manifest[1].unlink()
        reject(lambda: M["index_rejects"](*missing_manifest[:2]),
               "original immutable")

        duplicate_manifest = fixture(root / "duplicate-manifest")
        mp = duplicate_manifest[1]
        put(mp, mp.read_text() + "kernel/rcu/tree.c\n")
        reject(lambda: M["index_rejects"](*duplicate_manifest[:2]),
               "empty or duplicated")

        no_git = fixture(root / "no-git")
        (no_git[0] / ".git").rmdir()
        reject(lambda: M["index_rejects"](*no_git[:2]), "isolated E404")

        malformed = fixture(root / "malformed")
        p = malformed[0] / "drivers/vendor/rejected_00.c.rej"
        put(p, "This reject is not a unified-diff hunk\n")
        summary = M["index_rejects"](*malformed[:2])
        assert p.relative_to(malformed[0]).as_posix() in (
            summary["unparseable_reject_files"]
        )
        assert summary["remaining_rejected_files"] == 64
        assert summary["total_rejected_hunks"] == 64

        missing_source = fixture(root / "missing-source")
        (missing_source[0] / "drivers/vendor/rejected_01.c").unlink()
        state = M["index_rejects"](*missing_source[:2])
        assert "drivers/vendor/rejected_01.c" in state["missing_source_files"]

        unknown_source = fixture(root / "not-in-manifest")
        mp = unknown_source[1]
        put(mp, "kernel/locking/already-ported.c\n")
        state = M["index_rejects"](*unknown_source[:2])
        assert len(state["remaining_not_in_initial_manifest"]) == 64
        assert len(state["initial_paths_no_longer_rejected"]) == 1

    print(
        "EXP76_STAGE82_RT_REJECT_INVENTORY_REGRESSIONS=12_PASS; "
        "REJECTS=64; KERNEL_BUILT=false; FLASH_READY=false"
    )


if __name__ == "__main__":
    main()
