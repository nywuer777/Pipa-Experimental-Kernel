#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage64 ION secure-heap regression / NO FLASH
"""Fail closed on source drift and preserve RT rejects and unrelated ION logic."""
from __future__ import annotations

import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT / "tools/exp76-rt-stage64-ion-spinlock.py"),
                   run_name="exp76_stage64_fixture")
prepare, execute = M["prepare"], M["execute"]


def put(root: Path, path: str, content: str) -> Path:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def fixture(root: Path) -> Path:
    tree = root / "trial"
    (tree / ".git").mkdir(parents=True)
    put(tree, M["FILE"], (
        "/* Pinned E404 ION secure-heap create fixture */\n"
        "struct ion_system_secure_heap {\n"
        "\tspinlock_t work_lock;\n"
        "};\n"
        + M["FUNCTION"]
        + "\tstruct ion_system_secure_heap *heap;\n\n"
        "\theap = kzalloc(sizeof(*heap), GFP_KERNEL);\n"
        "\tif (!heap)\n"
        "\t\treturn ERR_PTR(-ENOMEM);\n"
        "\theap->heap.ops = &system_secure_heap_ops;\n"
        "\theap->sys_heap = get_ion_heap(ION_SYSTEM_HEAP_ID);\n\n"
        + M["OLD"]
        + "\tINIT_DELAYED_WORK(&heap->prefetch_work,\n"
        "\t\t\t  ion_system_secure_heap_prefetch_work);\n"
        "\treturn &heap->heap;\n"
        "}\n"
    ))
    put(tree, M["PENDING"], "rejected RT patch\n")
    for i in range(63):
        put(tree, f"unresolved/reject-{i:02d}.rej", "rejected RT patch\n")
    return tree


def reject(fn, expected: str) -> None:
    try:
        fn()
    except ValueError as exc:
        assert expected in str(exc), str(exc)
    else:
        raise AssertionError("Expected Stage64 rejection: " + expected)


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        good = fixture(root / "good")
        before = (good / M["FILE"]).read_text(encoding="utf-8")
        verified = execute(good, root / "verify", "verify")
        assert not verified["applied"]
        assert (good / M["FILE"]).read_text() == before
        applied = execute(good, root / "apply", "apply")
        assert applied["applied"]
        assert (good / M["FILE"]).read_text() == before.replace(M["OLD"], M["NEW"])
        assert applied["outstanding_rt_rejects"] == 64
        assert applied["dynamic_spinlock_initialized_with_api"]
        assert not applied["kernel_built"] and not applied["flash_ready"]
        assert json.loads((root / "apply/stage64-status.json").read_text()) == applied
        reject(lambda: prepare(good), "static initializer assignment")

        wrong_function = fixture(root / "function-drift")
        p = wrong_function / M["FILE"]
        p.write_text(p.read_text().replace(
            "ion_system_secure_heap_create(", "other_secure_heap_create("))
        reject(lambda: prepare(wrong_function), "secure heap creation function")

        wrong_initializer = fixture(root / "initializer-drift")
        p = wrong_initializer / M["FILE"]
        p.write_text(p.read_text().replace(
            "__SPIN_LOCK_UNLOCKED(heap->work_lock)", "0"))
        reject(lambda: prepare(wrong_initializer), "static initializer assignment")

        duplicate = fixture(root / "duplicate")
        p = duplicate / M["FILE"]
        p.write_text(p.read_text() + M["OLD"])
        reject(lambda: prepare(duplicate), "static initializer assignment")

        missing_alloc = fixture(root / "missing-allocation")
        p = missing_alloc / M["FILE"]
        p.write_text(p.read_text().replace("heap = kzalloc(", "heap = kmalloc("))
        reject(lambda: prepare(missing_alloc), "Dynamic secure heap allocation")

        missing_guard = fixture(root / "missing-guard")
        p = missing_guard / M["FILE"]
        p.write_text(p.read_text().replace("if (!heap)", "if (heap)"))
        reject(lambda: prepare(missing_guard), "Secure heap allocation failure guard")

        missing_work = fixture(root / "missing-work")
        p = missing_work / M["FILE"]
        p.write_text(p.read_text().replace("INIT_DELAYED_WORK(", "INIT_WORK("))
        reject(lambda: prepare(missing_work), "Secure heap delayed work initializer")

        missing_rej = fixture(root / "missing-reject")
        (missing_rej / "unresolved/reject-00.rej").unlink()
        reject(lambda: prepare(missing_rej), "64 outstanding")

        no_git = fixture(root / "no-git")
        (no_git / ".git").rmdir()
        reject(lambda: prepare(no_git), "isolated E404")

        invalid_mode = fixture(root / "mode")
        reject(lambda: execute(invalid_mode, root / "bad", "flash"), "verify/apply only")
    print("EXP76_STAGE64_ION_SPINLOCK_REGRESSIONS=11_PASS; KERNEL_BUILT=false; FLASH_READY=false")


if __name__ == "__main__":
    main()
