#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage15 scheduler feature ABI / E404 checkout
"""Port PREEMPT_LAZY scheduler feature to E404 compile-time SCHED_FEAT_* ABI.

Preserve vendor SCHED_FEAT_TTWU_QUEUE=0 for both RT and non-RT.
This is not a functional PREEMPT_RT build or a flash candidate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

FEATURES = "kernel/sched/features.h"
REJECT_SHA256 = "fd7467a2ddf05a3ded4819726925c260d2ab0faae02121e6b53ed73376e3b164"
ORIGINAL = "#define SCHED_FEAT_TTWU_QUEUE 0\n"
REPLACEMENT = (
    "#define SCHED_FEAT_TTWU_QUEUE 0\n"
    "\n"
    "/* Match resched_curr_lazy()'s CONFIG_PREEMPT_LAZY gate. */\n"
    "#ifdef CONFIG_PREEMPT_LAZY\n"
    "#define SCHED_FEAT_PREEMPT_LAZY 1\n"
    "#else\n"
    "#define SCHED_FEAT_PREEMPT_LAZY 0\n"
    "#endif\n"
)


def analyze(root: Path):
    feature = root / FEATURES
    rejected = root / (FEATURES + ".rej")
    core = root / "kernel/sched/core.c"
    header = root / "kernel/sched/sched.h"
    kconfig = root / "kernel/Kconfig.preempt"
    for file in (feature, rejected, core, header, kconfig):
        if not file.is_file():
            raise ValueError("Missing source/reject dependency: " + str(file))
    actual = hashlib.sha256(rejected.read_bytes()).hexdigest()
    if actual != REJECT_SHA256:
        raise ValueError("Unexpected upstream scheduler feature reject SHA: " + actual)
    rej = rejected.read_text(encoding="utf-8")
    if len(re.findall(r"(?m)^@@ -\d+", rej)) != 1:
        raise ValueError("Expected exactly one PREEMPT_LAZY scheduler feature hunk")
    for token in (
        "+SCHED_FEAT(TTWU_QUEUE, false)",
        "+SCHED_FEAT(PREEMPT_LAZY, true)",
        "+#ifdef CONFIG_PREEMPT_RT_FULL",
        "+# ifdef CONFIG_PREEMPT_LAZY",
        "+SCHED_FEAT(TTWU_QUEUE, true)",
    ):
        if rej.count(token) != 1:
            raise ValueError("Unknown RT scheduler feature reject: " + token)
    before = feature.read_text(encoding="utf-8")
    if before.count(ORIGINAL) != 1:
        raise ValueError("E404 TTWU_QUEUE must have its existing fixed value 0")
    if any(x in before for x in (
        "SCHED_FEAT_PREEMPT_LAZY",
        "SCHED_FEAT(PREEMPT_LAZY",
        "SCHED_FEAT(TTWU_QUEUE",
    )):
        raise ValueError("E404 scheduler feature interface already modified")
    if not re.search(r"(?m)^#define SCHED_FEAT_[A-Z_0-9]+ [01]$", before):
        raise ValueError("Not an E404 compile-time scheduler feature header")
    sched = header.read_text(encoding="utf-8")
    if sched.count("#define sched_feat(x) SCHED_FEAT_##x") != 1:
        raise ValueError("E404 scheduler feature macro ABI has changed")
    core_text = core.read_text(encoding="utf-8")
    match = re.search(
        r"#ifdef CONFIG_PREEMPT_LAZY\s+.*?"
        r"\bvoid resched_curr_lazy\(struct rq \*rq\)\s*\{(?P<body>.*?)\n\}"
        r"\s*#endif",
        core_text, re.DOTALL
    )
    if not match or match.group("body").count("sched_feat(PREEMPT_LAZY)") != 1:
        raise ValueError("Scheduler lazy reschedule function not gated as expected")
    if "if (!sched_feat(PREEMPT_LAZY))" not in match.group("body"):
        raise ValueError("Lazy preemption requires feature gate; function changed")
    config = kconfig.read_text(encoding="utf-8")
    if not re.search(
        r"(?m)^config PREEMPT_LAZY\s*\n\s*def_bool y if HAVE_PREEMPT_LAZY && PREEMPT_RT_FULL",
        config,
    ):
        raise ValueError("Missing RT lazy preemption Kconfig prerequisite")
    updated = before.replace(ORIGINAL, REPLACEMENT, 1)
    if updated.count("SCHED_FEAT_TTWU_QUEUE 0") != 1:
        raise ValueError("Vendor TTWU_QUEUE invariant changed")
    if updated.count("#define SCHED_FEAT_PREEMPT_LAZY 1") != 1:
        raise ValueError("Lazy feature not uniquely defined in RT config")
    if updated.count("#define SCHED_FEAT_PREEMPT_LAZY 0") != 1:
        raise ValueError("Non-lazy configuration branch not uniquely defined")
    return feature, rejected, updated


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = p.parse_args()
    root = args.tree.resolve()
    feature, rejected, patched = analyze(root)
    if args.mode == "apply":
        feature.write_text(patched, encoding="utf-8")
        rejected.unlink()

    files = len(list(root.rglob("*.rej")))
    status = {
        "stage": "EXP76_RT_STAGE15_SCHED_FEATURE_ABI",
        "applied": args.mode == "apply",
        "vendor_ttwu_queue_preserved": 0,
        "preempt_lazy_feature_defined_only_under_rt_lazy_config": True,
        "rt_scheduler_resched_curr_lazy_feature_reference_satisfied": args.mode == "apply",
        "remaining_rejected_files": files,
        "kernel_compiled": False,
        "rt_config_enabled": False,
        "flash_ready": False,
    }
    report = args.report.resolve()
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage15-status.json").write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(status, indent=2))
    if args.mode == "apply" and files != 66:
        raise SystemExit("FAIL_CLOSED: expected 66 remaining rejected files")


if __name__ == "__main__":
    main()
