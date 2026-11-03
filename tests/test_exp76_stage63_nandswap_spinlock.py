#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage63 nandswap RT spinlock regression / NO FLASH
"""Stage63 verifies a single vendor ABI repair and fails closed on drift."""
from __future__ import annotations

import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT / "tools/exp76-rt-stage63-nandswap-spinlock.py"),
                   run_name="exp76_stage63_fixture")
prepare, execute = M["prepare"], M["execute"]


def write(root: Path, path: str, contents: str) -> Path:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(contents, encoding="utf-8")
    return target


def fixture(root: Path) -> Path:
    tree = root / "trial"
    (tree / ".git").mkdir(parents=True)
    write(tree, M["FILE"], (
        "/* E404 vendor nandswap baseline */\n"
        "static inline struct ns_task_struct *ns_task_insert(pid_t pid, int type)\n"
        "{\n"
        "\tstruct ns_task_struct *ntask = NULL;\n\n"
        "\tntask = kzalloc(sizeof(struct ns_task_struct),\n"
        "\t\t\t\tGFP_KERNEL);\n"
        "\tif (!ntask)\n\t\tgoto out;\n\n"
        + M["OLD"]
        + "\tntask->timeout = jiffies;\n"
        "\tntask->retry = 0;\n"
        "\tkref_init(&ntask->kref);\n\n"
        "\tspin_lock(&ns_tree_lock);\n"
        "\tradix_tree_insert(&ns_tree, pid, ntask);\n"
        "\tspin_unlock(&ns_tree_lock);\n\n"
        "out:\n\treturn ntask;\n}\n"
    ))
    write(tree, M["PENDING"], "pending\n")
    for i in range(63):
        write(tree, f"pending/reject-{i:02d}.rej", "pending\n")
    return tree


def reject(fn, message: str) -> None:
    try:
        fn()
    except ValueError as exc:
        assert message in str(exc), str(exc)
    else:
        raise AssertionError("Expected fail-closed rejection: " + message)


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        good = fixture(root / "good")
        before = (good / M["FILE"]).read_text()
        verified = execute(good, root / "verify", "verify")
        assert not verified["applied"]
        assert (good / M["FILE"]).read_text() == before
        applied = execute(good, root / "apply", "apply")
        assert applied["applied"]
        assert (good / M["FILE"]).read_text() == before.replace(M["OLD"], M["NEW"])
        assert applied["outstanding_rt_rejects"] == 64
        assert not applied["kernel_built"] and not applied["flash_ready"]
        assert json.loads((root / "apply/stage63-status.json").read_text()) == applied
        reject(lambda: prepare(good), "Unmodified vendor")

        no_function = fixture(root / "function-drift")
        p = no_function / M["FILE"]
        p.write_text(p.read_text().replace("ns_task_insert(pid_t", "ns_task_other(pid_t"))
        reject(lambda: prepare(no_function), "E404 ns_task_insert")

        wrong_initializer = fixture(root / "initializer-drift")
        p = wrong_initializer / M["FILE"]
        p.write_text(p.read_text().replace("__SPIN_LOCK_UNLOCKED(lock)", "0"))
        reject(lambda: prepare(wrong_initializer), "Unmodified vendor")

        duplicate = fixture(root / "duplicate")
        p = duplicate / M["FILE"]
        p.write_text(p.read_text() + M["OLD"])
        reject(lambda: prepare(duplicate), "Unmodified vendor")

        no_alloc = fixture(root / "no-allocation")
        p = no_alloc / M["FILE"]
        p.write_text(p.read_text().replace("ntask = kzalloc", "ntask = kmalloc"))
        reject(lambda: prepare(no_alloc), "Heap allocation")

        no_guard = fixture(root / "no-guard")
        p = no_guard / M["FILE"]
        p.write_text(p.read_text().replace("if (!ntask)", "if (ntask)"))
        reject(lambda: prepare(no_guard), "Allocation failure guard")

        no_reject = fixture(root / "reject-drift")
        (no_reject / "pending/reject-00.rej").unlink()
        reject(lambda: prepare(no_reject), "64 outstanding")

        no_git = fixture(root / "no-git")
        (no_git / ".git").rmdir()
        reject(lambda: prepare(no_git), "isolated E404")

        wrong_mode = fixture(root / "mode")
        reject(lambda: execute(wrong_mode, root / "invalid", "flash"),
               "verify/apply only")
    print("EXP76_STAGE63_NANDSWAP_SPINLOCK_REGRESSIONS=10_PASS; KERNEL_BUILT=false; FLASH_READY=false")


if __name__ == "__main__":
    main()
