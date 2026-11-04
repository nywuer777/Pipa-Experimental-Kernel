#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage23 prepare evidence regression / NO FLASH
"""Synthetic tests for make prepare exit semantics and first-error context."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "exp76-stage23-prepare-gate.py"
HEADERS = ("include/generated/asm-offsets.h", "include/generated/bounds.h", "include/generated/timeconst.h")


def run_case(make_rc: int, present: tuple[bool, bool, bool], log: str, expected: int, first_line: int | None) -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        output, report = root / "out", root / "report"
        output.mkdir()
        for path, exists in zip(HEADERS, present):
            if exists:
                header = output / path
                header.parent.mkdir(parents=True, exist_ok=True)
                header.write_text("#define TEST_HEADER 1\n", encoding="utf-8")
        source = root / "prepare.log"
        source.write_text(log, encoding="utf-8")
        result = subprocess.run([sys.executable, str(SCRIPT), "--output", str(output), "--report", str(report), "--log", str(source), "--make-rc", str(make_rc)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        data = json.loads((report / "PREPARE_GATE.json").read_text())
        assert data["make_exit_code"] == make_rc
        assert data["gate_exit_code"] == expected
        assert data["completed"] == (expected == 0)
        assert data["first_error_line"] == first_line
        assert int((report / "prepare.rc").read_text()) == expected
        assert data["flash_ready"] is False and data["kernel_built"] is False
        assert (report / "prepare.first-error-context.txt").exists()
        if first_line is not None:
            assert "In file included from" in data["first_error_context"]
            assert "error:" in data["first_error_context"]


def main() -> None:
    run_case(0, (True, True, True), "GEN include/generated/asm-offsets.h\n", 0, None)
    run_case(2, (False, True, True), "In file included from foo.c:11:\ninclude/foo.h:43:1: error: bad type\nmake[2]: *** [Kbuild:56] Error 1\n", 2, 2)
    run_case(0, (False, True, True), "make: Leaving directory\n", 97, None)
    run_case(124, (False, False, False), "make: timeout waiting\n", 124, None)
    print("EXP76_STAGE23_PREPARE_GATE_REGRESSION=4_PASS; FLASH_READY=false")


if __name__ == "__main__":
    main()
