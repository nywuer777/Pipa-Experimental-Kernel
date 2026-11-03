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
        assert empty["kernel_subtree_diagnostic"] is None
        assert empty["mm_subtree_diagnostic"] is None
        assert empty["fs_subtree_diagnostic"] is None
        assert empty["cross_subsystem_coverage"] is None
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
        put(
            artifact / "exp76-stage46-report" / "OBJECT_COVERAGE_CROSS_SUBSYSTEM.json", {
                "stage": "EXP76_STAGE46_RT_CROSS_SUBSYSTEM_OBJECTS_NONFLASH",
                "baseline_12_objects_compiled": True,
                "objects_attempted": 9,
                "objects_compiled": 8,
                "all_cross_objects_compiled": False,
                "remaining_rejected_files": 64,
                "link_performed": False,
                "targets": {
                    "kernel/irq/manage.o": {
                        "attempted": True, "compiled": False, "exit_code": 2,
                        "errors_excerpt": ["manage.c:9: error: fixture only"],
                    },
                    "kernel/locking/mutex.o": {
                        "attempted": True, "compiled": True, "exit_code": 0,
                        "errors_excerpt": [],
                    },
                },
            },
        )
        put(
            artifact / "exp76-stage50-report" / "KERNEL_SUBTREE_DIAGNOSTIC.json", {
                "stage": "EXP76_STAGE50_KERNEL_SUBTREE_KBUILD_ARCHIVE_NONFLASH",
                "target": "kernel/built-in.a",
                "baseline_22_objects_compiled": True,
                "attempted": True,
                "exit_code": 2,
                "archive_created": False,
                "archive_bytes": 0,
                "errors_excerpt": ["kernel/panic.c:41: error: simulated Kbuild mismatch"],
                "first_error_context": ["panic.c:39", "panic.c:41: error: simulated Kbuild mismatch"],
                "remaining_rejected_files": 64,
                "full_kernel_link_performed": False,
                "kernel_built": False,
                "flash_ready": False,
            },
        )
        put(
            artifact / "exp76-stage66-report" / "MM_SUBTREE_DIAGNOSTIC.json", {
                "stage": "EXP76_STAGE66_MM_SUBTREE_KBUILD_ARCHIVE_NONFLASH",
                "target": "mm/built-in.a",
                "top_level_directory_scope": "vmlinux-dirs=mm",
                "prior_kernel_subtree_gate": True,
                "attempted": True,
                "exit_code": 2,
                "timed_out": False,
                "archive_created": False,
                "archive_bytes": 0,
                "errors_excerpt": ["mm/vmscan.c:42: error: fixture-only MM error"],
                "first_error_context": ["mm/vmscan.c:42: error: fixture-only MM error"],
                "remaining_rejected_files": 64,
                "full_kernel_link_performed": False,
                "kernel_built": False,
                "flash_ready": False,
            },
        )
        put(
            artifact / "exp76-stage67-report" / "FS_SUBTREE_DIAGNOSTIC.json", {
                "stage": "EXP76_STAGE67_FS_SUBTREE_KBUILD_ARCHIVE_NONFLASH",
                "target": "fs/built-in.a",
                "top_level_directory_scope": "vmlinux-dirs=fs",
                "prior_kernel_subtree_gate": True,
                "prior_mm_subtree_gate": True,
                "attempted": True,
                "exit_code": 2,
                "timed_out": False,
                "archive_created": False,
                "archive_bytes": 0,
                "errors_excerpt": ["fs/open.c:11: error: fixture-only FS error"],
                "first_error_context": ["fs/open.c:11: error: fixture-only FS error"],
                "remaining_rejected_files": 64,
                "full_kernel_link_performed": False,
                "kernel_built": False,
                "flash_ready": False,
            },
        )
        put(artifact / "exp76-rt-report" / "stage31" / "stage31-status.json", {
            "stage": "EXP76_STAGE31_E404_RT_FAIR_DL_CLASS_AFFINITY",
            "remaining_rejected_files": 64, "applied": True,
        })
        put(artifact / "exp76-rt-report" / "stage34" / "stage34-status.json", {
            "stage": "EXP76_STAGE34_RT_TIMER_SWORK_REJECTED_HUNK_RESTORED",
            "remaining_rejected_files": 64, "applied": True,
        })
        put(artifact / "exp76-rt-report" / "stage35" / "stage35-status.json", {
            "stage": "EXP76_STAGE35_RT_MIGHT_SLEEP_NO_STATE_CHECK",
            "remaining_rejected_files": 64, "applied": True,
        })
        put(artifact / "exp76-rt-report" / "stage36" / "stage36-status.json", {
            "stage": "EXP76_STAGE36_RT_CPU_PINNING_CONTRACT_INVENTORY",
            "remaining_rejected_files": 64, "applied": None,
        })
        put(artifact / "exp76-rt-report" / "stage38" / "stage38-status.json", {
            "stage": "EXP76_STAGE38_RT_SOFTIRQ_REJECTED_ENTRY_AND_GUARDS",
            "remaining_rejected_files": 64, "applied": True,
        })
        put(artifact / "exp76-rt-report" / "stage40" / "stage40-status.json", {
            "stage": "EXP76_STAGE40_RT_SLEEPING_LOCK_TASK_ABI",
            "remaining_rejected_files": 64, "applied": True,
        })
        put(artifact / "exp76-rt-report" / "stage41" / "stage41-status.json", {
            "stage": "EXP76_STAGE41_RT_MIGRATION_LIFECYCLE_E404",
            "remaining_rejected_files": 64, "applied": True,
            "migration_runtime_semantics_verified": False,
        })
        put(artifact / "exp76-rt-report" / "stage42" / "stage42-status.json", {
            "stage": "EXP76_STAGE42_RT_CPU_HOTPLUG_PIN_DRAIN_ARM64_TLB",
            "remaining_rejected_files": 64, "applied": True,
            "migration_hotplug_runtime_verified": False,
        })
        put(artifact / "exp76-rt-report" / "stage47" / "stage47-status.json", {
            "stage": "EXP76_STAGE47_RCU_PREPROCESSOR_AND_WORKQUEUE_RAW_LOCK",
            "remaining_rejected_files": 64, "applied": True,
            "rcu_postpatch_preprocessor_balanced": True,
            "workqueue_sleeping_pair_ported": True,
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
        assert failed["stages"]["stage34"]["applied"] is True
        assert failed["stages"]["stage34"]["remaining_rejected_files"] == 64
        assert failed["stages"]["stage35"]["applied"] is True
        assert failed["stages"]["stage35"]["remaining_rejected_files"] == 64
        assert failed["stages"]["stage36"]["present"] is True
        assert failed["stages"]["stage36"]["remaining_rejected_files"] == 64
        assert failed["stages"]["stage38"]["applied"] is True
        assert failed["stages"]["stage38"]["remaining_rejected_files"] == 64
        assert failed["stages"]["stage40"]["present"] is True
        assert failed["stages"]["stage40"]["applied"] is True
        assert failed["stages"]["stage40"]["remaining_rejected_files"] == 64
        assert failed["stages"]["stage41"]["present"] is True
        assert failed["stages"]["stage41"]["applied"] is True
        assert failed["stages"]["stage41"]["remaining_rejected_files"] == 64
        assert failed["stages"]["stage42"]["present"] is True
        assert failed["stages"]["stage42"]["applied"] is True
        assert failed["stages"]["stage42"]["remaining_rejected_files"] == 64
        assert failed["stages"]["stage47"]["present"] is True
        assert failed["stages"]["stage47"]["applied"] is True
        assert failed["stages"]["stage47"]["remaining_rejected_files"] == 64
        subtree = failed["kernel_subtree_diagnostic"]
        assert subtree["stage"] == "EXP76_STAGE50_KERNEL_SUBTREE_KBUILD_ARCHIVE_NONFLASH"
        assert subtree["target"] == "kernel/built-in.a"
        assert subtree["baseline_22_objects_compiled"] is True
        assert subtree["attempted"] is True
        assert subtree["exit_code"] == 2
        assert subtree["archive_created"] is False
        assert subtree["remaining_rejected_files"] == 64
        assert "simulated Kbuild mismatch" in subtree["errors_excerpt"][0]
        assert subtree["full_kernel_link_performed"] is False
        assert subtree["kernel_built"] is False
        assert subtree["flash_ready"] is False
        mm = failed["mm_subtree_diagnostic"]
        assert mm["target"] == "mm/built-in.a"
        assert mm["top_level_directory_scope"] == "vmlinux-dirs=mm"
        assert mm["prior_kernel_subtree_gate"] is True
        assert mm["exit_code"] == 2 and mm["archive_created"] is False
        assert mm["errors_excerpt"][0].endswith("fixture-only MM error")
        assert mm["kernel_built"] is False and mm["flash_ready"] is False
        fs = failed["fs_subtree_diagnostic"]
        assert fs["target"] == "fs/built-in.a"
        assert fs["top_level_directory_scope"] == "vmlinux-dirs=fs"
        assert fs["prior_kernel_subtree_gate"] is True
        assert fs["prior_mm_subtree_gate"] is True
        assert fs["exit_code"] == 2 and fs["archive_created"] is False
        assert fs["errors_excerpt"][0].endswith("fixture-only FS error")
        assert fs["kernel_built"] is False and fs["flash_ready"] is False
        assert failed["cross_subsystem_coverage"]["objects_attempted"] == 9
        assert failed["cross_subsystem_coverage"]["objects_compiled"] == 8
        assert failed["cross_subsystem_coverage"]["remaining_rejected_files"] == 64
        assert failed["cross_subsystem_coverage"]["link_performed"] is False
        assert failed["cross_subsystem_coverage"]["targets"]["kernel/irq/manage.o"]["compiled"] is False
        assert failed["cross_subsystem_coverage"]["targets"]["kernel/irq/manage.o"]["errors_excerpt"][0].endswith("fixture only")
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
