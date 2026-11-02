#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage24 CI evidence regression / NO FLASH
"""Verify evidence relay handles missing artifacts, full diagnostics, and run ordering."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "exp76-stage24-collect-ci-evidence.py"
REPO = "nywuer777/Pipa-Experimental-Kernel"
SHA = "13671ebf94653c27b590375daa678dc00bfd3f8d"


def put(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def invoke(artifact: Path, target: Path, run_id: int, conclusion: str) -> dict:
    result = subprocess.run([
        sys.executable, str(TOOL), "--artifact-root", str(artifact),
        "--evidence-root", str(target), "--repo", REPO,
        "--source-sha", SHA, "--run-id", str(run_id),
        "--job-conclusion", conclusion,
    ], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads((target / "ci-evidence" / "runs" / f"{run_id}.json").read_text())


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        artifact = root / "incoming"
        evidence = root / "evidence"
        empty = invoke(artifact, evidence, 120, "failure")
        assert empty["artifact_present"] is False
        assert empty["preparation"] is None
        assert empty["targets"] == {}
        assert empty["job_conclusion"] == "failure"
        assert empty["flash_ready"] is False

        put(artifact / "exp76-stage18-report" / "PREPARE_GATE.json", {
            "make_exit_code": 2, "gate_exit_code": 2, "completed": False,
            "missing_headers": ["include/generated/asm-offsets.h"],
            "errors_excerpt": ["include/linux/swap.h:346:1: error: missing type"],
            "first_error_context": "In file included from mm.h:10:\nerror: missing type",
        })
        put(artifact / "exp76-stage18-report" / "OBJECT_DIAGNOSTIC.json", {
            "targets": {
                "kernel_sched_cpupri.o": {
                    "attempted": False, "exit_code": None, "compiled": False,
                    "skip_reason": "BLOCKED_BY_PREPARE", "errors_excerpt": [],
                },
            },
        })
        put(artifact / "exp76-rt-report" / "stage21" / "stage21-status.json", {
            "stage": "EXP76_RT_STAGE21_E404_RCU_INCLUDE_RESTORED",
            "remaining_rejected_files": 64, "applied": True,
        })
        put(artifact / "exp76-rt-report" / "stage26" / "stage26-status.json", {
            "stage": "EXP76_STAGE26_E404_ARM64_FORK_VALUE_AFFINITY",
            "remaining_rejected_files": 64, "applied": True,
        })
        put(artifact / "exp76-rt-report" / "stage27" / "stage27-status.json", {
            "stage": "EXP76_STAGE27_E404_CORE_AFFINITY_MASK_RECONCILIATION",
            "remaining_rejected_files": 64, "applied": True,
        })
        put(artifact / "exp76-rt-report" / "stage28" / "stage28-status.json", {
            "stage": "EXP76_STAGE28_RT_TASK_STATE_LOCKED_HELPER_RESTORED",
            "remaining_rejected_files": 64, "applied": True,
        })
        put(artifact / "exp76-rt-report" / "stage29" / "stage29-status.json", {
            "stage": "EXP76_STAGE29_E404_RT_MIGRATION_TASK_ABI",
            "remaining_rejected_files": 64,
            "applied": True,
        })
        put(artifact / "exp76-stage30-report" / "OBJECT_COVERAGE.json", {
            "stage": "EXP76_STAGE30_RT_OBJECT_COVERAGE_NONFLASH",
            "baseline_3_objects_compiled": True,
            "objects_attempted": 9,
            "objects_compiled": 3,
            "all_extra_objects_compiled": False,
            "migration_contract": {
                "migrate_disabled_sched_missing_local_definition": True,
                "runtime_migration_contract_verified": False,
            },
            "targets": {
                "kernel/sched/rt.o": {
                    "attempted": True, "compiled": False, "exit_code": 2,
                    "errors_excerpt": ["rt.c:12: error: fixture-only failure"],
                },
            },
        })
        put(artifact / "exp76-rt-report" / "stage31" / "stage31-status.json", {
            "stage": "EXP76_STAGE31_E404_RT_FAIR_DL_CLASS_AFFINITY",
            "remaining_rejected_files": 64, "applied": True,
        })
        failed = invoke(artifact, evidence, 122, "success")
        assert failed["artifact_present"] is True
        assert failed["preparation"]["completed"] is False
        assert failed["targets"]["kernel_sched_cpupri.o"]["attempted"] is False
        assert failed["stages"]["stage21"]["remaining_rejected_files"] == 64
        assert failed["stages"]["stage26"]["applied"] is True
        assert failed["stages"]["stage27"]["remaining_rejected_files"] == 64
        assert failed["stages"]["stage28"]["applied"] is True
        assert failed["stages"]["stage28"]["remaining_rejected_files"] == 64
        assert failed["stages"]["stage29"]["applied"] is True
        assert failed["stages"]["stage29"]["remaining_rejected_files"] == 64
        assert failed["stages"]["stage31"]["applied"] is True
        assert failed["stages"]["stage31"]["remaining_rejected_files"] == 64
        assert failed["extra_object_coverage"]["objects_attempted"] == 9
        assert failed["extra_object_coverage"]["objects_compiled"] == 3
        assert failed["extra_object_coverage"]["targets"]["kernel/sched/rt.o"]["compiled"] is False
        assert failed["extra_object_coverage"]["migration_contract"]["migrate_disabled_sched_missing_local_definition"] is True
        assert failed["run_url"].endswith("/122")
        assert failed["kernel_built"] is False
        latest = evidence / "ci-evidence" / "clang21-latest.json"
        assert json.loads(latest.read_text())["run_id"] == 122

        older = invoke(artifact, evidence, 121, "success")
        assert older["run_id"] == 121
        assert json.loads(latest.read_text())["run_id"] == 122
    print("EXP76_STAGE24_EVIDENCE_TESTS=3_PASS; FLASH_READY=false")


if __name__ == "__main__":
    main()
