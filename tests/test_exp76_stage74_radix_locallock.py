#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage74 radix-tree regression / NO FLASH
"""Fail closed on missing RT locallock macros, source drift and reject changes."""
from __future__ import annotations

import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(
    str(ROOT / "tools/exp76-rt-stage74-radix-locallock.py"),
    run_name="exp76_stage74_fixture",
)
prepare, execute = M["prepare"], M["execute"]


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def fixture(root: Path) -> Path:
    tree = root / "overlay"
    (tree / ".git").mkdir(parents=True)
    write(tree / M["FILE"], (
        "/* RT radix-tree local locking fixture */\n"
        "#include <linux/kernel.h>\n"
        + M["ORIGINAL_INCLUDE"]
        + "#include <linux/preempt.h>\n"
        + M["RT_DECLARATION"] + "\n"
        + "void *preload(void)\n{\n"
        + "\tauto rtp = get_locked_var(radix_tree_preloads_lock, radix_tree_preloads);\n"
        + "\tput_locked_var(radix_tree_preloads_lock, radix_tree_preloads);\n"
        + "\tlocal_lock(radix_tree_preloads_lock);\n"
        + "\tlocal_unlock(radix_tree_preloads_lock);\n"
        + "\treturn 0;\n}\n"
    ))
    write(tree / M["HEADER"], (
        "#define DEFINE_LOCAL_IRQ_LOCK(lvar) 1\n"
        "#define get_locked_var(lvar, var) (var)\n"
        "#define put_locked_var(lvar, var) (void)0\n"
        "#define local_lock(lvar) (void)0\n"
        "#define local_unlock(lvar) (void)0\n"
    ))
    write(tree / M["REJECT"], "known RT reject\n")
    for i in range(63):
        write(tree / f"pending/{i:02d}.rej", "pending RT reject\n")
    return tree


def reject(fn, text: str) -> None:
    try:
        fn()
    except ValueError as error:
        assert text in str(error), str(error)
    else:
        raise AssertionError("Expected Stage74 rejection: " + text)


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        good = fixture(root / "good")
        before = (good / M["FILE"]).read_text(encoding="utf-8")
        verified = execute(good, root / "verify", "verify")
        assert verified["applied"] is False
        assert (good / M["FILE"]).read_text() == before
        applied = execute(good, root / "applied", "apply")
        assert applied["applied"] is True
        after = (good / M["FILE"]).read_text()
        assert after == before.replace(
            M["ORIGINAL_INCLUDE"], M["PATCHED_INCLUDE"], 1
        )
        assert applied["rt_lock_declaration_preserved"] is True
        assert applied["rt_lock_calls_preserved"] is True
        assert applied["existing_locallock_api_verified"] is True
        assert applied["remaining_rejected_files"] == 64
        assert not applied["kernel_built"] and not applied["flash_ready"]
        assert json.loads(
            (root / "applied/stage74-status.json").read_text()
        ) == applied
        reject(lambda: prepare(good), "already included")

        missing_header = fixture(root / "missing-header")
        (missing_header / M["HEADER"]).unlink()
        reject(lambda: prepare(missing_header), "requires pinned")

        missing_macro = fixture(root / "missing-macro")
        p = missing_macro / M["HEADER"]
        p.write_text(p.read_text().replace(
            "#define get_locked_var", "#define unknown_macro"
        ))
        reject(lambda: prepare(missing_macro), "missing API")

        no_declaration = fixture(root / "missing-declaration")
        p = no_declaration / M["FILE"]
        p.write_text(p.read_text().replace(
            M["RT_DECLARATION"], "static int unrelated;"
        ))
        reject(lambda: prepare(no_declaration), "declaration drift")

        missing_call = fixture(root / "missing-call")
        p = missing_call / M["FILE"]
        p.write_text(p.read_text().replace(
            "local_unlock(radix_tree_preloads_lock);",
            "local_irq_enable();",
        ))
        reject(lambda: prepare(missing_call), "preload locking API missing")

        anchor_drift = fixture(root / "missing-percpu")
        p = anchor_drift / M["FILE"]
        p.write_text(p.read_text().replace(
            M["ORIGINAL_INCLUDE"], "#include <linux/percpu-defs.h>\n"
        ))
        reject(lambda: prepare(anchor_drift), "include anchor drift")

        duplicate = fixture(root / "duplicate-percpu")
        p = duplicate / M["FILE"]
        p.write_text(p.read_text() + M["ORIGINAL_INCLUDE"])
        reject(lambda: prepare(duplicate), "include anchor drift")

        no_git = fixture(root / "no-git")
        (no_git / ".git").rmdir()
        reject(lambda: prepare(no_git), "isolated E404")

        lost_reject = fixture(root / "lost-reject")
        (lost_reject / "pending/00.rej").unlink()
        reject(lambda: prepare(lost_reject), "64 outstanding")

        lost_sentinel = fixture(root / "lost-sentinel")
        (lost_sentinel / M["REJECT"]).unlink()
        reject(lambda: prepare(lost_sentinel), "scheduler reject sentinel")

        invalid_mode = fixture(root / "invalid-mode")
        reject(lambda: execute(invalid_mode, root / "bad", "flash"),
               "verify/apply only")
    print("EXP76_STAGE74_RADIX_LOCALLOCK_REGRESSIONS=12_PASS; KERNEL_BUILT=false; FLASH_READY=false")


if __name__ == "__main__":
    main()
