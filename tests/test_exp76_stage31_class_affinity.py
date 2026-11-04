#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage31 scheduler class ABI regression / NO FLASH
"""Exercise 12 sourced RT and pre-existing E404 affinity fragments and drift gates."""
from __future__ import annotations

import json
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "exp76-rt-stage31-class-affinity.py"
CODE = runpy.run_path(str(SCRIPT), run_name="exp76_stage31_fixture")
FRAGMENTS = CODE["REPLACEMENTS"]
FIELDS = CODE["BASELINE_FIELDS"]
assert sum(len(v) for v in FRAGMENTS.values()) == 12


def put(root: Path, path: str, content: str) -> None:
    dest = root / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")


def setup(root: Path) -> dict[str, str]:
    put(root, "include/linux/sched.h", FIELDS)
    put(root, "kernel/sched/cpupri.c.rej", "pending\n")
    for n in range(63):
        put(root, f"pending/r{n:02d}.rej", "pending\n")
    original = {}
    for path, pairs in FRAGMENTS.items():
        original[path] = "/* representative RT class source */\n" + "\n".join(
            rt for rt, _ in pairs
        ) + "\n"
        put(root, path, original[path])
    return original


def invoke(root: Path, mode: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--tree", str(root),
         "--report", str(root / "report"), "--mode", mode],
        capture_output=True, text=True,
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        good = base / "good"
        orig = setup(good)
        checked = invoke(good, "verify")
        assert checked.returncode == 0, checked.stderr
        assert all((good / path).read_text() == text for path, text in orig.items())

        applied = invoke(good, "apply")
        assert applied.returncode == 0, applied.stderr
        for path, pairs in FRAGMENTS.items():
            expected = orig[path]
            for rt, vendor in pairs:
                expected = expected.replace(rt, vendor, 1)
            assert (good / path).read_text() == expected
            assert "->cpus_ptr" not in expected
        result = json.loads((good / "report/stage31-status.json").read_text())
        assert result["replaced_fragments"] == 12
        assert result["stage32_fair_numa_affinity_reconciled"] is True
        assert result["stage33_preexisting_vendor_fair_cpus_ptr_reconciled"] is True
        assert result["remaining_rejected_files"] == 64
        assert result["migration_runtime_implemented"] is False
        assert result["kernel_built"] is False and result["flash_ready"] is False

        missing = base / "missing-fragment"
        items = setup(missing)
        name = "kernel/sched/rt.c"
        put(missing, name, items[name].replace(FRAGMENTS[name][0][0], "missing_expression"))
        assert invoke(missing, "apply").returncode != 0
        assert (missing / name).read_text() != (good / name).read_text()

        drift = base / "vendor-abi-drift"
        setup(drift)
        put(drift, "include/linux/sched.h", FIELDS.replace("cpus_allowed;", "cpus_mask;"))
        assert invoke(drift, "apply").returncode != 0

        shortage = base / "missing-reject"
        setup(shortage)
        (shortage / "pending/r00.rej").unlink()
        assert invoke(shortage, "apply").returncode != 0

        duplicate = base / "duplicate-fragment"
        source = setup(duplicate)
        name = "kernel/sched/deadline.c"
        put(duplicate, name, source[name] + "\n" + FRAGMENTS[name][0][0] + "\n")
        assert invoke(duplicate, "apply").returncode != 0

        partial = base / "partial-vendor"
        source = setup(partial)
        name = "kernel/sched/fair.c"
        put(partial, name, source[name] + "\n" + FRAGMENTS[name][0][1] + "\n")
        assert invoke(partial, "apply").returncode != 0

        # Stage32: the Stage31 synthetic fixture had omitted two RT NUMA sites.
        # Both are mandatory and must retain one exact location each.
        numa_missing = base / "numa-missing"
        source = setup(numa_missing)
        name = "kernel/sched/fair.c"
        rt_numa = "cpumask_test_cpu(env->src_cpu, cur->cpus_ptr)"
        assert rt_numa in source[name]
        put(numa_missing, name, source[name].replace(rt_numa, "stale_numa_affinity()"))
        assert invoke(numa_missing, "apply").returncode != 0
        assert (numa_missing / name).read_text() != (good / name).read_text()

        numa_duplicate = base / "numa-duplicate"
        source = setup(numa_duplicate)
        rt_numa2 = "cpumask_test_cpu(cpu, env->p->cpus_ptr)"
        assert rt_numa2 in source[name]
        put(numa_duplicate, name, source[name] + rt_numa2 + "\n")
        assert invoke(numa_duplicate, "apply").returncode != 0

        # Stage33: these snippets originate in the PINNED vendor E404
        # fair.c before the PREEMPT_RT partial patch. They were absent
        # from the Stage31/32 patch-diff-only test fixture.
        vendor_smt = "for_each_cpu_and(cpu, cpu_smt_mask(target), p->cpus_ptr)"
        vendor_comment1 = " * 3) cannot be migrated to this CPU due to cpus_ptr, or"
        vendor_comment2 = " * isn't true due to cpus_ptr constraints and the like."
        for fragment, case in (
            (vendor_smt, "smt"),
            (vendor_comment1, "migration-comment"),
            (vendor_comment2, "imbalance-comment"),
        ):
            source_dir = base / ("vendor-" + case)
            sources = setup(source_dir)
            assert fragment in sources[name], case
            put(source_dir, name, sources[name].replace(fragment, "STALE_VENDOR_FRAGMENT"))
            assert invoke(source_dir, "apply").returncode != 0
            assert (source_dir / name).read_text() == sources[name].replace(fragment, "STALE_VENDOR_FRAGMENT")
    print("EXP76_STAGE33_VENDOR_FAIR_REGRESSIONS=12_PASS; FLASH_READY=false")


if __name__ == "__main__":
    main()
