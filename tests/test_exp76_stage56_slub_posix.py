#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 GitHub Actions / EXP76 Stage56 SLUB+POSIX RT regressions / NO FLASH
"""Verify exact small RT source integrations and reject drift/second apply."""
from __future__ import annotations
import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT / "tools/exp76-rt-stage56-slub-posix.py"),
                   run_name="exp76_stage56_test")
prepare, execute = M["prepare"], M["execute"]


def write(tree: Path, name: str, data: str) -> Path:
    item = tree / name
    item.parent.mkdir(parents=True, exist_ok=True)
    item.write_text(data, encoding="utf-8")
    return item


def fixture(root: Path) -> Path:
    tree = root / "trial"
    (tree / ".git").mkdir(parents=True)
    write(tree, M["SLUB"], "static struct page *allocate_slab(struct kmem_cache *s, gfp_t flags, int node)\n{\n"
          + M["SLUB_OLD"] + "body();\n" + M["SLUB_EXIT"] + "}\n")
    write(tree, M["BUG"], "# define WARN_ON_SMP(x)\tWARN_ON(x)\n"
          "# define WARN_ON_SMP(x)\t({0;})\n"
          + M["WARN_ANCHOR"])
    write(tree, M["TIMER"],
          "#ifdef CONFIG_PREEMPT_RT_BASE\n"
          "WARN_ON_ONCE_NONRT(!irqs_disabled());\n"
          "#endif\n")
    write(tree, M["REJECT"], "pending\n")
    for n in range(63):
        write(tree, f"pending/reject-{n:02d}.rej", "pending\n")
    return tree


def fails(action, fragment: str) -> None:
    try:
        action()
    except ValueError as exc:
        assert fragment in str(exc), str(exc)
    else:
        raise AssertionError("Stage56 unexpectedly accepted " + fragment)


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        tree = fixture(base / "good")
        before = {n: (tree / n).read_text() for n in (M["SLUB"], M["BUG"])}
        a = execute(tree, base / "verify", "verify")
        assert not a["applied"] and all((tree / n).read_text() == s
                                        for n, s in before.items())
        b = execute(tree, base / "apply", "apply")
        assert b["applied"] and b["remaining_rejected_files"] == 64
        assert b["kernel_built"] is False and b["flash_ready"] is False
        assert (tree / M["SLUB"]).read_text() == before[M["SLUB"]].replace(
            M["SLUB_OLD"], M["SLUB_NEW"], 1)
        assert (tree / M["BUG"]).read_text() == before[M["BUG"]].replace(
            M["WARN_ANCHOR"], M["WARN_BLOCK"] + M["WARN_ANCHOR"], 1)
        assert json.loads((base / "apply/stage56-status.json").read_text()) == b
        fails(lambda: prepare(tree), "Partial RT SLUB IRQ entry")

        old_entry = fixture(base / "missing-entry")
        p = old_entry / M["SLUB"]
        p.write_text(p.read_text().replace(M["SLUB_OLD"], "/* absent */\n"))
        fails(lambda: prepare(old_entry), "Partial RT SLUB IRQ entry")

        old_exit = fixture(base / "missing-exit")
        p = old_exit / M["SLUB"]
        p.write_text(p.read_text().replace(M["SLUB_EXIT"], "/* absent */\n"))
        fails(lambda: prepare(old_exit), "Applied RT SLUB IRQ exit")

        duplicate = fixture(base / "duplicate-entry")
        p = duplicate / M["SLUB"]
        p.write_text(p.read_text() + M["SLUB_OLD"])
        fails(lambda: prepare(duplicate), "exactly one pinned")

        missing_bug = fixture(base / "missing-warn-anchor")
        p = missing_bug / M["BUG"]
        p.write_text(p.read_text().replace(M["WARN_ANCHOR"], "/* absent */\n"))
        fails(lambda: prepare(missing_bug), "warning macro insertion")

        no_warn = fixture(base / "already-defined")
        p = no_warn / M["BUG"]
        p.write_text(p.read_text() + "#define WARN_ON_ONCE_NONRT(x) (x)\n")
        fails(lambda: prepare(no_warn), "already defined")

        no_consumer = fixture(base / "missing-posix-consumer")
        p = no_consumer / M["TIMER"]
        p.write_text(p.read_text().replace("WARN_ON_ONCE_NONRT(!irqs_disabled());",
                                            "WARN_ON_ONCE(!irqs_disabled());"))
        fails(lambda: prepare(no_consumer), "timer warning consumer missing")

        no_reject = fixture(base / "reject-lost")
        (no_reject / "pending/reject-00.rej").unlink()
        fails(lambda: prepare(no_reject), "64 unresolved")

        no_git = fixture(base / "no-git")
        (no_git / ".git").rmdir()
        fails(lambda: prepare(no_git), "isolated E404")

        invalid_mode = fixture(base / "wrong-mode")
        fails(lambda: execute(invalid_mode, base / "bad", "flash"), "Stage56 mode")
    print("EXP76_STAGE56_SLUB_POSIX_REGRESSIONS=10_PASS; KERNEL_BUILT=false; FLASH_READY=false")


if __name__ == "__main__":
    main()
