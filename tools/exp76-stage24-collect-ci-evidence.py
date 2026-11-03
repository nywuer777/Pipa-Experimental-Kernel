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
