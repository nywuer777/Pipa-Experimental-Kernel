#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage51 neighbour RT pointer regression / NO FLASH
"""Assert a hunk-scoped const correction; no broad source/config changes."""
from __future__ import annotations

import hashlib
import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT / "tools/exp76-rt-stage51-neigh-const.py"), run_name="exp76_stage51_test")
prepare, execute = M["prepare"], M["execute"]
CALLEE, OLD, NEW = M["CALLEE"], M["CALLER_OLD"], M["CALLER_NEW"]
HEADER = M["HEADER"]


def fixture(parent: Path) -> Path:
    tree = parent / "trial"
    (tree / ".git").mkdir(parents=True)
    header = tree / HEADER
    header.parent.mkdir(parents=True)
    header.write_text("/* pinned E404 RT trial */\n" + CALLEE + "{ return 0; }\n" + OLD)
    rej_dir = tree / "kernel/sched"
    rej_dir.mkdir(parents=True)
    (rej_dir / "cpupri.c.rej").write_text("pending\n")
    for index in range(63):
        (rej_dir / f"reject-{index:02d}.rej").write_text("pending\n")
    return tree


def fails(fn: object, required: str) -> None:
    try:
        fn()
    except ValueError as exc:
        assert required in str(exc), str(exc)
    else:
        raise AssertionError("Expected rejection: " + required)


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        tree = fixture(root / "correct")
        source = tree / HEADER
        original = source.read_text()
        verified = execute(tree, root / "verify-report", "verify")
        assert source.read_text() == original
        assert verified["applied"] is False
        changed = execute(tree, root / "apply-report", "apply")
        assert source.read_text() == original.replace(OLD, NEW, 1)
        assert changed["applied"] is True
        assert changed["remaining_rejected_files"] == 64
        assert changed["kernel_built"] is False
        assert changed["flash_ready"] is False
        assert changed["original_sha256"] == hashlib.sha256(original.encode()).hexdigest()
        assert json.loads((root / "apply-report/stage51-status.json").read_text()) == changed
        fails(lambda: prepare(tree), "neigh_output vendor skip_cache caller")

        callee = fixture(root / "const-callee")
        path = callee / HEADER
        path.write_text(path.read_text().replace(CALLEE, CALLEE.replace(
            "(struct hh_cache", "(const struct hh_cache")))
        fails(lambda: prepare(callee), "RT mutable neigh_hh_output ABI")

        old_vendor = fixture(root / "missing-skip-cache")
        path = old_vendor / HEADER
        path.write_text(path.read_text().replace("bool skip_cache", "bool skip_header"))
        fails(lambda: prepare(old_vendor), "E404 neigh_output vendor skip_cache caller")

        duplicates = fixture(root / "ambiguous-caller")
        path = duplicates / HEADER
        path.write_text(path.read_text() + "\n" + OLD)
        fails(lambda: prepare(duplicates), "expected exactly one match")

        lost_reject = fixture(root / "lost-reject")
        (lost_reject / "kernel/sched/reject-00.rej").unlink()
        fails(lambda: prepare(lost_reject), "64 unresolved RT rejects")

        wrong_target = fixture(root / "wrong-git")
        (wrong_target / ".git").rmdir()
        fails(lambda: prepare(wrong_target), "isolated E404 git checkout")

        missing_cpupri = fixture(root / "missing-cpupri")
        old_rej = missing_cpupri / "kernel/sched/cpupri.c.rej"
        old_rej.rename(missing_cpupri / "kernel/sched/other.rej")
        fails(lambda: prepare(missing_cpupri), "cpupri.c.rej")

        invalid_mode = fixture(root / "mode")
        fails(lambda: execute(invalid_mode, root / "invalid-mode", "flash"), "Unsupported Stage51 mode")
    print("EXP76_STAGE51_NEIGH_RT_POINTER_REGRESSIONS=8_PASS; KERNEL_BUILT=false; FLASH_READY=false")


if __name__ == "__main__":
    main()
