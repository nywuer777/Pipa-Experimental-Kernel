#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 GitHub Actions / EXP76 Stage59 kthread/proc ABI regressions / NO FLASH
"""Check exact worker RT spinlock operation pairing and E404 /proc affinity."""
from __future__ import annotations

import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT / "tools/exp76-rt-stage59-kthread-proc.py"),
                   run_name="stage59_fixture")
prepare, execute = M["prepare"], M["execute"]


def put(t: Path, path: str, src: str) -> Path:
    p = t / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(src, encoding="utf-8")
    return p


def fixture(base: Path) -> Path:
    tree = base / "trial"
    (tree / ".git").mkdir(parents=True)
    put(tree, M["KTHREAD_HEADER"],
        "struct kthread_worker {\n\traw_spinlock_t\t\tlock;\n};\n"
        ".lock = __RAW_SPIN_LOCK_UNLOCKED((worker).lock)\n")
    put(tree, M["SCHED"], "struct task_struct {\n"
        "\tcpumask_t\t\t\tcpus_allowed;\n};\n")
    worker = (
        M["WORKER_PREFIX"]
        + "{\nrepeat:\n\tif (kthread_should_stop()) {\n"
        + M["STOP_OLD"] + "\t\treturn 0;\n\t}\n"
        + M["PICK_OLD"]
        + "\t\twork = list_first_entry(&worker->work_list, struct kthread_work, node);\n"
        + "\t}\n" + M["PICK_UNLOCK_OLD"]
        + "\treturn 0;\n}\n"
    )
    put(tree, M["KTHREAD"],
        "void init(void) {\n\traw_spin_lock_init(&worker->lock);\n}\n"
        + worker + M["WORKER_END"]
        + "void flush(void) {\n\traw_spin_lock_irq(&worker->lock);\n"
        + "\traw_spin_unlock_irq(&worker->lock);\n}\n")
    proc = (
        M["PROC_START"] + "{\n"
        + '\tseq_printf(m, "Cpus_allowed:\\t%*pb\\n",\n'
        + "\t\t   " + M["PROC_OLD"] + ");\n"
        + '\tseq_printf(m, "Cpus_allowed_list:\\t%*pbl\\n",\n'
        + "\t\t   " + M["PROC_OLD"] + ");\n"
        + "}\n\n" + M["PROC_END"] + "\n"
    )
    put(tree, M["PROC"], proc)
    put(tree, "kernel/sched/cpupri.c.rej", "pending\n")
    for k in range(63):
        put(tree, f"unresolved/r-{k:02d}.rej", "pending\n")
    return tree


def reject(fn, expected: str) -> None:
    try:
        fn()
    except ValueError as exc:
        assert expected in str(exc), str(exc)
    else:
        raise AssertionError("Expected Stage59 rejection: " + expected)


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        good = fixture(root / "good")
        originals = {name: (good / name).read_text()
                     for name in (M["KTHREAD"], M["PROC"])}
        dry = execute(good, root / "dry", "verify")
        assert not dry["applied"]
        assert all((good / name).read_text() == value
                   for name, value in originals.items())
        done = execute(good, root / "applied", "apply")
        assert done["applied"] and done["worker_lock_ops_reconciled"] == 4
        assert done["proc_affinity_mask_references_restored"] == 2
        assert done["remaining_rejected_files"] == 64
        assert done["kernel_built"] is False and done["flash_ready"] is False
        assert (good / M["KTHREAD"]).read_text().count(
            "raw_spin_lock_irq(&worker->lock)") == 3
        assert (good / M["KTHREAD"]).read_text().count(
            "raw_spin_unlock_irq(&worker->lock)") == 3
        assert M["PROC_OLD"] not in (good / M["PROC"]).read_text()
        assert (good / M["PROC"]).read_text().count(M["PROC_NEW"]) == 2
        assert json.loads((root / "applied/stage59-status.json").read_text()) == done
        reject(lambda: prepare(good), "Already-applied RT kthread_flush_work caller")

        bad_type = fixture(root / "bad-type")
        p = bad_type / M["KTHREAD_HEADER"]
        p.write_text(p.read_text().replace("raw_spinlock_t", "spinlock_t"))
        reject(lambda: prepare(bad_type), "raw_spinlock_t")

        bad_static = fixture(root / "bad-initializer")
        p = bad_static / M["KTHREAD_HEADER"]
        p.write_text(p.read_text().replace("__RAW_SPIN_LOCK_UNLOCKED",
                                           "__SPIN_LOCK_UNLOCKED"))
        reject(lambda: prepare(bad_static), "static initializer")

        bad_init = fixture(root / "bad-init")
        p = bad_init / M["KTHREAD"]
        p.write_text(p.read_text().replace("raw_spin_lock_init", "spin_lock_init"))
        reject(lambda: prepare(bad_init), "initialization")

        missing_stop = fixture(root / "bad-stop")
        p = missing_stop / M["KTHREAD"]
        p.write_text(p.read_text().replace(M["STOP_OLD"], "/* missing stop lock */\n"))
        reject(lambda: prepare(missing_stop), "stop lock pair")

        partial = fixture(root / "partial")
        p = partial / M["KTHREAD"]
        p.write_text(p.read_text().replace(
            "\t\tspin_lock_irq(&worker->lock);",
            "\t\traw_spin_lock_irq(&worker->lock);"))
        reject(lambda: prepare(partial), "stop lock pair")

        bad_proc = fixture(root / "bad-proc")
        p = bad_proc / M["PROC"]
        p.write_text(p.read_text().replace(M["PROC_OLD"], M["PROC_NEW"], 1))
        reject(lambda: prepare(bad_proc), "task->cpus_ptr")

        bad_mask = fixture(root / "bad-mask")
        p = bad_mask / M["SCHED"]
        p.write_text(p.read_text().replace("cpus_allowed", "other_mask"))
        reject(lambda: prepare(bad_mask), "task_struct affinity mask")

        lost_reject = fixture(root / "lost-reject")
        (lost_reject / "unresolved/r-00.rej").unlink()
        reject(lambda: prepare(lost_reject), "64 unresolved")

        lost_git = fixture(root / "lost-git")
        (lost_git / ".git").rmdir()
        reject(lambda: prepare(lost_git), "isolated E404")

        bad_mode = fixture(root / "bad-mode")
        reject(lambda: execute(bad_mode, root / "bad", "flash"),
               "Unsupported Stage59 mode")
    print("EXP76_STAGE59_KTHREAD_PROC_REGRESSIONS=10_PASS; KERNEL_BUILT=false; FLASH_READY=false")


if __name__ == "__main__":
    main()
