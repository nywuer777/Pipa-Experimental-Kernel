#!/usr/bin/env python3
# Python 3 + host C compiler / GitHub Actions Ubuntu / E404 scheduler feature smoke test
"""Compile-test the Stage15 feature header under three simulated Kconfig states.

Tests C preprocessor macro expansion only; does not compile a Linux kernel.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

CASES = (
    ("non_rt", [], 0),
    ("rt_without_lazy", ["-DCONFIG_PREEMPT_RT_FULL=1"], 0),
    ("rt_with_lazy", ["-DCONFIG_PREEMPT_RT_FULL=1", "-DCONFIG_PREEMPT_LAZY=1"], 1),
)
PROBE = """
#include "kernel/sched/features.h"
#if SCHED_FEAT_TTWU_QUEUE != 0
#error "E404 TTWU_QUEUE changed"
#endif
#if SCHED_FEAT_PREEMPT_LAZY != EXPECTED_LAZY_FEATURE
#error "PREEMPT_LAZY feature incorrect for Kconfig state"
#endif
_Static_assert(SCHED_FEAT_TTWU_QUEUE == 0, "vendor TTWU_QUEUE invariant");
_Static_assert(SCHED_FEAT_PREEMPT_LAZY == EXPECTED_LAZY_FEATURE, "lazy preemption feature");
"""


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    root = args.tree.resolve()
    if not (root / "kernel/sched/features.h").is_file():
        raise SystemExit("Missing E404 scheduler feature header")
    cc = shutil.which("cc")
    if cc is None:
        raise SystemExit("Host cc not installed, fail closed")
    report = args.report.resolve()
    report.mkdir(parents=True, exist_ok=True)
    output = []
    for name, definitions, lazy in CASES:
        command = [
            cc, "-x", "c", "-std=gnu11", "-fsyntax-only", "-Werror",
            "-I", str(root), f"-DEXPECTED_LAZY_FEATURE={lazy}",
            *definitions, "-"
        ]
        run = subprocess.run(
            command, input=PROBE, text=True,
            capture_output=True, check=False
        )
        result = {
            "case": name, "definitions": definitions,
            "expected_lazy": lazy, "compiler_exit": run.returncode,
            "stderr": run.stderr,
        }
        output.append(result)
        if run.returncode != 0:
            (report / "stage15-cc-preflight.json").write_text(
                json.dumps(output, indent=2) + "\n", encoding="utf-8"
            )
            raise SystemExit(f"Stage15 host C preprocessor gate failed: {name}\n{run.stderr}")
    (report / "stage15-cc-preflight.json").write_text(
        json.dumps(output, indent=2) + "\n", encoding="utf-8"
    )
    print("EXP76_STAGE15_HOST_C_FEATURE_TESTS=3_PASS; KERNEL_BUILT=false; FLASH_READY=false")


if __name__ == "__main__":
    main()
