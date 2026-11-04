#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage62 OF cache RT regression tests / NO FLASH
"""Verify exact OF source rewrite, no-op verify and fail-closed drift checks."""
from __future__ import annotations

import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT / "tools/exp76-rt-stage62-phandle-cache.py"),
                   run_name="exp76_stage62_regression")
prepare, execute = M["prepare"], M["execute"]


def put(root: Path, name: str, contents: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")
    return path


def fixture(root: Path) -> Path:
    tree = root / "trial"
    (tree / ".git").mkdir(parents=True)
    put(tree, M["FILE"], (
        "/* E404+RT OF cache */\n"
        "static struct device_node **phandle_cache;\n"
        "static u32 phandle_cache_mask;\n"
        + M["OLD_FREE"] + "\n"
        "void of_populate_phandle_cache(void)\n"
        "{\n"
        "\tunsigned long flags;\n"
        "\tu32 cache_entries;\n"
        "\tstruct device_node *np;\n"
        "\tu32 phandles = 0;\n"
        "\tstruct device_node **shadow;\n\n"
        + M["RT_CALL"]
        + "\n\tfor_each_of_allnodes(np)\n"
        "\t\tif (np->phandle && np->phandle != OF_PHANDLE_ILLEGAL)\n"
        "\t\t\tphandles++;\n\n"
        + M["RT_ALLOC_UNLOCK"]
        + "\tphandle_cache_mask = cache_entries - 1;\n\n"
        + M["RT_ALLOC_RELOCK"]
        + "\tif (!phandle_cache)\n\t\tgoto out;\n\n"
        "\tfor_each_of_allnodes(np)\n"
        "\t\tif (np->phandle && np->phandle != OF_PHANDLE_ILLEGAL)\n"
        "\t\t\tphandle_cache[np->phandle & phandle_cache_mask] = np;\n\n"
        + M["RT_UNLOCK_FREE"] + "}\n"
    ))
    put(tree, M["PENDING"], "preserved RT rejection\n")
    for i in range(63):
        put(tree, f"unresolved/reject-{i:02d}.rej", "preserved RT rejection\n")
    return tree


def should_reject(fn, label: str) -> None:
    try:
        fn()
    except ValueError as exc:
        assert label in str(exc), str(exc)
    else:
        raise AssertionError(f"Missing fail-closed Stage62 rejection: {label}")


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        good = fixture(root / "good")
        source = (good / M["FILE"]).read_text()
        verified = execute(good, root / "verify", "verify")
        assert verified["applied"] is False
        assert (good / M["FILE"]).read_text() == source
        applied = execute(good, root / "apply", "apply")
        assert applied["applied"] is True
        assert applied["outstanding_rt_rejects"] == 64
        assert applied["kernel_built"] is False and applied["flash_ready"] is False
        assert (good / M["FILE"]).read_text() == source.replace(
            M["OLD_FREE"], M["NEW_FREE"])
        assert "kfree(phandle_cache);" not in (good / M["FILE"]).read_text()
        assert json.loads((root / "apply/stage62-status.json").read_text()) == applied
        should_reject(lambda: prepare(good), "unmodified cache release")

        wrong_function = fixture(root / "wrong-function")
        p = wrong_function / M["FILE"]
        p.write_text(p.read_text().replace(
            "static void __of_free_phandle_cache(void)", "static void other_free(void)"))
        should_reject(lambda: prepare(wrong_function), "unmodified cache release")

        missing_shadow = fixture(root / "no-shadow")
        p = missing_shadow / M["FILE"]
        p.write_text(p.read_text().replace(
            "shadow = __of_free_phandle_cache();", "__of_free_phandle_cache();"))
        should_reject(lambda: prepare(missing_shadow), "shadow-cache call")

        missing_free = fixture(root / "no-free")
        p = missing_free / M["FILE"]
        p.write_text(p.read_text().replace("\tkfree(shadow);", "\t/* missing free */"))
        should_reject(lambda: prepare(missing_free), "deferred shadow kfree")

        missing_unlock = fixture(root / "no-unlock")
        p = missing_unlock / M["FILE"]
        p.write_text(p.read_text().replace(
            M["RT_ALLOC_UNLOCK"], "\tif (!phandles)\n\t\tgoto out;\n"))
        should_reject(lambda: prepare(missing_unlock), "unlocked allocation")

        missing_relock = fixture(root / "no-relock")
        p = missing_relock / M["FILE"]
        p.write_text(p.read_text().replace(M["RT_ALLOC_RELOCK"], "/* missing */\n"))
        should_reject(lambda: prepare(missing_relock), "allocation re-lock")

        wrong_node_loop = fixture(root / "no-nodes")
        p = wrong_node_loop / M["FILE"]
        p.write_text(p.read_text().replace(
            "\tfor_each_of_allnodes(np)\n", "\tfor_each_othernode(np)\n"))
        should_reject(lambda: prepare(wrong_node_loop), "both OF phandle")

        missing_ref = fixture(root / "no-ref")
        p = missing_ref / M["FILE"]
        p.write_text(p.read_text().replace("\tof_node_put(phandle_cache[k]);",
                                           "\t/* no reference release */"))
        should_reject(lambda: prepare(missing_ref), "unmodified cache release")

        lost_rej = fixture(root / "lost-reject")
        (lost_rej / "unresolved/reject-00.rej").unlink()
        should_reject(lambda: prepare(lost_rej), "64 outstanding")

        no_git = fixture(root / "no-git")
        (no_git / ".git").rmdir()
        should_reject(lambda: prepare(no_git), "isolated E404")

        unsupported = fixture(root / "wrong-mode")
        should_reject(lambda: execute(unsupported, root / "bad", "flash"),
                      "verify/apply only")
    print("EXP76_STAGE62_OF_PHANDLE_CACHE_REGRESSIONS=10_PASS; KERNEL_BUILT=false; FLASH_READY=false")


if __name__ == "__main__":
    main()
