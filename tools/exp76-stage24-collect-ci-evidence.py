#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage24 CI evidence relay / NO FLASH
"""Publish compact diagnostic evidence to an isolated, read-only-to-source branch.

The collector never changes kernel source and writes only bounded JSON summaries.
GitHub Actions runs it in a separate job granted contents:write; the compiler
job retains contents:read. No credentials, raw logs, images, or boot artifacts.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SHA = re.compile(r"^[0-9a-f]{40}$")
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
STAGES = ("stage19", "stage20", "stage21", "stage26", "stage27", "stage28", "stage29", "stage31", "stage34", "stage35", "stage36", "stage38", "stage40", "stage41", "stage42", "stage47")
STAGE_FILENAMES = ("stage19-status.json", "stage20-status.json", "stage21-status.json", "stage26-status.json", "stage27-status.json", "stage28-status.json", "stage29-status.json", "stage31-status.json", "stage34-status.json", "stage35-status.json", "stage36-status.json", "stage38-status.json", "stage40-status.json", "stage41-status.json", "stage42-status.json", "stage47-status.json")


def read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    if path.stat().st_size > 512 * 1024:
        raise ValueError("Unexpected oversized CI JSON: " + str(path))
    value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(value, dict):
        raise ValueError("Expected JSON object: " + str(path))
    return value


def bounded_lines(value: object, count: int = 20) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item)[:360] for item in value[:count]]


def summarize(artifact: Path, *, repo: str, source_sha: str,
              run_id: int, job_conclusion: str) -> dict:
    if not REPO.fullmatch(repo) or not SHA.fullmatch(source_sha):
        raise ValueError("Invalid repository or pinned source SHA")
    if run_id < 1 or job_conclusion not in (
        "success", "failure", "cancelled", "skipped", "timed_out"
    ):
        raise ValueError("Invalid GitHub Actions run metadata")
    report = artifact / "exp76-stage18-report"
    obj = read_json(report / "OBJECT_DIAGNOSTIC.json")
    prep = read_json(report / "PREPARE_GATE.json")
    stages = {}
    for name, filename in zip(STAGES, STAGE_FILENAMES):
        value = read_json(artifact / "exp76-rt-report" / name / filename)
        stages[name] = {
            "present": value is not None,
            "stage": str(value.get("stage", ""))[:120] if value else None,
            "remaining_rejected_files": value.get("remaining_rejected_files") if value else None,
            "applied": value.get("applied") if value else None,
        }
    targets = {}
    if obj is not None:
        for name, value in (obj.get("targets") or {}).items():
            if not isinstance(value, dict):
                continue
            targets[str(name)[:80]] = {
                "attempted": value.get("attempted"),
                "compiled": value.get("compiled") is True,
                "exit_code": value.get("exit_code"),
                "skip_reason": value.get("skip_reason"),
                "errors_excerpt": bounded_lines(value.get("errors_excerpt"), 12),
            }
    coverage = read_json(artifact / "exp76-stage30-report" / "OBJECT_COVERAGE.json")
    extra_objects = None
    if coverage is not None:
        entries = {}
        for name, value in (coverage.get("targets") or {}).items():
            if not isinstance(value, dict):
                continue
            entries[str(name)[:80]] = {
                "attempted": value.get("attempted"),
                "compiled": value.get("compiled") is True,
                "exit_code": value.get("exit_code"),
                "skip_reason": value.get("skip_reason"),
                "errors_excerpt": bounded_lines(value.get("errors_excerpt"), 12),
            }
        extra_objects = {
            "stage": str(coverage.get("stage") or "")[:120],
            "baseline_3_objects_compiled": coverage.get("baseline_3_objects_compiled") is True,
            "objects_attempted": coverage.get("objects_attempted"),
            "objects_compiled": coverage.get("objects_compiled"),
            "all_extra_objects_compiled": coverage.get("all_extra_objects_compiled") is True,
            "migration_contract": coverage.get("migration_contract"),
            "targets": entries,
        }
    extended = read_json(
        artifact / "exp76-stage46-report" / "OBJECT_COVERAGE_CROSS_SUBSYSTEM.json"
    )
    cross_objects = None
    if extended is not None:
        entries = {}
        for name, value in (extended.get("targets") or {}).items():
            if not isinstance(value, dict):
                continue
            entries[str(name)[:80]] = {
                "attempted": value.get("attempted") is True,
                "compiled": value.get("compiled") is True,
                "exit_code": value.get("exit_code"),
                "skip_reason": value.get("skip_reason"),
                "errors_excerpt": bounded_lines(value.get("errors_excerpt"), 12),
            }
        cross_objects = {
            "stage": str(extended.get("stage") or "")[:120],
            "baseline_12_objects_compiled":
                extended.get("baseline_12_objects_compiled") is True,
            "objects_attempted": extended.get("objects_attempted"),
            "objects_compiled": extended.get("objects_compiled"),
            "all_cross_objects_compiled":
                extended.get("all_cross_objects_compiled") is True,
            "remaining_rejected_files": extended.get("remaining_rejected_files"),
            "link_performed": extended.get("link_performed") is True,
            "targets": entries,
        }
    archive = read_json(
        artifact / "exp76-stage50-report" / "KERNEL_SUBTREE_DIAGNOSTIC.json"
    )
    kernel_subtree = None
    if archive is not None:
        kernel_subtree = {
            "stage": str(archive.get("stage") or "")[:120],
            "target": str(archive.get("target") or "")[:80],
            "baseline_22_objects_compiled":
                archive.get("baseline_22_objects_compiled") is True,
            "attempted": archive.get("attempted") is True,
            "exit_code": archive.get("exit_code"),
            "archive_created": archive.get("archive_created") is True,
            "archive_bytes": archive.get("archive_bytes"),
            "skip_reason": str(archive.get("skip_reason") or "")[:120] or None,
            "errors_excerpt": bounded_lines(archive.get("errors_excerpt"), 25),
            "first_error_context": bounded_lines(
                archive.get("first_error_context"), 24
            ),
            "remaining_rejected_files": archive.get("remaining_rejected_files"),
            "full_kernel_link_performed":
                archive.get("full_kernel_link_performed") is True,
            "kernel_built": False,
            "flash_ready": False,
        }
    mm_archive = read_json(
        artifact / "exp76-stage66-report" / "MM_SUBTREE_DIAGNOSTIC.json"
    )
    mm_subtree = None
    if mm_archive is not None:
        mm_subtree = {
            "stage": str(mm_archive.get("stage") or "")[:120],
            "target": str(mm_archive.get("target") or "")[:80],
            "top_level_directory_scope":
                str(mm_archive.get("top_level_directory_scope") or "")[:80],
            "prior_kernel_subtree_gate":
                mm_archive.get("prior_kernel_subtree_gate") is True,
            "attempted": mm_archive.get("attempted") is True,
            "exit_code": mm_archive.get("exit_code"),
            "timed_out": mm_archive.get("timed_out") is True,
            "archive_created": mm_archive.get("archive_created") is True,
            "archive_bytes": mm_archive.get("archive_bytes"),
            "errors_excerpt": bounded_lines(mm_archive.get("errors_excerpt"), 25),
            "first_error_context": bounded_lines(
                mm_archive.get("first_error_context"), 24
            ),
            "remaining_rejected_files": mm_archive.get("remaining_rejected_files"),
            "full_kernel_link_performed":
                mm_archive.get("full_kernel_link_performed") is True,
            "kernel_built": False,
            "flash_ready": False,
        }
    fs_archive = read_json(
        artifact / "exp76-stage67-report" / "FS_SUBTREE_DIAGNOSTIC.json"
    )
    fs_subtree = None
    if fs_archive is not None:
        fs_subtree = {
            "stage": str(fs_archive.get("stage") or "")[:120],
            "target": str(fs_archive.get("target") or "")[:80],
            "top_level_directory_scope":
                str(fs_archive.get("top_level_directory_scope") or "")[:80],
            "prior_kernel_subtree_gate":
                fs_archive.get("prior_kernel_subtree_gate") is True,
            "prior_mm_subtree_gate":
                fs_archive.get("prior_mm_subtree_gate") is True,
            "attempted": fs_archive.get("attempted") is True,
            "exit_code": fs_archive.get("exit_code"),
            "timed_out": fs_archive.get("timed_out") is True,
            "archive_created": fs_archive.get("archive_created") is True,
            "archive_bytes": fs_archive.get("archive_bytes"),
            "errors_excerpt": bounded_lines(fs_archive.get("errors_excerpt"), 25),
            "first_error_context": bounded_lines(
                fs_archive.get("first_error_context"), 24
            ),
            "remaining_rejected_files": fs_archive.get("remaining_rejected_files"),
            "full_kernel_link_performed":
                fs_archive.get("full_kernel_link_performed") is True,
            "kernel_built": False,
            "flash_ready": False,
        }
    ipc_archive = read_json(
        artifact / "exp76-stage68-report" / "IPC_SUBTREE_DIAGNOSTIC.json"
    )
    ipc_subtree = None
    if ipc_archive is not None:
        ipc_subtree = {
            "stage": str(ipc_archive.get("stage") or "")[:120],
            "target": str(ipc_archive.get("target") or "")[:80],
            "top_level_directory_scope":
                str(ipc_archive.get("top_level_directory_scope") or "")[:80],
            "prior_kernel_subtree_gate":
                ipc_archive.get("prior_kernel_subtree_gate") is True,
            "prior_mm_subtree_gate":
                ipc_archive.get("prior_mm_subtree_gate") is True,
            "prior_fs_subtree_gate":
                ipc_archive.get("prior_fs_subtree_gate") is True,
            "attempted": ipc_archive.get("attempted") is True,
            "exit_code": ipc_archive.get("exit_code"),
            "timed_out": ipc_archive.get("timed_out") is True,
            "archive_created": ipc_archive.get("archive_created") is True,
            "archive_bytes": ipc_archive.get("archive_bytes"),
            "archive_magic_hex": str(ipc_archive.get("archive_magic_hex") or "")[:16],
            "archive_has_members": ipc_archive.get("archive_has_members") is True,
            "enabled_ipc_configs": [
                str(x)[:64] for x in (ipc_archive.get("enabled_ipc_configs") or [])[:8]
            ],
            "compile_semantics": str(ipc_archive.get("compile_semantics") or "")[:80],
            "errors_excerpt": bounded_lines(ipc_archive.get("errors_excerpt"), 25),
            "first_error_context": bounded_lines(
                ipc_archive.get("first_error_context"), 24
            ),
            "remaining_rejected_files": ipc_archive.get("remaining_rejected_files"),
            "full_kernel_link_performed":
                ipc_archive.get("full_kernel_link_performed") is True,
            "kernel_built": False,
            "flash_ready": False,
        }
    security_archive = read_json(
        artifact / "exp76-stage69-report" / "SECURITY_SUBTREE_DIAGNOSTIC.json"
    )
    security_subtree = None
    if security_archive is not None:
        security_subtree = {
            "stage": str(security_archive.get("stage") or "")[:120],
            "target": str(security_archive.get("target") or "")[:80],
            "top_level_directory_scope":
                str(security_archive.get("top_level_directory_scope") or "")[:80],
            "ipc_compile_semantics":
                str(security_archive.get("ipc_compile_semantics") or "")[:80],
            "prior_ipc_subtree_gate":
                security_archive.get("prior_ipc_subtree_gate") is True,
            "attempted": security_archive.get("attempted") is True,
            "exit_code": security_archive.get("exit_code"),
            "timed_out": security_archive.get("timed_out") is True,
            "archive_created": security_archive.get("archive_created") is True,
            "archive_has_members":
                security_archive.get("archive_has_members") is True,
            "archive_bytes": security_archive.get("archive_bytes"),
            "errors_excerpt": bounded_lines(security_archive.get("errors_excerpt"), 25),
            "first_error_context": bounded_lines(
                security_archive.get("first_error_context"), 24
            ),
            "remaining_rejected_files":
                security_archive.get("remaining_rejected_files"),
            "full_kernel_link_performed":
                security_archive.get("full_kernel_link_performed") is True,
            "kernel_built": False,
            "flash_ready": False,
        }
    net_archive = read_json(
        artifact / "exp76-stage72-report" / "NET_SUBTREE_DIAGNOSTIC.json"
    )
    net_subtree = None
    if net_archive is not None:
        net_subtree = {
            "stage": str(net_archive.get("stage") or "")[:120],
            "target": str(net_archive.get("target") or "")[:80],
            "top_level_directory_scope":
                str(net_archive.get("top_level_directory_scope") or "")[:80],
            "prior_security_subtree_gate":
                net_archive.get("prior_security_subtree_gate") is True,
            "attempted": net_archive.get("attempted") is True,
            "exit_code": net_archive.get("exit_code"),
            "timed_out": net_archive.get("timed_out") is True,
            "archive_created": net_archive.get("archive_created") is True,
            "archive_has_members": net_archive.get("archive_has_members") is True,
            "archive_bytes": net_archive.get("archive_bytes"),
            "archive_inspection_exit_code":
                net_archive.get("archive_inspection_exit_code"),
            "archive_members_count": net_archive.get("archive_members_count"),
            "archive_members_sample": [
                str(x)[:150] for x in
                (net_archive.get("archive_members_sample") or [])[:24]
            ],
            "errors_excerpt": bounded_lines(net_archive.get("errors_excerpt"), 25),
            "first_error_context": bounded_lines(
                net_archive.get("first_error_context"), 24
            ),
            "remaining_rejected_files": net_archive.get("remaining_rejected_files"),
            "full_kernel_link_performed":
                net_archive.get("full_kernel_link_performed") is True,
            "kernel_built": False,
            "flash_ready": False,
        }
    lib_archive = read_json(
        artifact / "exp76-stage73-report" / "LIB_SUBTREE_DIAGNOSTIC.json"
    )
    lib_subtree = None
    if lib_archive is not None:
        lib_subtree = {
            "stage": str(lib_archive.get("stage") or "")[:120],
            "target": str(lib_archive.get("target") or "")[:80],
            "top_level_directory_scope":
                str(lib_archive.get("top_level_directory_scope") or "")[:80],
            "prior_net_subtree_gate":
                lib_archive.get("prior_net_subtree_gate") is True,
            "attempted": lib_archive.get("attempted") is True,
            "exit_code": lib_archive.get("exit_code"),
            "timed_out": lib_archive.get("timed_out") is True,
            "archive_created": lib_archive.get("archive_created") is True,
            "archive_has_members": lib_archive.get("archive_has_members") is True,
            "archive_bytes": lib_archive.get("archive_bytes"),
            "archive_inspection_exit_code":
                lib_archive.get("archive_inspection_exit_code"),
            "archive_members_count": lib_archive.get("archive_members_count"),
            "archive_members_sample": [
                str(x)[:150] for x in
                (lib_archive.get("archive_members_sample") or [])[:24]
            ],
            "errors_excerpt": bounded_lines(lib_archive.get("errors_excerpt"), 25),
            "first_error_context": bounded_lines(
                lib_archive.get("first_error_context"), 24
            ),
            "remaining_rejected_files": lib_archive.get("remaining_rejected_files"),
            "full_kernel_link_performed":
                lib_archive.get("full_kernel_link_performed") is True,
            "kernel_built": False,
            "flash_ready": False,
        }
    crypto_archive = read_json(
        artifact / "exp76-stage75-report" / "CRYPTO_SUBTREE_DIAGNOSTIC.json"
    )
    crypto_subtree = None
    if crypto_archive is not None:
        crypto_subtree = {
            "stage": str(crypto_archive.get("stage") or "")[:120],
            "target": str(crypto_archive.get("target") or "")[:80],
            "top_level_directory_scope":
                str(crypto_archive.get("top_level_directory_scope") or "")[:80],
            "prior_lib_subtree_gate":
                crypto_archive.get("prior_lib_subtree_gate") is True,
            "attempted": crypto_archive.get("attempted") is True,
            "exit_code": crypto_archive.get("exit_code"),
            "timed_out": crypto_archive.get("timed_out") is True,
            "archive_created": crypto_archive.get("archive_created") is True,
            "archive_has_members": crypto_archive.get("archive_has_members") is True,
            "archive_bytes": crypto_archive.get("archive_bytes"),
            "archive_inspection_exit_code":
                crypto_archive.get("archive_inspection_exit_code"),
            "archive_members_count": crypto_archive.get("archive_members_count"),
            "archive_members_sample": [
                str(x)[:150] for x in
                (crypto_archive.get("archive_members_sample") or [])[:24]
            ],
            "errors_excerpt":
                bounded_lines(crypto_archive.get("errors_excerpt"), 25),
            "first_error_context": bounded_lines(
                crypto_archive.get("first_error_context"), 24
            ),
            "remaining_rejected_files":
                crypto_archive.get("remaining_rejected_files"),
            "full_kernel_link_performed":
                crypto_archive.get("full_kernel_link_performed") is True,
            "kernel_built": False,
            "flash_ready": False,
        }
    drivers_archive = read_json(
        artifact / "exp76-stage76-report" / "DRIVERS_SUBTREE_DIAGNOSTIC.json"
    )
    drivers_subtree = None
    if drivers_archive is not None:
        drivers_subtree = {
            "stage": str(drivers_archive.get("stage") or "")[:120],
            "target": str(drivers_archive.get("target") or "")[:80],
            "top_level_directory_scope":
                str(drivers_archive.get("top_level_directory_scope") or "")[:80],
            "prior_crypto_subtree_gate":
                drivers_archive.get("prior_crypto_subtree_gate") is True,
            "attempted": drivers_archive.get("attempted") is True,
            "exit_code": drivers_archive.get("exit_code"),
            "timed_out": drivers_archive.get("timed_out") is True,
            "archive_created": drivers_archive.get("archive_created") is True,
            "archive_has_members": drivers_archive.get("archive_has_members") is True,
            "archive_bytes": drivers_archive.get("archive_bytes"),
            "archive_inspection_exit_code":
                drivers_archive.get("archive_inspection_exit_code"),
            "archive_members_count": drivers_archive.get("archive_members_count"),
            "archive_members_sample": [
                str(x)[:150] for x in
                (drivers_archive.get("archive_members_sample") or [])[:24]
            ],
            "errors_excerpt":
                bounded_lines(drivers_archive.get("errors_excerpt"), 25),
            "first_error_context": bounded_lines(
                drivers_archive.get("first_error_context"), 24
            ),
            "remaining_rejected_files":
                drivers_archive.get("remaining_rejected_files"),
            "full_kernel_link_performed":
                drivers_archive.get("full_kernel_link_performed") is True,
            "kernel_built": False,
            "flash_ready": False,
        }
    compile_h = read_json(
        artifact / "exp76-stage77-report" / "COMPILE_H_PREP_DIAGNOSTIC.json"
    )
    stage77_compile_h = None
    if compile_h is not None:
        stage77_compile_h = {
            "stage": str(compile_h.get("stage") or "")[:120],
            "target": str(compile_h.get("target") or "")[:80],
            "generated_header": str(compile_h.get("generated_header") or "")[:100],
            "prior_crypto_subtree_gate":
                compile_h.get("prior_crypto_subtree_gate") is True,
            "attempted": compile_h.get("attempted") is True,
            "exit_code": compile_h.get("exit_code"),
            "timed_out": compile_h.get("timed_out") is True,
            "compile_h_created": compile_h.get("compile_h_created") is True,
            "compile_h_anchors_valid":
                compile_h.get("compile_h_anchors_valid") is True,
            "compile_h_macro_issues": bounded_lines(
                compile_h.get("compile_h_macro_issues"), 12
            ),
            "compile_h_macro_names": [
                str(x)[:40] for x in
                (compile_h.get("compile_h_macro_names") or [])[:12]
            ],
            "compile_h_uts_machine":
                str(compile_h.get("compile_h_uts_machine") or "")[:60],
            "compile_h_bytes": compile_h.get("compile_h_bytes"),
            "compile_h_sha256": str(compile_h.get("compile_h_sha256") or "")[:64],
            "init_version_object_created":
                compile_h.get("init_version_object_created") is True,
            "errors_excerpt": bounded_lines(compile_h.get("errors_excerpt"), 25),
            "first_error_context": bounded_lines(
                compile_h.get("first_error_context"), 24
            ),
            "remaining_rejected_files":
                compile_h.get("remaining_rejected_files"),
            "full_kernel_link_performed":
                compile_h.get("full_kernel_link_performed") is True,
            "kernel_built": False,
            "flash_ready": False,
        }
    functionfs = read_json(
        artifact / "exp76-rt-report" / "stage79" / "stage79-status.json"
    )
    functionfs_rt = None
    if functionfs is not None:
        functionfs_rt = {
            "stage": str(functionfs.get("stage") or "")[:120],
            "target": str(functionfs.get("target") or "")[:160],
            "applied": functionfs.get("applied") is True,
            "rt_completion_swait_used":
                functionfs.get("rt_completion_swait_used") is True,
            "nonrt_waitqueue_preserved":
                functionfs.get("nonrt_waitqueue_preserved") is True,
            "normal_waitqueue_checks_preserved":
                functionfs.get("normal_waitqueue_checks_preserved") is True,
            "completion_lifecycle_preserved":
                functionfs.get("completion_lifecycle_preserved") is True,
            "remaining_rejected_files": functionfs.get("remaining_rejected_files"),
            "original_sha256": str(functionfs.get("original_sha256") or "")[:64],
            "patched_sha256": str(functionfs.get("patched_sha256") or "")[:64],
            "full_kernel_link_performed":
                functionfs.get("full_kernel_link_performed") is True,
            "kernel_built": False,
            "flash_ready": False,
        }
    block_init_raw = read_json(
        artifact / "exp76-stage81-report" / "BLOCK_INIT_SUBTREES_DIAGNOSTIC.json"
    )
    block_init = None
    if block_init_raw is not None:
        block_init_targets = {}
        for name in ("block", "init"):
            obj = (block_init_raw.get("targets") or {}).get(name)
            if not isinstance(obj, dict):
                continue
            block_init_targets[name] = {
                "target": str(obj.get("target") or "")[:100],
                "directory_scope": str(obj.get("directory_scope") or "")[:80],
                "attempted": obj.get("attempted") is True,
                "exit_code": obj.get("exit_code"),
                "timed_out": obj.get("timed_out") is True,
                "archive_created": obj.get("archive_created") is True,
                "archive_bytes": obj.get("archive_bytes"),
                "archive_inspection_exit_code": obj.get("archive_inspection_exit_code"),
                "archive_has_members": obj.get("archive_has_members") is True,
                "archive_members_count": obj.get("archive_members_count"),
                "archive_members_sample": [
                    str(x)[:150] for x in
                    (obj.get("archive_members_sample") or [])[:20]
                ],
                "errors_excerpt": bounded_lines(obj.get("errors_excerpt"), 25),
                "first_error_context": bounded_lines(
                    obj.get("first_error_context"), 24
                ),
            }
        block_init = {
            "stage": str(block_init_raw.get("stage") or "")[:130],
            "prior_drivers_subtree_gate":
                block_init_raw.get("prior_drivers_subtree_gate") is True,
            "prior_compile_h_gate":
                block_init_raw.get("prior_compile_h_gate") is True,
            "prior_functionfs_rt_gate":
                block_init_raw.get("prior_functionfs_rt_gate") is True,
            "targets": block_init_targets,
            "all_archives_verified":
                block_init_raw.get("all_archives_verified") is True,
            "remaining_rejected_files":
                block_init_raw.get("remaining_rejected_files"),
            "full_kernel_link_performed":
                block_init_raw.get("full_kernel_link_performed") is True,
            "kernel_built": False,
            "flash_ready": False,
        }
    reject_index_raw = read_json(
        artifact / "exp76-stage82-report" / "RT_REJECT_HUNK_INVENTORY.json"
    )
    reject_index = None
    if reject_index_raw is not None:
        reject_entries = {
            str(item.get("source") or ""): item
            for item in (reject_index_raw.get("entries") or [])
            if isinstance(item, dict)
        }
        important = []
        for source in (reject_index_raw.get("priority_order") or [])[:24]:
            item = reject_entries.get(str(source))
            if not item:
                continue
            important.append({
                "source": str(source)[:200],
                "review_category": str(item.get("review_category") or "")[:80],
                "review_score": item.get("review_score"),
                "hunk_count": item.get("hunk_count"),
                "reject_sha256": str(item.get("reject_sha256") or "")[:64],
                "parse_issues": bounded_lines(item.get("parse_issues"), 4),
                "first_hunk_headers": [
                    str(h.get("header") or "")[:200]
                    for h in (item.get("hunks") or [])[:3]
                    if isinstance(h, dict)
                ],
                "first_change_excerpt": [
                    str(line)[:160]
                    for h in (item.get("hunks") or [])[:2]
                    if isinstance(h, dict)
                    for line in (h.get("change_excerpt") or [])[:3]
                ][:6],
            })
        reject_index = {
            "stage": str(reject_index_raw.get("stage") or "")[:130],
            "initial_rejected_path_count":
                reject_index_raw.get("initial_rejected_path_count"),
            "remaining_rejected_files":
                reject_index_raw.get("remaining_rejected_files"),
            "total_rejected_hunks": reject_index_raw.get("total_rejected_hunks"),
            "total_added_lines": reject_index_raw.get("total_added_lines"),
            "total_removed_lines": reject_index_raw.get("total_removed_lines"),
            "remaining_not_in_initial_manifest": bounded_lines(
                reject_index_raw.get("remaining_not_in_initial_manifest"), 12
            ),
            "initial_paths_no_longer_rejected_count": len(
                reject_index_raw.get("initial_paths_no_longer_rejected") or []
            ),
            "categories": reject_index_raw.get("categories"),
            "unparseable_reject_files": bounded_lines(
                reject_index_raw.get("unparseable_reject_files"), 12
            ),
            "missing_source_files": bounded_lines(
                reject_index_raw.get("missing_source_files"), 12
            ),
            "priority_sample": important,
            "resolution_verified": False,
            "source_modified": False,
            "rejects_deleted": False,
            "full_kernel_link_performed": False,
            "kernel_built": False,
            "flash_ready": False,
        }
    arm64_neon_status = read_json(
        artifact / "exp76-rt-report" / "stage83" / "stage83-status.json"
    )
    arm64_neon = None
    if arm64_neon_status is not None:
        arm64_neon = {
            "stage": str(arm64_neon_status.get("stage") or "")[:130],
            "target": str(arm64_neon_status.get("target") or "")[:130],
            "applied": arm64_neon_status.get("applied") is True,
            "rejected_hunks_reviewed":
                arm64_neon_status.get("rejected_hunks_reviewed"),
            "config_dependencies_patched": [
                str(x)[:80] for x in
                (arm64_neon_status.get("config_dependencies_patched") or [])[:8]
            ],
            "rt_guard": str(arm64_neon_status.get("rt_guard") or "")[:80],
            "rejected_hunk_sha256":
                str(arm64_neon_status.get("rejected_hunk_sha256") or "")[:64],
            "nonrt_kernel_mode_neon_preserved":
                arm64_neon_status.get("nonrt_kernel_mode_neon_preserved") is True,
            "unrelated_arm64_crypto_config_preserved":
                arm64_neon_status.get("unrelated_arm64_crypto_config_preserved") is True,
            "reject_audit_file_retained":
                arm64_neon_status.get("reject_audit_file_retained") is True,
            "remaining_rejected_files":
                arm64_neon_status.get("remaining_rejected_files"),
            "semantic_backport_review_pending":
                arm64_neon_status.get("semantic_backport_review_pending") is True,
            "original_source_sha256":
                str(arm64_neon_status.get("original_source_sha256") or "")[:64],
            "patched_source_sha256":
                str(arm64_neon_status.get("patched_source_sha256") or "")[:64],
            "full_kernel_link_performed": False,
            "kernel_built": False,
            "flash_ready": False,
        }
    linked_raw = read_json(
        artifact / "exp76-stage84-report" / "VMLINUX_LINK_DIAGNOSTIC.json"
    )
    link = None
    if linked_raw is not None:
        link = {
            "stage": str(linked_raw.get("stage") or "")[:140],
            "target": str(linked_raw.get("target") or "")[:80],
            "prior_block_init_archives_gate":
                linked_raw.get("prior_block_init_archives_gate") is True,
            "prior_arm64_crypto_kconfig_gate":
                linked_raw.get("prior_arm64_crypto_kconfig_gate") is True,
            "attempted": linked_raw.get("attempted") is True,
            "exit_code": linked_raw.get("exit_code"),
            "timed_out": linked_raw.get("timed_out") is True,
            "vmlinux_created": linked_raw.get("vmlinux_created") is True,
            "vmlinux_bytes": linked_raw.get("vmlinux_bytes"),
            "vmlinux_elf_verified":
                linked_raw.get("vmlinux_elf_verified") is True,
            "first_compiler_linker_errors": bounded_lines(
                linked_raw.get("first_compiler_linker_errors"), 30
            ),
            "first_failure_context": bounded_lines(
                linked_raw.get("first_failure_context"), 36
            ),
            "remaining_rejected_files":
                linked_raw.get("remaining_rejected_files"),
            "boot_image_generated":
                linked_raw.get("boot_image_generated") is True,
            "flash_performed": linked_raw.get("flash_performed") is True,
            "runtime_verified": False,
            "kernel_built": False,
            "flash_ready": False,
        }
    rt_link_apis_raw = read_json(
        artifact / "exp76-rt-report" / "stage85" / "stage85-status.json"
    )
    rt_link_apis = None
    if rt_link_apis_raw is not None:
        rt_link_apis = {
            "stage": str(rt_link_apis_raw.get("stage") or "")[:140],
            "applied": rt_link_apis_raw.get("applied") is True,
            "rt_public_wrapper_count":
                rt_link_apis_raw.get("rt_public_wrapper_count"),
            "rt_public_symbols": [
                str(x)[:70] for x in
                (rt_link_apis_raw.get("rt_public_symbols") or [])[:20]
            ],
            "files_patched": [
                str(x)[:160] for x in
                (rt_link_apis_raw.get("files_patched") or [])[:8]
            ],
            "non_rt_vendor_rwsem_not_linked":
                rt_link_apis_raw.get("non_rt_vendor_rwsem_not_linked") is True,
            "idr_preload_end_uses_local_unlock":
                rt_link_apis_raw.get("idr_preload_end_uses_local_unlock") is True,
            "idr_preload_lock_pair_preserved":
                rt_link_apis_raw.get("idr_preload_lock_pair_preserved") is True,
            "rt_rwsem_lowlevel_preserved":
                rt_link_apis_raw.get("rt_rwsem_lowlevel_preserved") is True,
            "rejected_files_remaining":
                rt_link_apis_raw.get("rejected_files_remaining"),
            "full_kernel_link_performed": False,
            "kernel_built": False,
            "flash_ready": False,
        }
    raw_image_raw = read_json(
        artifact / "exp76-stage86-report" / "RAW_ARM64_IMAGE_DIAGNOSTIC.json"
    )
    raw_image = None
    if raw_image_raw is not None:
        raw_image = {
            "stage": str(raw_image_raw.get("stage") or "")[:140],
            "target": str(raw_image_raw.get("target") or "")[:60],
            "raw_image_path": str(raw_image_raw.get("raw_image_path") or "")[:120],
            "prior_vmlinux_link_proven":
                raw_image_raw.get("prior_vmlinux_link_proven") is True,
            "prior_rt_rwsem_idr_link_proven":
                raw_image_raw.get("prior_rt_rwsem_idr_link_proven") is True,
            "public_link_symbols_verified": [
                str(x)[:80] for x in
                (raw_image_raw.get("public_link_symbols_verified") or [])[:16]
            ],
            "public_link_symbols_missing": [
                str(x)[:80] for x in
                (raw_image_raw.get("public_link_symbols_missing") or [])[:16]
            ],
            "all_previous_unresolved_symbols_restored":
                raw_image_raw.get("all_previous_unresolved_symbols_restored") is True,
            "attempted": raw_image_raw.get("attempted") is True,
            "exit_code": raw_image_raw.get("exit_code"),
            "timed_out": raw_image_raw.get("timed_out") is True,
            "raw_image_created": raw_image_raw.get("raw_image_created") is True,
            "raw_image_bytes": raw_image_raw.get("raw_image_bytes"),
            "raw_arm64_magic_hex":
                str(raw_image_raw.get("raw_arm64_magic_hex") or "")[:8],
            "raw_arm64_header_valid":
                raw_image_raw.get("raw_arm64_header_valid") is True,
            "raw_image_sha256":
                str(raw_image_raw.get("raw_image_sha256") or "")[:64],
            "image_artifact_uploaded": False,
            "packaged_boot_image_generated": False,
            "flash_performed": False,
            "remaining_rejected_files":
                raw_image_raw.get("remaining_rejected_files"),
            "rt_semantic_review_complete": False,
            "runtime_verified": False,
            "kernel_built": False,
            "flash_ready": False,
            "first_compiler_errors": bounded_lines(
                raw_image_raw.get("first_compiler_errors"), 20
            ),
            "first_failure_context": bounded_lines(
                raw_image_raw.get("first_failure_context"), 24
            ),
        }
    kasan_raw = read_json(
        artifact / "exp76-rt-report" / "stage87" / "stage87-status.json"
    )
    kasan = None
    if kasan_raw is not None:
        kasan = {
            "stage": str(kasan_raw.get("stage") or "")[:140],
            "target": str(kasan_raw.get("target") or "")[:160],
            "original_reject_sha256":
                str(kasan_raw.get("original_reject_sha256") or "")[:64],
            "vendor_source_sha256":
                str(kasan_raw.get("vendor_source_sha256") or "")[:64],
            "reviewed_rejected_hunks":
                kasan_raw.get("reviewed_rejected_hunks"),
            "reviewed_added_lines": kasan_raw.get("reviewed_added_lines"),
            "reviewed_removed_lines": kasan_raw.get("reviewed_removed_lines"),
            "all_added_raw_spinlock_lines_present":
                kasan_raw.get("all_added_raw_spinlock_lines_present") is True,
            "all_obsolete_spinlock_lines_absent":
                kasan_raw.get("all_obsolete_spinlock_lines_absent") is True,
            "vendor_equivalent_hunks": kasan_raw.get("vendor_equivalent_hunks"),
            "vendor_equivalent_files": kasan_raw.get("vendor_equivalent_files"),
            "source_changed": kasan_raw.get("source_changed") is True,
            "rejects_deleted": kasan_raw.get("rejects_deleted") is True,
            "rejected_files_remaining": kasan_raw.get("rejected_files_remaining"),
            "semantic_scope": str(kasan_raw.get("semantic_scope") or "")[:140],
            "all_rt_semantics_verified": False,
            "kernel_built": False,
            "flash_ready": False,
        }
    kconfig_raw = read_json(
        artifact / "exp76-rt-report" / "stage88" / "stage88-status.json"
    )
    rt_kconfig = None
    if kconfig_raw is not None:
        rt_kconfig = {
            "stage": str(kconfig_raw.get("stage") or "")[:140],
            "applied": kconfig_raw.get("applied") is True,
            "configs_patched": [
                str(x)[:80] for x in
                (kconfig_raw.get("configs_patched") or [])[:8]
            ],
            "kconfig_files_patched": [
                str(x)[:140] for x in
                (kconfig_raw.get("kconfig_files_patched") or [])[:8]
            ],
            "upstream_rejected_hunks_reviewed":
                kconfig_raw.get("upstream_rejected_hunks_reviewed"),
            "upstream_rejected_lines_reviewed":
                kconfig_raw.get("upstream_rejected_lines_reviewed"),
            "vendor_rwsem_prerequisites_preserved":
                kconfig_raw.get("vendor_rwsem_prerequisites_preserved") is True,
            "rt_guard": str(kconfig_raw.get("rt_guard") or "")[:64],
            "original_rejects_retained":
                kconfig_raw.get("original_rejects_retained") is True,
            "remaining_rejected_files":
                kconfig_raw.get("remaining_rejected_files"),
            "effective_config_verified":
                kconfig_raw.get("effective_config_verified") is True,
            "effective_config_disabled": [
                str(x)[:80] for x in
                (kconfig_raw.get("effective_config_disabled") or [])[:8]
            ],
            "rt_semantic_review_complete": False,
            "runtime_verified": False,
            "kernel_built": False,
            "flash_ready": False,
        }
    proc_swait_raw = read_json(
        artifact / "exp76-rt-report" / "stage89" / "stage89-status.json"
    )
    proc_swait = None
    if proc_swait_raw is not None:
        proc_swait = {
            "stage": str(proc_swait_raw.get("stage") or "")[:140],
            "target": str(proc_swait_raw.get("target") or "")[:160],
            "applied": proc_swait_raw.get("applied") is True,
            "source_original_sha256":
                str(proc_swait_raw.get("source_original_sha256") or "")[:64],
            "source_patched_sha256":
                str(proc_swait_raw.get("source_patched_sha256") or "")[:64],
            "rejected_hunk_sha256":
                str(proc_swait_raw.get("rejected_hunk_sha256") or "")[:64],
            "upstream_hunks_reviewed":
                proc_swait_raw.get("upstream_hunks_reviewed"),
            "upstream_includes_added":
                proc_swait_raw.get("upstream_includes_added"),
            "vendor_e404_code_preserved":
                proc_swait_raw.get("vendor_e404_code_preserved") is True,
            "rt_swait_api_present":
                proc_swait_raw.get("rt_swait_api_present") is True,
            "original_reject_retained":
                proc_swait_raw.get("original_reject_retained") is True,
            "remaining_rejected_files":
                proc_swait_raw.get("remaining_rejected_files"),
            "scheduler_semantic_review_complete": False,
            "full_kernel_link_rechecked": False,
            "runtime_verified": False,
            "kernel_built": False,
            "flash_ready": False,
        }
    rt_uts_raw = read_json(
        artifact / "exp76-rt-report" / "stage90" / "stage90-status.json"
    )
    rt_uts = None
    if rt_uts_raw is not None:
        rt_uts = {
            "stage": str(rt_uts_raw.get("stage") or "")[:140],
            "applied": rt_uts_raw.get("applied") is True,
            "paths": [
                str(x)[:120] for x in (rt_uts_raw.get("paths") or [])[:8]
            ],
            "upstream_reject_hunks_reviewed":
                rt_uts_raw.get("upstream_reject_hunks_reviewed"),
            "vendor_cc_version_and_ld_abi_preserved":
                rt_uts_raw.get("vendor_cc_version_and_ld_abi_preserved") is True,
            "rt_uts_version_marker":
                str(rt_uts_raw.get("rt_uts_version_marker") or "")[:32],
            "effective_uts_version_verified":
                rt_uts_raw.get("effective_uts_version_verified") is True,
            "generated_uts_version":
                str(rt_uts_raw.get("generated_uts_version") or "")[:96],
            "generated_compiler_metadata_present":
                rt_uts_raw.get("generated_compiler_metadata_present") is True,
            "uts_release_modified": rt_uts_raw.get("uts_release_modified") is True,
            "kernel_sys_uname_modified":
                rt_uts_raw.get("kernel_sys_uname_modified") is True,
            "original_rejects_retained":
                rt_uts_raw.get("original_rejects_retained") is True,
            "remaining_rejected_files":
                rt_uts_raw.get("remaining_rejected_files"),
            "runtime_verified": False,
            "kernel_built": False,
            "flash_ready": False,
        }
    pid_atomic_raw = read_json(
        artifact / "exp76-rt-report" / "stage91" / "stage91-status.json"
    )
    pid_atomic = None
    if pid_atomic_raw is not None:
        pid_atomic = {
            "stage": str(pid_atomic_raw.get("stage") or "")[:140],
            "target": str(pid_atomic_raw.get("target") or "")[:160],
            "dependency": str(pid_atomic_raw.get("dependency") or "")[:100],
            "applied": pid_atomic_raw.get("applied") is True,
            "pinned_reject_sha256":
                str(pid_atomic_raw.get("pinned_reject_sha256") or "")[:64],
            "original_source_sha256":
                str(pid_atomic_raw.get("original_source_sha256") or "")[:64],
            "patched_source_sha256":
                str(pid_atomic_raw.get("patched_source_sha256") or "")[:64],
            "rejected_hunks_reviewed":
                pid_atomic_raw.get("rejected_hunks_reviewed"),
            "header_dependencies_added":
                pid_atomic_raw.get("header_dependencies_added"),
            "pid_atomic_api_usage_preserved":
                pid_atomic_raw.get("pid_atomic_api_usage_preserved") is True,
            "vendor_pidfd_abi_preserved":
                pid_atomic_raw.get("vendor_pidfd_abi_preserved") is True,
            "original_reject_retained":
                pid_atomic_raw.get("original_reject_retained") is True,
            "remaining_rejected_files":
                pid_atomic_raw.get("remaining_rejected_files"),
            "source_change_only_include":
                pid_atomic_raw.get("source_change_only_include") is True,
            "scheduler_runtime_review_complete": False,
            "kernel_built": False,
            "flash_ready": False,
        }
    preparation = None
    if prep is not None:
        preparation = {
            "make_exit_code": prep.get("make_exit_code"),
            "gate_exit_code": prep.get("gate_exit_code"),
            "completed": prep.get("completed") is True,
            "missing_headers": bounded_lines(prep.get("missing_headers"), 10),
            "errors_excerpt": bounded_lines(prep.get("errors_excerpt"), 18),
            "first_error_context": str(prep.get("first_error_context") or "")[:4800],
        }
    # Older results (pre-Stage23) remain distinguishable from missing results.
    elif obj is not None and isinstance(obj.get("preparation"), dict):
        preparation = obj["preparation"]
    status_path = report / "status.txt"
    status = status_path.read_text(errors="replace").strip()[:350] if status_path.is_file() else None
    return {
        "schema": "EXP76_STAGE24_EVIDENCE_V1",
        "repository": repo,
        "source_sha": source_sha,
        "run_id": run_id,
        "run_url": f"https://github.com/{repo}/actions/runs/{run_id}",
        "job_conclusion": job_conclusion,
        "status": status,
        "artifact_present": artifact.is_dir() and (obj is not None or prep is not None),
        "preparation": preparation,
        "targets": targets,
        "extra_object_coverage": extra_objects,
        "cross_subsystem_coverage": cross_objects,
        "kernel_subtree_diagnostic": kernel_subtree,
        "mm_subtree_diagnostic": mm_subtree,
        "fs_subtree_diagnostic": fs_subtree,
        "ipc_subtree_diagnostic": ipc_subtree,
        "security_subtree_diagnostic": security_subtree,
        "net_subtree_diagnostic": net_subtree,
        "lib_subtree_diagnostic": lib_subtree,
        "crypto_subtree_diagnostic": crypto_subtree,
        "drivers_subtree_diagnostic": drivers_subtree,
        "compile_h_preflight_diagnostic": stage77_compile_h,
        "functionfs_rt_swait_status": functionfs_rt,
        "block_init_subtrees_diagnostic": block_init,
        "rt_reject_hunk_inventory": reject_index,
        "arm64_neon_rt_kconfig_port": arm64_neon,
        "vmlinux_integration_diagnostic": link,
        "rwsem_idr_rt_link_repair": rt_link_apis,
        "raw_arm64_image_diagnostic": raw_image,
        "kasan_raw_spinlock_equivalence": kasan,
        "rt_kconfig_guard_port": rt_kconfig,
        "proc_swait_rt_include_port": proc_swait,
        "rt_uts_version_generator_port": rt_uts,
        "pid_atomic_rt_header_port": pid_atomic,
        "stages": stages,
        "kernel_built": False,
        "flash_ready": False,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--artifact-root", required=True, type=Path)
    p.add_argument("--evidence-root", required=True, type=Path)
    p.add_argument("--repo", required=True)
    p.add_argument("--source-sha", required=True)
    p.add_argument("--run-id", required=True, type=int)
    p.add_argument("--job-conclusion", required=True)
    a = p.parse_args()
    result = summarize(a.artifact_root, repo=a.repo, source_sha=a.source_sha,
                       run_id=a.run_id, job_conclusion=a.job_conclusion)
    root = a.evidence_root.resolve() / "ci-evidence"
    history = root / "runs"
    history.mkdir(parents=True, exist_ok=True)
    run_file = history / f"{a.run_id}.json"
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if run_file.exists() and run_file.read_text() != rendered:
        raise ValueError("CI run ID already exists with different evidence")
    run_file.write_text(rendered, encoding="utf-8")
    latest = root / "clang21-latest.json"
    last = read_json(latest)
    if last is None or a.run_id >= int(last["run_id"]):
        latest.write_text(rendered, encoding="utf-8")
    print(json.dumps({
        "run_id": a.run_id, "job_conclusion": a.job_conclusion,
        "artifact_present": result["artifact_present"],
        "prepare_completed": (result["preparation"] or {}).get("completed"),
        "targets_seen": list(result["targets"]),
        "flash_ready": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
