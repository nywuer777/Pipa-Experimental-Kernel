#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage98 RCU update provenance regressions / NO FLASH
"""Fail-closed synthetic tests for pinned RT update.c rejection and prior proof."""
from __future__ import annotations

import hashlib
import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(
    str(ROOT / "tools/exp76-stage98-rcu-update-audit.py"),
    run_name="stage98_test_helpers",
)
REJECT_TEXT = "".join(
    (
        header + " context\n" +
        ("+#include <linux/rcuwait.h>\n" if i == 0 else "") +
        ("-static int rcu_normal_after_boot;\n"
         "+static int rcu_normal_after_boot = IS_ENABLED(CONFIG_PREEMPT_RT_FULL);\n"
         if i == 1 else "") +
        ("+#ifndef CONFIG_PREEMPT_RT_FULL\n" if i == 2 else "") +
        f"-old_{i}();\n+new_{i}();\n"
    )
    for i, header in enumerate(M["HUNK_PREFIXES"])
)

def put(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def put_json(path: Path, obj: dict) -> None:
    put(path, json.dumps(obj))

def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def fixture(base: Path) -> tuple[Path, ...]:
    tree = base / "trial"
    (tree / ".git").mkdir(parents=True)
    put(tree / M["REJECT"], REJECT_TEXT)
    put(tree / M["SOURCE"], (
        "#ifndef CONFIG_PREEMPT_RT_FULL\n"
        "int rcu_read_lock_bh_held(void)\n"
        "EXPORT_SYMBOL_GPL(rcu_read_lock_bh_held);\n"
    ))
    put(tree / "kernel/sched/cpupri.c.rej", "@@ -1 +1 @@\n-old\n+new\n")
    for i in range(62):
        put(tree / f"other/{i:02d}.c.rej", "@@ -1 +1 @@\n-old\n+new\n")
    inventory, stage93, stage97 = (
        base / "stage82.json", base / "stage93.json", base / "stage97.json"
    )
    put_json(inventory, {
        "stage": M["STAGE82"], "remaining_rejected_files": 64,
        "source_modified": False, "rejects_deleted": False,
        "entries": [{
            "source": M["SOURCE"],
            "hunk_count": 3,
            "reject_sha256": hashlib.sha256(REJECT_TEXT.encode()).hexdigest(),
            "parse_issues": [],
        }],
    })
    put_json(stage93, {
        "stage": M["STAGE93"], "rt_config_verified": True,
        "linked_rcu_exports_missing": [],
        "linked_rcu_exports_present": [
            "synchronize_rcu", "rcu_barrier",
            "__rcu_read_lock", "__rcu_read_unlock",
        ],
        "verification_scope": "SOURCE_AND_LINK_ONLY",
        "original_rejected_files_remaining": 64,
        "rt_rcu_runtime_semantics_verified": False,
        "rcu_grace_period_runtime_verified": False,
        "source_sha256": {
            M["SOURCE"]: hashlib.sha256((tree / M["SOURCE"]).read_bytes()).hexdigest()
        },
    })
    put_json(stage97, {
        "stage": M["STAGE97"],
        "stage82_inventory_proven": True,
        "stage93_linked_exports_proven": True,
        "original_rcu_plugin_rejected_hunks_pending": 11,
        "original_rejected_files_remaining": 64,
        "rcu_plugin_source_matches_stage93": True,
        "source_modified": False,
        "rt_rcu_runtime_semantics_verified": False,
        "verification_scope": "SOURCE_PROVENANCE_ONLY",
    })
    return tree, inventory, stage93, stage97, base / "report"

def run(fx: tuple[Path, ...]) -> dict:
    return M["execute"](*fx)

def reject(action, token: str) -> None:
    try:
        action()
    except ValueError as error:
        assert token in str(error), (token, str(error))
    else:
        raise AssertionError("Expected Stage98 refusal: " + token)

def update_digest(fx: tuple[Path, ...]) -> None:
    obj = load(fx[1])
    digest = hashlib.sha256((fx[0] / M["REJECT"]).read_bytes()).hexdigest()
    obj["entries"][0]["reject_sha256"] = digest
    put_json(fx[1], obj)
    M["execute"].__globals__["REJECT_SHA"] = digest

def update_source_digest(fx: tuple[Path, ...]) -> None:
    obj = load(fx[2])
    obj["source_sha256"][M["SOURCE"]] = hashlib.sha256(
        (fx[0] / M["SOURCE"]).read_bytes()
    ).hexdigest()
    put_json(fx[2], obj)

def main() -> None:
    globals_dict = M["execute"].__globals__
    original = globals_dict["REJECT_SHA"]
    pinned = hashlib.sha256(REJECT_TEXT.encode()).hexdigest()
    globals_dict["REJECT_SHA"] = pinned
    try:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            good = fixture(base / "good")
            original_source = (good[0] / M["SOURCE"]).read_bytes()
            original_reject = (good[0] / M["REJECT"]).read_bytes()
            result = run(good)
            assert result["original_rcu_update_rejected_hunks_pending"] == 3
            assert result["original_rcu_update_hunk_headers"] == list(
                M["HUNK_PREFIXES"]
            ) if all(
                h == prefix + " context" for h, prefix in zip(
                    result["original_rcu_update_hunk_headers"], M["HUNK_PREFIXES"]
                )
            ) else False
            assert result["stage82_inventory_proven"]
            assert result["stage93_linked_exports_proven"]
            assert result["stage97_rcu_plugin_proven"]
            assert result["rcu_update_source_matches_stage93"]
            assert result["verification_scope"] == "SOURCE_PROVENANCE_ONLY"
            assert result["original_rejected_files_remaining"] == 64
            assert result["rejected_hunks_semantically_resolved"] == 0
            assert not result["rt_rcu_runtime_semantics_verified"]
            assert not result["rcu_grace_period_runtime_verified"]
            assert not result["device_boot_verified"]
            assert not result["kernel_built"] and not result["flash_ready"]
            assert (good[0] / M["SOURCE"]).read_bytes() == original_source
            assert (good[0] / M["REJECT"]).read_bytes() == original_reject
            assert load(good[4] / M["REPORT"]) == result

            drift = fixture(base / "reject-sha")
            put(drift[0] / M["REJECT"], REJECT_TEXT + "extra\n")
            reject(lambda: run(drift), "reject SHA256 drift")

            bad_index = fixture(base / "inventory")
            inv = load(bad_index[1])
            inv["entries"][0]["hunk_count"] = 2
            put_json(bad_index[1], inv)
            reject(lambda: run(bad_index), "hunk provenance mismatch")

            bad_header = fixture(base / "headers")
            put(bad_header[0] / M["REJECT"],
                REJECT_TEXT.replace("@@ -53,6 +53,7 @@", "@@ malformed"))
            update_digest(bad_header)
            reject(lambda: run(bad_header), "three-hunk headers changed")
            globals_dict["REJECT_SHA"] = pinned

            bad_marker = fixture(base / "marker")
            put(bad_marker[0] / M["REJECT"],
                REJECT_TEXT.replace("+#include <linux/rcuwait.h>",
                                    "+#include <linux/missing.h>"))
            update_digest(bad_marker)
            reject(lambda: run(bad_marker), "marker drift")
            globals_dict["REJECT_SHA"] = pinned

            stale_source = fixture(base / "source-sha")
            put(stale_source[0] / M["SOURCE"], "modified\n")
            reject(lambda: run(stale_source), "source SHA256 drift")

            missing_marker = fixture(base / "source-marker")
            put(missing_marker[0] / M["SOURCE"],
                (missing_marker[0] / M["SOURCE"]).read_text().replace(
                    "EXPORT_SYMBOL_GPL(rcu_read_lock_bh_held);", "not_exported;"
                ))
            update_source_digest(missing_marker)
            reject(lambda: run(missing_marker), "unified source marker missing")

            bad_guard = fixture(base / "guard-order")
            put(bad_guard[0] / M["SOURCE"], (
                "int rcu_read_lock_bh_held(void)\n"
                "#ifndef CONFIG_PREEMPT_RT_FULL\n"
                "EXPORT_SYMBOL_GPL(rcu_read_lock_bh_held);\n"
            ))
            update_source_digest(bad_guard)
            reject(lambda: run(bad_guard), "conditional location drift")

            bad_stage93 = fixture(base / "stage93")
            old = load(bad_stage93[2])
            old["linked_rcu_exports_missing"] = ["rcu_barrier"]
            put_json(bad_stage93[2], old)
            reject(lambda: run(bad_stage93), "Stage93 linked RCU")

            bad_stage97 = fixture(base / "stage97")
            old = load(bad_stage97[3])
            old["source_modified"] = True
            put_json(bad_stage97[3], old)
            reject(lambda: run(bad_stage97), "Stage97 RCU plugin")

            lost_reject = fixture(base / "reject-count")
            (lost_reject[0] / "other/00.c.rej").unlink()
            reject(lambda: run(lost_reject), "original 64 RT reject")

            lost_git = fixture(base / "git")
            (lost_git[0] / ".git").rmdir()
            reject(lambda: run(lost_git), "isolated pinned")

            lost_sentinel = fixture(base / "sentinel")
            (lost_sentinel[0] / "kernel/sched/cpupri.c.rej").unlink()
            reject(lambda: run(lost_sentinel), "original 64 RT reject")
    finally:
        globals_dict["REJECT_SHA"] = original
    print("EXP76_STAGE98_RCU_UPDATE_REGRESSIONS=13_PASS; "
          "REJECT_HUNKS=3; NOFLASH=true")

if __name__ == "__main__":
    main()
