#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 GitHub Actions / EXP76 Stage53 LRU and deadline RT regression / NO FLASH
"""Assert bounded LRU helper integration and E404 cpudeadline affinity."""
from __future__ import annotations
import json
import runpy
import tempfile
from pathlib import Path

M = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "tools/exp76-rt-stage53-lru-cpudl.py"),
    run_name="exp76_stage53_fixture")
prepare, execute = M["prepare"], M["execute"]


def fixture(folder: Path) -> Path:
    t = folder / "trial"
    (t / ".git").mkdir(parents=True)
    s = t / M["SWAP"]
    s.parent.mkdir(parents=True)
    s.write_text(
        "/* RT LRU */\n" + M["SMP_HEADER"] + M["RT_HELPER"]
        + "#else\n"
        + "static DEFINE_PER_CPU(struct work_struct, lru_add_drain_work);\n"
        + "static void lru_add_drain_per_cpu(struct work_struct *dummy)\n"
        + "{\n\tlru_add_drain();\n}\n"
        + M["NONRT_HELPER"] + "#endif\n"
        + "void lru_add_drain_all(void)\n"
        + "{\n\tint cpu;\n" + M["OLD_DRAIN"] + "}\n",
        encoding="utf-8")
    c = t / M["CPUDL"]
    c.parent.mkdir(parents=True, exist_ok=True)
    c.write_text(
        "int cpudl_find(struct cpudl *cp, struct task_struct *p,\n"
        "  struct cpumask *later_mask)\n"
        "{\n\t" + M["CPUDL_AND_OLD"] + ";\n\t"
        + M["CPUDL_TEST_OLD"] + ";\n}\n",
        encoding="utf-8")
    rej = t / "kernel/sched"
    rej.mkdir(parents=True, exist_ok=True)
    (rej / "cpupri.c.rej").write_text("pending\n")
    for k in range(63):
        (rej / f"reject-{k:02d}.rej").write_text("pending\n")
    return t


def fail(fn, marker: str) -> None:
    try:
        fn()
    except ValueError as e:
        assert marker in str(e), str(e)
    else:
        raise AssertionError("Expected Stage53 reject: " + marker)


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        good = fixture(root / "good")
        srcs = [good / M["SWAP"], good / M["CPUDL"]]
        before = {p: p.read_text() for p in srcs}
        s = execute(good, root / "verify", "verify")
        assert not s["applied"]
        assert all(p.read_text() == before[p] for p in srcs)
        s = execute(good, root / "apply", "apply")
        assert s["applied"] and s["remaining_rejected_files"] == 64
        assert s["kernel_built"] is False and s["flash_ready"] is False
        assert (good / M["SWAP"]).read_text() == before[srcs[0]].replace(
            M["OLD_DRAIN"], M["NEW_DRAIN"], 1)
        assert (good / M["CPUDL"]).read_text() == before[srcs[1]].replace(
            M["CPUDL_AND_OLD"], M["CPUDL_AND_NEW"], 1).replace(
            M["CPUDL_TEST_OLD"], M["CPUDL_TEST_NEW"], 1)
        assert json.loads((root / "apply/stage53-status.json").read_text()) == s
        fail(lambda: prepare(good), "vendor LRU drain loop")

        missing_rt = fixture(root / "lost-rt-helper")
        p = missing_rt / M["SWAP"]
        p.write_text(p.read_text().replace(M["RT_HELPER"], "/* missing */\n"))
        fail(lambda: prepare(missing_rt), "Pinned RT remote LRU helper")

        missing_nonrt = fixture(root / "lost-nonrt-helper")
        p = missing_nonrt / M["SWAP"]
        p.write_text(p.read_text().replace(M["NONRT_HELPER"], "/* missing */\n"))
        fail(lambda: prepare(missing_nonrt), "Pinned non-RT per-CPU work helper")

        vendor_drift = fixture(root / "vendor-condition-drift")
        p = vendor_drift / M["SWAP"]
        p.write_text(p.read_text().replace("need_activate_page_drain(cpu)",
                                           "need_other_drain(cpu)"))
        fail(lambda: prepare(vendor_drift), "E404 vendor LRU drain loop")

        duplicate = fixture(root / "duplicate-loop")
        p = duplicate / M["SWAP"]
        p.write_text(p.read_text() + "\n" + M["OLD_DRAIN"])
        fail(lambda: prepare(duplicate), "expected exactly one")

        deadline_drift = fixture(root / "deadline-drift")
        p = deadline_drift / M["CPUDL"]
        p.write_text(p.read_text().replace(M["CPUDL_TEST_OLD"], "cpumask_test_cpu(0, NULL)"))
        fail(lambda: prepare(deadline_drift), "best_cpu mask")

        missing_reject = fixture(root / "missing-reject")
        (missing_reject / "kernel/sched/reject-00.rej").unlink()
        fail(lambda: prepare(missing_reject), "64 unresolved RT rejects")

        missing_cpupri = fixture(root / "missing-cpupri")
        (missing_cpupri / "kernel/sched/cpupri.c.rej").unlink()
        (missing_cpupri / "kernel/sched/new.rej").write_text("pending\n")
        fail(lambda: prepare(missing_cpupri), "cpupri.c.rej")

        bad_git = fixture(root / "no-git")
        (bad_git / ".git").rmdir()
        fail(lambda: prepare(bad_git), "isolated E404")

        bad_mode = fixture(root / "wrong-mode")
        fail(lambda: execute(bad_mode, root / "wrong-mode", "flash"),
             "Unsupported Stage53 mode")
    print("EXP76_STAGE53_LRU_CPUDEADLINE_REGRESSIONS=9_PASS; KERNEL_BUILT=false; FLASH_READY=false")


if __name__ == "__main__":
    main()
