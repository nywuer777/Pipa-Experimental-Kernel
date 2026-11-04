#!/usr/bin/env python3
# Python 3 / Ubuntu Actions / EXP76 Stage61 idle softirq and userfaultfd seqlock fail-closed regressions / NO FLASH
"""Test the bounded RT dispatcher and seqlock ABI fix with source-drift gates."""
from __future__ import annotations
import json
import runpy
import tempfile
from pathlib import Path

M = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "tools/exp76-rt-stage61-smp-uffd.py"),
    run_name="exp76_stage61_fixture")
prepare, execute = M["prepare"], M["execute"]

def write(tree: Path, name: str, body: str) -> Path:
    p = tree / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p

def fixture(base: Path) -> Path:
    tree = base / "trial"
    (tree / ".git").mkdir(parents=True)
    write(tree, M["SMP"],
          "void flush_smp_call_function_from_idle(void)\n{\n"
          + M["SMP_OLD"] + "}\n")
    write(tree, M["SOFTIRQ"],
          "DEFINE_PER_CPU(struct task_struct *, ktimer_softirqd);\n"
          "static void wakeup_softirqd(void)\n{ }\n"
          + M["TIMER_WAKE"])
    write(tree, M["INTERRUPT"],
          M["PUBLIC_ANCHOR"]
          + "static inline struct task_struct *this_cpu_ksoftirqd(void)\n"
          "{ return NULL; }\n")
    write(tree, M["USERFAULT"],
          "/* a refile sequence protected by fault_pending_wqh lock */\n"
          + M["UFFD_OLD"]
          + "write_seqlock(&ctx->refile_seq);\n"
          + "write_sequnlock(&ctx->refile_seq);\n"
          + "read_seqbegin(&ctx->refile_seq);\n"
          + "read_seqretry(&ctx->refile_seq, seq);\n"
          + "seqlock_init(&ctx->refile_seq);\n")
    write(tree, M["REJECT"], "outstanding\n")
    for k in range(63):
        write(tree, f"rejects/left-{k:02d}.rej", "outstanding\n")
    return tree

def must_fail(fn, label: str) -> None:
    try:
        fn()
    except ValueError as e:
        assert label in str(e), str(e)
    else:
        raise AssertionError("Expected Stage61 fail-closed error: " + label)

def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        root = fixture(base / "happy")
        original = {p: (root / p).read_text() for p in
                    (M["SMP"], M["SOFTIRQ"], M["INTERRUPT"], M["USERFAULT"])}
        dry = execute(root, base / "dry", "verify")
        assert dry["applied"] is False
        assert all((root / p).read_text() == t for p,t in original.items())
        result = execute(root, base / "apply", "apply")
        assert result["applied"] is True
        assert result["remaining_rejected_files"] == 64
        assert result["flash_ready"] is False and result["kernel_built"] is False
        assert (root / M["SMP"]).read_text() == original[M["SMP"]].replace(M["SMP_OLD"], M["SMP_NEW"])
        assert (root / M["SOFTIRQ"]).read_text() == original[M["SOFTIRQ"]].replace(M["TIMER_WAKE"], M["SOFTIRQ_NEW"])
        assert (root / M["INTERRUPT"]).read_text() == original[M["INTERRUPT"]].replace(M["PUBLIC_ANCHOR"], M["PUBLIC_NEW"])
        assert (root / M["USERFAULT"]).read_text() == original[M["USERFAULT"]].replace(M["UFFD_OLD"], M["UFFD_NEW"])
        assert json.loads((base / "apply/stage61-status.json").read_text()) == result
        must_fail(lambda: prepare(root), "idle softirq direct dispatch")

        no_soft = fixture(base / "missing-rt")
        p = no_soft / M["SOFTIRQ"]
        p.write_text(p.read_text().replace(M["TIMER_WAKE"], "/* missing RT timer wake */\n"))
        must_fail(lambda: prepare(no_soft), "RT per-CPU timer")

        no_worker = fixture(base / "missing-worker")
        p = no_worker / M["SOFTIRQ"]
        p.write_text(p.read_text().replace("static void wakeup_softirqd(void)\n", "static void missing(void)\n"))
        must_fail(lambda: prepare(no_worker), "regular softirq worker")

        no_smp = fixture(base / "missing-smp")
        p = no_smp / M["SMP"]
        p.write_text(p.read_text().replace(M["SMP_OLD"], "/* changed */\n"))
        must_fail(lambda: prepare(no_smp), "idle softirq direct")

        no_applied = fixture(base / "missing-rt-consumers")
        p = no_applied / M["USERFAULT"]
        p.write_text(p.read_text().replace("write_seqlock(&ctx->refile_seq);", "write_seqcount_begin(&ctx->refile_seq);"))
        must_fail(lambda: prepare(no_applied), "Applied RT userfaultfd")

        no_uffd = fixture(base / "missing-type")
        p = no_uffd / M["USERFAULT"]
        p.write_text(p.read_text().replace(M["UFFD_OLD"], M["UFFD_NEW"]))
        must_fail(lambda: prepare(no_uffd), "racy seqcount declaration")

        no_decl = fixture(base / "missing-public")
        p = no_decl / M["INTERRUPT"]
        p.write_text(p.read_text().replace(M["PUBLIC_ANCHOR"], "/* no public anchor */\n"))
        must_fail(lambda: prepare(no_decl), "public softirq")

        lost_rej = fixture(base / "missing-reject")
        (lost_rej / "rejects/left-00.rej").unlink()
        must_fail(lambda: prepare(lost_rej), "64 outstanding")

        wrong_tree = fixture(base / "missing-git")
        (wrong_tree / ".git").rmdir()
        must_fail(lambda: prepare(wrong_tree), "isolated E404")

        bad_mode = fixture(base / "bad-mode")
        must_fail(lambda: execute(bad_mode, base / "bad", "flash"), "verify or apply")
    print("EXP76_STAGE61_SMP_UFFD_REGRESSIONS=9_PASS; KERNEL_BUILT=false; FLASH_READY=false")

if __name__ == "__main__":
    main()
