#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 GitHub Actions / EXP76 Stage55 exact-source regressions / NO FLASH
"""Exercise the two bounded IRQ/rwsem replacements and fail-closed guards."""
from __future__ import annotations

import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT / "tools/exp76-rt-stage55-irq-rwsem.py"),
                   run_name="exp76_stage55_fixture")
prepare, execute = M["prepare"], M["execute"]


def write(root: Path, path: str, text: str) -> Path:
    item = root / path
    item.parent.mkdir(parents=True, exist_ok=True)
    item.write_text(text, encoding="utf-8")
    return item


def fixture(root: Path) -> Path:
    tree = root / "trial"
    (tree / ".git").mkdir(parents=True)
    write(tree, M["TOPOLOGY"], "/* E404 RT rootdomain */\n" + M["IRQ_OLD"])
    write(tree, M["MADVISE"], "/* Oplus vendor swapin */\n" + M["GUARD"] +
          "\t" + M["MADVISE_OLD"] + "\n#endif\n")
    write(tree, M["IRQ_HEADER"],
          "#define IRQ_WORK_HARD_IRQ\tBIT(3)\n"
          "struct irq_work {\n\tatomic_t flags;\n};\n"
          "void init_irq_work(void) {\n\tatomic_set(&work->flags, 0);\n}\n")
    write(tree, M["RWSEM_HEADER"],
          "#ifdef CONFIG_PREEMPT_RT_FULL\n#include <linux/rwsem_rt.h>\n#else\n"
          "static inline int rwsem_is_contended(struct rw_semaphore *sem)\n"
          "{ return 0; }\n#endif\n")
    write(tree, M["RT_RWSEM"],
          "static inline int rwsem_is_contended(struct rw_semaphore *sem)\n"
          "{ return 0; }\n")
    write(tree, "kernel/sched/cpupri.c.rej", "preserved reject\n")
    for i in range(63):
        write(tree, f"pending/{i:02d}.rej", "unresolved\n")
    return tree


def reject(fn, message: str) -> None:
    try:
        fn()
    except ValueError as exc:
        assert message in str(exc), str(exc)
    else:
        raise AssertionError("Expected Stage55 failure: " + message)


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        good = fixture(root / "good")
        initial = {n: (good / n).read_text()
                   for n in (M["TOPOLOGY"], M["MADVISE"])}
        checked = execute(good, root / "verify-report", "verify")
        assert checked["applied"] is False
        assert all((good / n).read_text() == text for n, text in initial.items())
        done = execute(good, root / "apply-report", "apply")
        assert done["applied"] is True and done["remaining_rejected_files"] == 64
        assert done["kernel_built"] is False and done["flash_ready"] is False
        assert (good / M["TOPOLOGY"]).read_text() == initial[M["TOPOLOGY"]].replace(
            M["IRQ_OLD"], M["IRQ_NEW"])
        assert (good / M["MADVISE"]).read_text() == initial[M["MADVISE"]].replace(
            M["MADVISE_OLD"], M["MADVISE_NEW"])
        assert json.loads((root / "apply-report/stage55-status.json").read_text()) == done
        reject(lambda: prepare(good), "RT rootdomain IRQ")

        no_atomic = fixture(root / "no-atomic")
        p = no_atomic / M["IRQ_HEADER"]
        p.write_text(p.read_text().replace("atomic_t flags;", "unsigned long flags;"))
        reject(lambda: prepare(no_atomic), "atomic_t contract")

        no_hard = fixture(root / "no-hard-flag")
        p = no_hard / M["IRQ_HEADER"]
        p.write_text(p.read_text().replace("IRQ_WORK_HARD_IRQ", "IRQ_WORK_OTHER"))
        reject(lambda: prepare(no_hard), "defined flag")

        no_irq = fixture(root / "changed-irq-op")
        p = no_irq / M["TOPOLOGY"]
        p.write_text(p.read_text().replace(M["IRQ_OLD"], "/* changed */"))
        reject(lambda: prepare(no_irq), "RT rootdomain IRQ")

        no_vendor = fixture(root / "changed-vendor")
        p = no_vendor / M["MADVISE"]
        p.write_text(p.read_text().replace(M["MADVISE_OLD"], "/* changed */"))
        reject(lambda: prepare(no_vendor), "Oplus NAND swapin")

        no_guard = fixture(root / "no-guard")
        p = no_guard / M["MADVISE"]
        p.write_text(p.read_text().replace(M["GUARD"], ""))
        reject(lambda: prepare(no_guard), "build guard")

        no_rtsem = fixture(root / "no-rtsem")
        p = no_rtsem / M["RT_RWSEM"]
        p.write_text("/* missing RT rwsem contention helper */\n")
        reject(lambda: prepare(no_rtsem), "RT rwsem contention")

        no_nonrt = fixture(root / "no-nonrt")
        p = no_nonrt / M["RWSEM_HEADER"]
        p.write_text(p.read_text().replace(
            "static inline int rwsem_is_contended(struct rw_semaphore *sem)\n",
            "/* missing */\n"))
        reject(lambda: prepare(no_nonrt), "nonRT rwsem contention")

        lost_reject = fixture(root / "lost-reject")
        (lost_reject / "pending/00.rej").unlink()
        reject(lambda: prepare(lost_reject), "64 unresolved")

        incorrect_tree = fixture(root / "no-git")
        (incorrect_tree / ".git").rmdir()
        reject(lambda: prepare(incorrect_tree), "isolated E404")

        invalid_mode = fixture(root / "bad-mode")
        reject(lambda: execute(invalid_mode, root / "bad", "flash"), "Stage55 mode")
    print("EXP76_STAGE55_IRQ_RWSEM_REGRESSIONS=10_PASS; KERNEL_BUILT=false; FLASH_READY=false")


if __name__ == "__main__":
    main()
