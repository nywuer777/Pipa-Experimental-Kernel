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
        assert empty["ipc_subtree_diagnostic"] is None
        assert empty["security_subtree_diagnostic"] is None
        assert empty["net_subtree_diagnostic"] is None
        assert empty["lib_subtree_diagnostic"] is None
        assert empty["crypto_subtree_diagnostic"] is None
        assert empty["drivers_subtree_diagnostic"] is None
        assert empty["compile_h_preflight_diagnostic"] is None
        assert empty["functionfs_rt_swait_status"] is None
        assert empty["block_init_subtrees_diagnostic"] is None
        assert empty["rt_reject_hunk_inventory"] is None
        assert empty["arm64_neon_rt_kconfig_port"] is None
        assert empty["vmlinux_integration_diagnostic"] is None
        assert empty["rwsem_idr_rt_link_repair"] is None
        assert empty["raw_arm64_image_diagnostic"] is None
        assert empty["kasan_raw_spinlock_equivalence"] is None
        assert empty["rt_kconfig_guard_port"] is None
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
        put(
            artifact / "exp76-stage68-report" / "IPC_SUBTREE_DIAGNOSTIC.json", {
                "stage": "EXP76_STAGE68_IPC_SUBTREE_KBUILD_ARCHIVE_NONFLASH",
                "target": "ipc/built-in.a",
                "top_level_directory_scope": "vmlinux-dirs=ipc",
                "prior_kernel_subtree_gate": True,
                "prior_mm_subtree_gate": True,
                "prior_fs_subtree_gate": True,
                "attempted": True,
                "exit_code": 2,
                "timed_out": False,
                "archive_created": False,
                "archive_bytes": 0,
                "archive_magic_hex": "",
                "archive_has_members": False,
                "enabled_ipc_configs": ["CONFIG_SYSVIPC"],
                "compile_semantics": "FAILED",
                "errors_excerpt": ["ipc/msg.c:77: error: fixture-only IPC error"],
                "first_error_context": ["ipc/msg.c:77: error: fixture-only IPC error"],
                "remaining_rejected_files": 64,
                "full_kernel_link_performed": False,
                "kernel_built": False,
                "flash_ready": False,
            },
        )
        put(
            artifact / "exp76-stage69-report" / "SECURITY_SUBTREE_DIAGNOSTIC.json", {
                "stage": "EXP76_STAGE69_SECURITY_SUBTREE_KBUILD_ARCHIVE_NONFLASH",
                "target": "security/built-in.a",
                "top_level_directory_scope": "vmlinux-dirs=security",
                "ipc_compile_semantics": "CONFIG_DISABLED",
                "prior_ipc_subtree_gate": True,
                "attempted": True,
                "exit_code": 2,
                "timed_out": False,
                "archive_created": False,
                "archive_has_members": False,
                "archive_bytes": 0,
                "errors_excerpt": ["security/security.c:29: error: fixture-only security error"],
                "first_error_context": [
                    "security/security.c:29: error: fixture-only security error"
                ],
                "remaining_rejected_files": 64,
                "full_kernel_link_performed": False,
                "kernel_built": False,
                "flash_ready": False,
            },
        )
        put(
            artifact / "exp76-stage72-report" / "NET_SUBTREE_DIAGNOSTIC.json", {
                "stage": "EXP76_STAGE72_NET_SUBTREE_KBUILD_ARCHIVE_NONFLASH",
                "target": "net/built-in.a",
                "top_level_directory_scope": "vmlinux-dirs=net",
                "prior_security_subtree_gate": True,
                "attempted": True,
                "exit_code": 2,
                "timed_out": False,
                "archive_created": False,
                "archive_has_members": False,
                "archive_bytes": 0,
                "archive_inspection_exit_code": None,
                "archive_members_count": 0,
                "archive_members_sample": [],
                "errors_excerpt": ["net/core/dev.c:42: error: fixture-only net error"],
                "first_error_context": ["net/core/dev.c:42: error: fixture-only net error"],
                "remaining_rejected_files": 64,
                "full_kernel_link_performed": False,
                "kernel_built": False,
                "flash_ready": False,
            },
        )
        put(
            artifact / "exp76-stage73-report" / "LIB_SUBTREE_DIAGNOSTIC.json", {
                "stage": "EXP76_STAGE73_LIB_SUBTREE_KBUILD_ARCHIVE_NONFLASH",
                "target": "lib/built-in.a",
                "top_level_directory_scope": "vmlinux-dirs=lib",
                "prior_net_subtree_gate": True,
                "attempted": True,
                "exit_code": 2,
                "timed_out": False,
                "archive_created": False,
                "archive_has_members": False,
                "archive_bytes": 0,
                "archive_inspection_exit_code": None,
                "archive_members_count": 0,
                "archive_members_sample": [],
                "errors_excerpt": ["lib/string.c:42: error: fixture-only lib error"],
                "first_error_context": ["lib/string.c:42: error: fixture-only lib error"],
                "remaining_rejected_files": 64,
                "full_kernel_link_performed": False,
                "kernel_built": False,
                "flash_ready": False,
            },
        )
        put(
            artifact / "exp76-stage75-report" / "CRYPTO_SUBTREE_DIAGNOSTIC.json", {
                "stage": "EXP76_STAGE75_CRYPTO_SUBTREE_KBUILD_ARCHIVE_NONFLASH",
                "target": "crypto/built-in.a",
                "top_level_directory_scope": "vmlinux-dirs=crypto",
                "prior_lib_subtree_gate": True,
                "attempted": True,
                "exit_code": 2,
                "timed_out": False,
                "archive_created": False,
                "archive_has_members": False,
                "archive_bytes": 0,
                "archive_inspection_exit_code": None,
                "archive_members_count": 0,
                "archive_members_sample": [],
                "errors_excerpt": ["crypto/api.c:42: error: fixture-only crypto error"],
                "first_error_context": [
                    "crypto/api.c:42: error: fixture-only crypto error"
                ],
                "remaining_rejected_files": 64,
                "full_kernel_link_performed": False,
                "kernel_built": False,
                "flash_ready": False,
            },
        )
        put(
            artifact / "exp76-stage76-report" / "DRIVERS_SUBTREE_DIAGNOSTIC.json", {
                "stage": "EXP76_STAGE76_DRIVERS_SUBTREE_KBUILD_ARCHIVE_NONFLASH",
                "target": "drivers/built-in.a",
                "top_level_directory_scope": "vmlinux-dirs=drivers",
                "prior_crypto_subtree_gate": True,
                "attempted": True,
                "exit_code": 2,
                "timed_out": False,
                "archive_created": False,
                "archive_has_members": False,
                "archive_bytes": 0,
                "archive_inspection_exit_code": None,
                "archive_members_count": 0,
                "archive_members_sample": [],
                "errors_excerpt": ["drivers/base/core.c:42: error: fixture-only driver error"],
                "first_error_context": [
                    "drivers/base/core.c:42: error: fixture-only driver error"
                ],
                "remaining_rejected_files": 64,
                "full_kernel_link_performed": False,
                "kernel_built": False,
                "flash_ready": False,
            },
        )
        put(
            artifact / "exp76-stage77-report" / "COMPILE_H_PREP_DIAGNOSTIC.json", {
                "stage": "EXP76_STAGE77_KBUILD_COMPILE_H_INIT_VERSION_NONFLASH",
                "target": "init/version.o",
                "generated_header": "include/generated/compile.h",
                "prior_crypto_subtree_gate": True,
                "attempted": True,
                "exit_code": 2,
                "timed_out": False,
                "compile_h_created": False,
                "compile_h_anchors_valid": False,
                "compile_h_macro_issues": ["UTS_MACHINE: missing"],
                "compile_h_macro_names": [],
                "compile_h_uts_machine": None,
                "compile_h_bytes": 0,
                "compile_h_sha256": None,
                "init_version_object_created": False,
                "errors_excerpt": ["init/version.c:42: error: fixture-only version error"],
                "first_error_context": [
                    "init/version.c:42: error: fixture-only version error"
                ],
                "remaining_rejected_files": 64,
                "full_kernel_link_performed": False,
                "kernel_built": False,
                "flash_ready": False,
            },
        )
        put(artifact / "exp76-rt-report" / "stage79" / "stage79-status.json", {
            "stage": "EXP76_STAGE79_FUNCTIONFS_RT_COMPLETION_SWAIT_NONFLASH",
            "target": "drivers/usb/gadget/function/f_fs.c",
            "applied": True,
            "rt_completion_swait_used": True,
            "nonrt_waitqueue_preserved": True,
            "normal_waitqueue_checks_preserved": True,
            "completion_lifecycle_preserved": True,
            "remaining_rejected_files": 64,
            "original_sha256": "a" * 64,
            "patched_sha256": "b" * 64,
            "full_kernel_link_performed": False,
            "kernel_built": False,
            "flash_ready": False,
        })
        put(
            artifact / "exp76-stage81-report" / "BLOCK_INIT_SUBTREES_DIAGNOSTIC.json", {
                "stage": "EXP76_STAGE81_BLOCK_INIT_SCOPED_ARCHIVES_NONFLASH",
                "prior_drivers_subtree_gate": True,
                "prior_compile_h_gate": True,
                "prior_functionfs_rt_gate": True,
                "targets": {
                    "block": {
                        "target": "block/built-in.a",
                        "directory_scope": "vmlinux-dirs=block",
                        "attempted": True,
                        "exit_code": 2,
                        "timed_out": False,
                        "archive_created": False,
                        "archive_bytes": 0,
                        "archive_inspection_exit_code": None,
                        "archive_has_members": False,
                        "archive_members_count": 0,
                        "archive_members_sample": [],
                        "errors_excerpt": ["block/bio.c:2: error: fixture-only"],
                        "first_error_context": ["block/bio.c:2: error: fixture-only"],
                    },
                    "init": {
                        "target": "init/built-in.a",
                        "directory_scope": "vmlinux-dirs=init",
                        "attempted": True,
                        "exit_code": 0,
                        "timed_out": False,
                        "archive_created": True,
                        "archive_bytes": 120,
                        "archive_inspection_exit_code": 0,
                        "archive_has_members": True,
                        "archive_members_count": 8,
                        "archive_members_sample": ["init/version.o"],
                        "errors_excerpt": [],
                        "first_error_context": [],
                    },
                },
                "all_archives_verified": False,
                "remaining_rejected_files": 64,
                "full_kernel_link_performed": False,
                "kernel_built": False,
                "flash_ready": False,
            },
        )
        put(artifact / "exp76-stage82-report" / "RT_REJECT_HUNK_INVENTORY.json", {
            "stage": "EXP76_STAGE82_OUTSTANDING_RT_REJECT_HUNK_INVENTORY_NONFLASH",
            "initial_rejected_path_count": 80,
            "remaining_rejected_files": 64,
            "total_rejected_hunks": 110,
            "total_added_lines": 300,
            "total_removed_lines": 240,
            "remaining_not_in_initial_manifest": [],
            "initial_paths_no_longer_rejected": [
                "include/linux/old-resolved.c",
            ],
            "categories": {
                "locking_scheduler": 17,
                "rcu": 12,
                "architecture": 6,
                "subsystem": 29,
            },
            "unparseable_reject_files": [],
            "missing_source_files": [],
            "priority_order": [
                "kernel/sched/cpupri.c", "kernel/rcu/tree.c"
            ],
            "entries": [
                {
                    "source": "kernel/sched/cpupri.c",
                    "review_category": "locking_scheduler",
                    "review_score": 93,
                    "hunk_count": 3,
                    "reject_sha256": "a" * 64,
                    "parse_issues": [],
                    "hunks": [{
                        "header": "@@ -15,3 +15,4 @@",
                        "change_excerpt": ["-old()", "+rt()", "+new()"],
                    }],
                },
                {
                    "source": "kernel/rcu/tree.c",
                    "review_category": "rcu",
                    "review_score": 86,
                    "hunk_count": 1,
                    "reject_sha256": "b" * 64,
                    "parse_issues": [],
                    "hunks": [{
                        "header": "@@ -200 +200 @@",
                        "change_excerpt": ["-old_rcu()", "+new_rcu()"],
                    }],
                },
            ],
            "resolution_verified": False,
            "source_modified": False,
            "rejects_deleted": False,
            "full_kernel_link_performed": False,
            "kernel_built": False,
            "flash_ready": False,
        })
        put(artifact / "exp76-rt-report" / "stage83" / "stage83-status.json", {
            "stage": "EXP76_STAGE83_ARM64_NEON_CRYPTO_RT_KCONFIG_HUNK_NONFLASH",
            "target": "arch/arm64/crypto/Kconfig",
            "applied": True,
            "rejected_hunks_reviewed": 1,
            "config_dependencies_patched": [
                "CRYPTO_CHACHA20_NEON", "CRYPTO_POLY1305_NEON",
            ],
            "rt_guard": "!PREEMPT_RT_BASE",
            "rejected_hunk_sha256": "a" * 64,
            "nonrt_kernel_mode_neon_preserved": True,
            "unrelated_arm64_crypto_config_preserved": True,
            "reject_audit_file_retained": True,
            "remaining_rejected_files": 64,
            "semantic_backport_review_pending": True,
            "original_source_sha256": "b" * 64,
            "patched_source_sha256": "c" * 64,
            "full_kernel_link_performed": False,
            "kernel_built": False,
            "flash_ready": False,
        })
        put(artifact / "exp76-stage84-report" / "VMLINUX_LINK_DIAGNOSTIC.json", {
            "stage": "EXP76_STAGE84_PINNED_ARM64_VMLINUX_LINK_DIAGNOSTIC_NOFLASH",
            "target": "vmlinux",
            "prior_block_init_archives_gate": True,
            "prior_arm64_crypto_kconfig_gate": True,
            "attempted": True,
            "exit_code": 2,
            "timed_out": False,
            "vmlinux_created": False,
            "vmlinux_bytes": 0,
            "vmlinux_elf_verified": False,
            "first_compiler_linker_errors": [
                "ld.lld: error: undefined symbol: rt_semantics_fixture"
            ],
            "first_failure_context": [
                "ld.lld: error: undefined symbol: rt_semantics_fixture"
            ],
            "remaining_rejected_files": 64,
            "boot_image_generated": False,
            "flash_performed": False,
            "runtime_verified": False,
            "kernel_built": False,
            "flash_ready": False,
        })
        put(artifact / "exp76-rt-report" / "stage85" / "stage85-status.json", {
            "stage": "EXP76_STAGE85_RWSEM_RT_PUBLIC_API_IDR_PRELOAD_END_NONFLASH",
            "applied": True,
            "rt_public_wrapper_count": 9,
            "rt_public_symbols": [
                "down_read", "down_read_killable", "down_read_trylock",
                "down_write", "down_write_killable", "down_write_trylock",
                "up_read", "up_write", "downgrade_write",
            ],
            "files_patched": [
                "kernel/locking/Makefile",
                "kernel/locking/rwsem-rt-api.c",
                "lib/radix-tree.c",
            ],
            "non_rt_vendor_rwsem_not_linked": True,
            "idr_preload_end_uses_local_unlock": True,
            "idr_preload_lock_pair_preserved": True,
            "rt_rwsem_lowlevel_preserved": True,
            "rejected_files_remaining": 64,
            "full_kernel_link_performed": False,
            "kernel_built": False,
            "flash_ready": False,
        })
        put(artifact / "exp76-stage86-report" / "RAW_ARM64_IMAGE_DIAGNOSTIC.json", {
            "stage": "EXP76_STAGE86_RAW_ARM64_IMAGE_AND_RT_SYMBOL_DIAGNOSTIC_NONFLASH",
            "target": "Image",
            "raw_image_path": "arch/arm64/boot/Image",
            "prior_vmlinux_link_proven": True,
            "prior_rt_rwsem_idr_link_proven": True,
            "public_link_symbols_verified": [
                "down_write", "up_write", "down_read", "up_read",
                "idr_preload_end", "down_read_killable", "down_write_trylock",
                "down_read_trylock", "downgrade_write", "down_write_killable",
            ],
            "public_link_symbols_missing": [],
            "all_previous_unresolved_symbols_restored": True,
            "attempted": True,
            "exit_code": 0,
            "timed_out": False,
            "raw_image_created": True,
            "raw_image_bytes": 36718984,
            "raw_arm64_magic_hex": "41524d64",
            "raw_arm64_header_valid": True,
            "raw_image_sha256": "a" * 64,
            "image_artifact_uploaded": False,
            "packaged_boot_image_generated": False,
            "flash_performed": False,
            "remaining_rejected_files": 64,
            "rt_semantic_review_complete": False,
            "runtime_verified": False,
            "kernel_built": False,
            "flash_ready": False,
            "first_compiler_errors": [],
            "first_failure_context": ["OBJCOPY arch/arm64/boot/Image"],
        })
        put(artifact / "exp76-rt-report" / "stage87" / "stage87-status.json", {
            "stage": "EXP76_STAGE87_KASAN_RAW_SPINLOCK_VENDOR_EQUIVALENCE_NONFLASH",
            "target": "mm/kasan/quarantine.c",
            "original_reject_sha256": "0" * 64,
            "vendor_source_sha256": "1" * 64,
            "reviewed_rejected_hunks": 6,
            "reviewed_added_lines": 9,
            "reviewed_removed_lines": 9,
            "all_added_raw_spinlock_lines_present": True,
            "all_obsolete_spinlock_lines_absent": True,
            "vendor_equivalent_hunks": 6,
            "vendor_equivalent_files": 1,
            "source_changed": False,
            "rejects_deleted": False,
            "rejected_files_remaining": 64,
            "semantic_scope": "KASAN quarantine raw-spinlock substitutions only",
            "all_rt_semantics_verified": False,
            "kernel_built": False,
            "flash_ready": False,
        })
        put(artifact / "exp76-rt-report" / "stage88" / "stage88-status.json", {
            "stage": "EXP76_STAGE88_RT_THP_MUTEX_RWSEM_KCONFIG_GUARDS_NONFLASH",
            "applied": True,
            "configs_patched": [
                "TRANSPARENT_HUGEPAGE", "MUTEX_SPIN_ON_OWNER",
                "RWSEM_SPIN_ON_OWNER",
            ],
            "kconfig_files_patched": ["kernel/Kconfig.locks", "mm/Kconfig"],
            "upstream_rejected_hunks_reviewed": 2,
            "upstream_rejected_lines_reviewed": 3,
            "vendor_rwsem_prerequisites_preserved": True,
            "rt_guard": "!PREEMPT_RT_FULL",
            "original_rejects_retained": True,
            "remaining_rejected_files": 64,
            "effective_config_verified": True,
            "effective_config_disabled": [
                "TRANSPARENT_HUGEPAGE", "MUTEX_SPIN_ON_OWNER",
                "RWSEM_SPIN_ON_OWNER",
            ],
            "rt_semantic_review_complete": False,
            "runtime_verified": False,
            "kernel_built": False,
            "flash_ready": False,
        })
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
        ipc = failed["ipc_subtree_diagnostic"]
        assert ipc["target"] == "ipc/built-in.a"
        assert ipc["top_level_directory_scope"] == "vmlinux-dirs=ipc"
        assert ipc["prior_kernel_subtree_gate"] is True
        assert ipc["prior_mm_subtree_gate"] is True
        assert ipc["prior_fs_subtree_gate"] is True
        assert ipc["exit_code"] == 2 and ipc["archive_created"] is False
        assert ipc["errors_excerpt"][0].endswith("fixture-only IPC error")
        assert ipc["kernel_built"] is False and ipc["flash_ready"] is False
        sec = failed["security_subtree_diagnostic"]
        assert sec["target"] == "security/built-in.a"
        assert sec["top_level_directory_scope"] == "vmlinux-dirs=security"
        assert sec["ipc_compile_semantics"] == "CONFIG_DISABLED"
        assert sec["archive_created"] is False
        assert sec["archive_has_members"] is False
        assert sec["exit_code"] == 2
        assert sec["errors_excerpt"][0].endswith("fixture-only security error")
        assert not sec["kernel_built"] and not sec["flash_ready"]
        assert failed["ipc_subtree_diagnostic"]["compile_semantics"] == "FAILED"
        assert failed["ipc_subtree_diagnostic"]["archive_magic_hex"] == ""
        net = failed["net_subtree_diagnostic"]
        assert net["target"] == "net/built-in.a"
        assert net["top_level_directory_scope"] == "vmlinux-dirs=net"
        assert net["prior_security_subtree_gate"] is True
        assert net["archive_created"] is False
        assert net["archive_has_members"] is False
        assert net["archive_inspection_exit_code"] is None
        assert net["archive_members_count"] == 0
        assert net["archive_members_sample"] == []
        assert net["errors_excerpt"][0].endswith("fixture-only net error")
        assert not net["kernel_built"] and not net["flash_ready"]
        lib = failed["lib_subtree_diagnostic"]
        assert lib["target"] == "lib/built-in.a"
        assert lib["top_level_directory_scope"] == "vmlinux-dirs=lib"
        assert lib["prior_net_subtree_gate"] is True
        assert lib["archive_created"] is False
        assert lib["archive_has_members"] is False
        assert lib["archive_inspection_exit_code"] is None
        assert lib["archive_members_count"] == 0
        assert lib["archive_members_sample"] == []
        assert lib["errors_excerpt"][0].endswith("fixture-only lib error")
        assert not lib["kernel_built"] and not lib["flash_ready"]
        crypto = failed["crypto_subtree_diagnostic"]
        assert crypto["target"] == "crypto/built-in.a"
        assert crypto["top_level_directory_scope"] == "vmlinux-dirs=crypto"
        assert crypto["prior_lib_subtree_gate"] is True
        assert crypto["archive_created"] is False
        assert crypto["archive_has_members"] is False
        assert crypto["archive_inspection_exit_code"] is None
        assert crypto["archive_members_count"] == 0
        assert crypto["archive_members_sample"] == []
        assert crypto["errors_excerpt"][0].endswith("fixture-only crypto error")
        assert not crypto["kernel_built"] and not crypto["flash_ready"]
        drivers = failed["drivers_subtree_diagnostic"]
        assert drivers["target"] == "drivers/built-in.a"
        assert drivers["top_level_directory_scope"] == "vmlinux-dirs=drivers"
        assert drivers["prior_crypto_subtree_gate"] is True
        assert drivers["archive_created"] is False
        assert drivers["archive_has_members"] is False
        assert drivers["archive_inspection_exit_code"] is None
        assert drivers["archive_members_count"] == 0
        assert drivers["archive_members_sample"] == []
        assert drivers["errors_excerpt"][0].endswith("fixture-only driver error")
        assert not drivers["kernel_built"] and not drivers["flash_ready"]
        version = failed["compile_h_preflight_diagnostic"]
        assert version["stage"] == "EXP76_STAGE77_KBUILD_COMPILE_H_INIT_VERSION_NONFLASH"
        assert version["target"] == "init/version.o"
        assert version["generated_header"] == "include/generated/compile.h"
        assert version["prior_crypto_subtree_gate"] is True
        assert version["exit_code"] == 2
        assert version["compile_h_created"] is False
        assert version["compile_h_anchors_valid"] is False
        assert version["compile_h_macro_issues"] == ["UTS_MACHINE: missing"]
        assert version["compile_h_macro_names"] == []
        assert version["compile_h_uts_machine"] == ""
        assert version["compile_h_bytes"] == 0
        assert version["init_version_object_created"] is False
        assert version["errors_excerpt"][0].endswith("fixture-only version error")
        assert not version["kernel_built"] and not version["flash_ready"]
        functionfs = failed["functionfs_rt_swait_status"]
        assert functionfs["target"] == "drivers/usb/gadget/function/f_fs.c"
        assert functionfs["applied"] is True
        assert functionfs["rt_completion_swait_used"] is True
        assert functionfs["nonrt_waitqueue_preserved"] is True
        assert functionfs["normal_waitqueue_checks_preserved"] is True
        assert functionfs["completion_lifecycle_preserved"] is True
        assert functionfs["remaining_rejected_files"] == 64
        assert functionfs["original_sha256"] == "a" * 64
        assert functionfs["patched_sha256"] == "b" * 64
        assert not functionfs["kernel_built"] and not functionfs["flash_ready"]
        block_init = failed["block_init_subtrees_diagnostic"]
        assert block_init["stage"] == "EXP76_STAGE81_BLOCK_INIT_SCOPED_ARCHIVES_NONFLASH"
        assert block_init["prior_drivers_subtree_gate"] is True
        assert block_init["prior_compile_h_gate"] is True
        assert block_init["prior_functionfs_rt_gate"] is True
        assert block_init["all_archives_verified"] is False
        assert block_init["targets"]["block"]["exit_code"] == 2
        assert block_init["targets"]["block"]["archive_members_count"] == 0
        assert block_init["targets"]["block"]["errors_excerpt"][0].endswith("fixture-only")
        assert block_init["targets"]["init"]["archive_has_members"] is True
        assert block_init["targets"]["init"]["archive_members_count"] == 8
        assert not block_init["kernel_built"] and not block_init["flash_ready"]
        index = failed["rt_reject_hunk_inventory"]
        assert index["stage"] == "EXP76_STAGE82_OUTSTANDING_RT_REJECT_HUNK_INVENTORY_NONFLASH"
        assert index["initial_rejected_path_count"] == 80
        assert index["remaining_rejected_files"] == 64
        assert index["total_rejected_hunks"] == 110
        assert index["initial_paths_no_longer_rejected_count"] == 1
        assert index["categories"]["locking_scheduler"] == 17
        assert index["priority_sample"][0]["source"] == "kernel/sched/cpupri.c"
        assert index["priority_sample"][0]["hunk_count"] == 3
        assert index["priority_sample"][0]["first_hunk_headers"][0].startswith("@@ -15")
        assert not index["resolution_verified"]
        assert not index["source_modified"] and not index["rejects_deleted"]
        assert not index["kernel_built"] and not index["flash_ready"]
        arm64 = failed["arm64_neon_rt_kconfig_port"]
        assert arm64["stage"] == "EXP76_STAGE83_ARM64_NEON_CRYPTO_RT_KCONFIG_HUNK_NONFLASH"
        assert arm64["target"] == "arch/arm64/crypto/Kconfig"
        assert arm64["applied"] is True
        assert arm64["config_dependencies_patched"] == [
            "CRYPTO_CHACHA20_NEON", "CRYPTO_POLY1305_NEON",
        ]
        assert arm64["rejected_hunks_reviewed"] == 1
        assert arm64["rt_guard"] == "!PREEMPT_RT_BASE"
        assert arm64["reject_audit_file_retained"] is True
        assert arm64["remaining_rejected_files"] == 64
        assert arm64["semantic_backport_review_pending"] is True
        assert not arm64["kernel_built"] and not arm64["flash_ready"]
        link = failed["vmlinux_integration_diagnostic"]
        assert link["stage"] == "EXP76_STAGE84_PINNED_ARM64_VMLINUX_LINK_DIAGNOSTIC_NOFLASH"
        assert link["target"] == "vmlinux"
        assert link["attempted"] is True
        assert link["exit_code"] == 2
        assert link["vmlinux_elf_verified"] is False
        assert "undefined symbol" in link["first_compiler_linker_errors"][0]
        assert link["remaining_rejected_files"] == 64
        assert not link["boot_image_generated"] and not link["flash_performed"]
        assert not link["kernel_built"] and not link["flash_ready"]
        rt_link = failed["rwsem_idr_rt_link_repair"]
        assert rt_link["stage"] == "EXP76_STAGE85_RWSEM_RT_PUBLIC_API_IDR_PRELOAD_END_NONFLASH"
        assert rt_link["applied"] is True
        assert rt_link["rt_public_wrapper_count"] == 9
        assert rt_link["rt_public_symbols"][0] == "down_read"
        assert rt_link["non_rt_vendor_rwsem_not_linked"] is True
        assert rt_link["idr_preload_end_uses_local_unlock"] is True
        assert rt_link["idr_preload_lock_pair_preserved"] is True
        assert rt_link["rt_rwsem_lowlevel_preserved"] is True
        assert rt_link["rejected_files_remaining"] == 64
        assert not rt_link["kernel_built"] and not rt_link["flash_ready"]
        image = failed["raw_arm64_image_diagnostic"]
        assert image["stage"] == "EXP76_STAGE86_RAW_ARM64_IMAGE_AND_RT_SYMBOL_DIAGNOSTIC_NONFLASH"
        assert image["target"] == "Image"
        assert image["raw_image_path"] == "arch/arm64/boot/Image"
        assert image["all_previous_unresolved_symbols_restored"] is True
        assert image["public_link_symbols_verified"][4] == "idr_preload_end"
        assert image["public_link_symbols_missing"] == []
        assert image["exit_code"] == 0 and not image["timed_out"]
        assert image["raw_image_created"] and image["raw_arm64_header_valid"]
        assert image["raw_arm64_magic_hex"] == "41524d64"
        assert image["raw_image_sha256"] == "a" * 64
        assert image["remaining_rejected_files"] == 64
        assert not image["image_artifact_uploaded"]
        assert not image["packaged_boot_image_generated"]
        assert not image["flash_performed"] and not image["flash_ready"]
        assert not image["kernel_built"]
        kasan = failed["kasan_raw_spinlock_equivalence"]
        assert kasan["stage"] == "EXP76_STAGE87_KASAN_RAW_SPINLOCK_VENDOR_EQUIVALENCE_NONFLASH"
        assert kasan["target"] == "mm/kasan/quarantine.c"
        assert kasan["vendor_equivalent_files"] == 1
        assert kasan["vendor_equivalent_hunks"] == 6
        assert kasan["reviewed_added_lines"] == 9
        assert kasan["reviewed_removed_lines"] == 9
        assert kasan["all_added_raw_spinlock_lines_present"]
        assert kasan["all_obsolete_spinlock_lines_absent"]
        assert not kasan["source_changed"] and not kasan["rejects_deleted"]
        assert kasan["rejected_files_remaining"] == 64
        assert not kasan["all_rt_semantics_verified"]
        assert not kasan["flash_ready"]
        rt_kconfig = failed["rt_kconfig_guard_port"]
        assert rt_kconfig["stage"] == "EXP76_STAGE88_RT_THP_MUTEX_RWSEM_KCONFIG_GUARDS_NONFLASH"
        assert rt_kconfig["applied"] is True
        assert rt_kconfig["configs_patched"] == [
            "TRANSPARENT_HUGEPAGE", "MUTEX_SPIN_ON_OWNER",
            "RWSEM_SPIN_ON_OWNER",
        ]
        assert rt_kconfig["kconfig_files_patched"] == [
            "kernel/Kconfig.locks", "mm/Kconfig",
        ]
        assert rt_kconfig["upstream_rejected_hunks_reviewed"] == 2
        assert rt_kconfig["upstream_rejected_lines_reviewed"] == 3
        assert rt_kconfig["vendor_rwsem_prerequisites_preserved"] is True
        assert rt_kconfig["effective_config_verified"] is True
        assert rt_kconfig["effective_config_disabled"] == [
            "TRANSPARENT_HUGEPAGE", "MUTEX_SPIN_ON_OWNER",
            "RWSEM_SPIN_ON_OWNER",
        ]
        assert rt_kconfig["original_rejects_retained"] is True
        assert rt_kconfig["remaining_rejected_files"] == 64
        assert not rt_kconfig["kernel_built"] and not rt_kconfig["flash_ready"]
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
