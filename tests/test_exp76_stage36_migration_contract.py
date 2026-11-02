#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage36 RT migration contract regression / NO FLASH
"""Exercise exact upstream conditional cardinalities and refuse fake pin counters."""
from __future__ import annotations

import json
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/exp76-stage36-migration-contract.py"
MOD = runpy.run_path(str(TOOL), run_name="exp76_stage36_fixture")
CORE_REJECT_MARKERS = MOD["REQUIRED_REJECT_MARKERS"]


def put(root: Path, path: str, data: str) -> None:
    dest = root / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(data, encoding="utf-8")


def setup(root: Path) -> None:
    reject = "diff a/kernel/sched/core.c b/kernel/sched/core.c (rejected hunks)\n"
    for marker in CORE_REJECT_MARKERS:
        count = 3 if "migrate_disabled_sched" in marker else (
            2 if marker in ("+void migrate_disable(void)", "+void migrate_enable(void)")
            else 1
        )
        reject += (marker + "\n") * count
    put(root, "kernel/sched/core.c.rej", reject)
    put(root, "kernel/sched/sched.h.rej", MOD["PINNED_RQ_FIELD"] + "\n")
    put(root, "kernel/sched/cpupri.c.rej", "pending\n")
    for n in range(61):
        put(root, f"pending/r{n:02d}.rej", "pending\n")

    put(root, "kernel/sched/core.c",
        "static void migrate_disabled_sched(struct task_struct *p);\n"
        "int __migrate_disabled(struct task_struct *p)\n"
        "{\n\treturn p->migrate_disable;\n}\n")
    put(root, "kernel/sched/sched.h", "struct rq { unsigned int nr_running; };\n")
    put(root, "kernel/cpu.c",
        "if (cpu_nr_pinned(cpu)) return -EAGAIN;\n"
        "nr_pinned = cpu_nr_pinned(cpu);\n")
    put(root, "include/linux/sched.h",
        "cpumask_t\t\t\tcpus_allowed;\n"
        "cpumask_t\t\t\tcpus_requested;\n"
        "int\t\t\t\tmigrate_disable;\n"
        "bool\t\t\t\tmigrate_disable_scheduled;\n")
    put(root, "include/linux/preempt.h",
        "extern void migrate_disable(void);\n"
        "extern void migrate_enable(void);\n"
        "int __migrate_disabled(struct task_struct *p);\n"
        "extern void migrate_disable(void);\n"
        "extern void migrate_enable(void);\n")


def call(root: Path, mode: str = "audit") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), "--tree", str(root),
         "--report", str(root / "report"), "--mode", mode],
        capture_output=True, text=True,
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        good = base / "good"
        setup(good)
        preview = call(good, "verify")
        assert preview.returncode == 0, preview.stderr
        assert not (good / "report/stage36-status.json").exists()
        passed = call(good)
        assert passed.returncode == 0, passed.stderr
        report = json.loads((good / "report/stage36-status.json").read_text())
        assert report["read_only_kernel_tree"] is True
        assert report["cpu_hotplug_calls_cpu_nr_pinned"] == 2
        assert report["core_migrate_disable_and_enable_implemented"] is False
        assert report["core_cpu_nr_pinned_implemented"] is False
        assert report["runqueue_nr_pinned_field_implemented"] is False
        assert report["cross_file_runtime_contract_complete"] is False
        # Stage37: the manifest must report the number of .rej files,
        # not the number of declarations in the final preempt.h loop.
        assert len(list(good.rglob("*.rej"))) == 64
        assert report["remaining_rejected_files"] == len(list(good.rglob("*.rej")))
        assert len(report["blockers"]) == 7
        assert report["kernel_built"] is False and report["flash_ready"] is False

        removed = base / "missing-rejected-counter"
        setup(removed)
        p = removed / "kernel/sched/core.c.rej"
        p.write_text(p.read_text().replace(
            "+\t\tthis_rq()->nr_pinned++;\n", ""))
        assert call(removed).returncode != 0
        assert not (removed / "report/stage36-status.json").exists()

        fake = base / "fake-nr-pinned"
        setup(fake)
        p = fake / "kernel/sched/core.c"
        p.write_text(p.read_text() + "\nint cpu_nr_pinned(int cpu) { return 0; }\n")
        assert call(fake).returncode != 0

        incomplete = base / "untracked-rq"
        setup(incomplete)
        p = incomplete / "kernel/sched/sched.h"
        p.write_text(p.read_text() + "\nint nr_pinned;\n")
        assert call(incomplete).returncode != 0

        vendor_abi = base / "mask-drift"
        setup(vendor_abi)
        p = vendor_abi / "include/linux/sched.h"
        p.write_text(p.read_text().replace("cpus_allowed;", "cpus_ptr;"))
        assert call(vendor_abi).returncode != 0

        no_hotplug = base / "missing-cpu-consumer"
        setup(no_hotplug)
        p = no_hotplug / "kernel/cpu.c"
        p.write_text(p.read_text().replace("nr_pinned = cpu_nr_pinned(cpu);", "nr_pinned = 0;"))
        assert call(no_hotplug).returncode != 0

        preempt_drift = base / "preempt-declarations"
        setup(preempt_drift)
        p = preempt_drift / "include/linux/preempt.h"
        p.write_text(p.read_text() + "int __migrate_disabled(struct task_struct *p);\n")
        result = call(preempt_drift)
        assert result.returncode != 0
        assert "expected 1" in result.stderr
        assert not (preempt_drift / "report/stage36-status.json").exists()

        no_reject = base / "reject-count"
        setup(no_reject)
        (no_reject / "pending/r00.rej").unlink()
        assert call(no_reject).returncode != 0
    print("EXP76_STAGE37_RT_MIGRATION_CONTRACT=8_PASS; REJECTS=64; FLASH_READY=false")


if __name__ == "__main__":
    main()
