#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage23 arm64 prepare evidence gate / NO FLASH
"""Validate E404 make prepare artifacts and retain first compiler-error context.

This is diagnostic-only. A successful make exit without generated offsets
is not counted as preparation success. No kernel image or flash is produced.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REQUIRED = (
    "include/generated/asm-offsets.h",
    "include/generated/bounds.h",
    "include/generated/timeconst.h",
)
COMPILER_ERROR = re.compile(
    r"fatal error:|(?<![a-z])error:|No rule to make target|"
    r"make(?:\[\d+\])?:\s*\*\*\*|\bError\s+[0-9]+\b",
    re.IGNORECASE,
)
COMPILER_ISSUE = re.compile(
    r"fatal error:|(?<![a-z])error:|warning:|undefined reference|"
    r"No rule to make target|\bError\s+[0-9]+\b",
    re.IGNORECASE,
)
MISSING_GENERATED_RC = 97


def evaluate(output: Path, log: str, make_rc: int) -> dict:
    if make_rc < 0 or make_rc > 255:
        raise ValueError("make exit code outside shell range")
    lines = log.splitlines()
    generated = {name: (output / name).is_file() and (output / name).stat().st_size > 0
                 for name in REQUIRED}
    missing = [name for name, ok in generated.items() if not ok]
    gate_rc = make_rc if make_rc != 0 else (MISSING_GENERATED_RC if missing else 0)
    first_index = next((i for i, line in enumerate(lines) if COMPILER_ERROR.search(line)), None)
    if first_index is None:
        context = "\n".join(lines[-20:])
    else:
        context = "\n".join(lines[max(0, first_index - 12):first_index + 9])
    issues = [line for line in lines if COMPILER_ISSUE.search(line)][:50]
    if make_rc == 0 and missing:
        msg = "error: make prepare exited zero without required generated headers: " + ", ".join(missing)
        issues.insert(0, msg)
        context = msg + ("\n" + context if context else "")
    if make_rc != 0 and not issues:
        issues = ["error: make prepare failed, no recognized compiler diagnostic; inspect prepare.log"]
    return {
        "stage": "EXP76_STAGE23_ARM64_PREPARE_GATE",
        "target": "prepare",
        "make_exit_code": make_rc,
        "gate_exit_code": gate_rc,
        "completed": gate_rc == 0,
        "generated_headers": generated,
        "missing_headers": missing,
        "first_error_line": first_index + 1 if first_index is not None else None,
        "errors_excerpt": issues,
        "first_error_context": context,
        "kernel_built": False,
        "flash_ready": False,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--log", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--make-rc", type=int, required=True)
    args = p.parse_args()
    if not args.log.is_file() or not args.output.is_dir():
        raise ValueError("Missing captured make prepare log or output directory")
    report = args.report.resolve()
    report.mkdir(parents=True, exist_ok=True)
    status = evaluate(args.output.resolve(), args.log.read_text(encoding="utf-8", errors="replace"), args.make_rc)
    (report / "prepare.rc").write_text(str(status["gate_exit_code"]) + "\n", encoding="utf-8")
    (report / "prepare-make.rc").write_text(str(status["make_exit_code"]) + "\n", encoding="utf-8")
    (report / "prepare.errors.txt").write_text("\n".join(status["errors_excerpt"]) + "\n", encoding="utf-8")
    (report / "prepare.first-error-context.txt").write_text(status["first_error_context"] + "\n", encoding="utf-8")
    (report / "PREPARE_GATE.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: status[k] for k in ("stage", "make_exit_code", "gate_exit_code", "completed", "missing_headers", "first_error_line", "flash_ready")}, indent=2))


if __name__ == "__main__":
    main()
