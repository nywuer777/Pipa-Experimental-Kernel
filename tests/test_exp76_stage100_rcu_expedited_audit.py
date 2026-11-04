#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage100 RCU expedited synthetic regressions / NO FLASH
"""Fail-closed synthetic regression cases for expedited RCU CPU-selection audit."""
from __future__ import annotations

import hashlib
import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(
    str(ROOT / "tools/exp76-stage100-rcu-expedited-audit.py"),
    run_name="stage100_synthetic_helpers",
)
HUNK_HEADERS = [prefix for prefix in M["HUNK_PREFIXES"]]
REJECT_CONTENT = (
    HUNK_HEADERS[0] + "\n context\n"
    + M["REJECT_MARKERS"][0] + "\n+replacement();\n"
    + HUNK_HEADERS[1] + "\n context\n"
    + M["REJECT_MARKERS"][1] + "\n"
    + M["REJECT_MARKERS"][2] + "\n+replacement2();\n"
)

def put(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")

def save(path: Path, data: dict) -> None:
    put(path, json.dumps(data))

def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def fixture(base: Path) -> tuple[Path, ...]:
    root = base / "tree"
    (root / ".git").mkdir(parents=True)
    put(root / M["SOURCE"], (
        "static void sync_rcu_exp_select_node_cpus(void) {}\n"
        "static void sync_rcu_exp_select_cpus(void) {}\n"
    ))
    put(root / M["TREE"], "void rcu_core(void) {}\n")
    put(root / M["REJECT"], REJECT_CONTENT)
    put(root / "kernel/sched/cpupri.c.rej", "@@ -1 +1 @@\n-old\n+new\n")
    for i in range(62):
        put(root / f"other/{i:02d}.c.rej", "@@ -1 +1 @@\n-old\n+new\n")
    inventory, stage93, stage99 = (
        base / "stage82.json", base / "stage93.json", base / "stage99.json"
    )
    save(inventory, {
        "stage": M["STAGE82"],
        "remaining_rejected_files": 64,
        "source_modified": False, "rejects_deleted": False,
        "entries": [{
            "source": M["SOURCE"], "source_exists": True,
            "review_category": "rcu", "parse_issues": [],
            "reject_sha256": hashlib.sha256(REJECT_CONTENT.encode()).hexdigest(),
            "hunk_count": 2,
            "hunks": [{"header": header} for header in HUNK_HEADERS],
        }],
    })
    save(stage93, {
        "stage": M["STAGE93"],
        "rt_config_verified": True, "linked_rcu_exports_missing": [],
        "linked_rcu_exports_present": [
            "synchronize_rcu", "rcu_barrier",
            "__rcu_read_lock", "__rcu_read_unlock",
        ],
        "verification_scope": "SOURCE_AND_LINK_ONLY",
        "original_rejected_files_remaining": 64,
        "rt_rcu_runtime_semantics_verified": False,
        "rcu_grace_period_runtime_verified": False,
        "source_sha256": {
            M["TREE"]: hashlib.sha256((root / M["TREE"]).read_bytes()).hexdigest()
        },
    })
    save(stage99, {
        "stage": M["STAGE99"],
        "stage82_reject_inventory_verified": True,
        "stage93_linked_rcu_contract_verified": True,
        "original_srcu_rejected_hunks_pending": 6,
        "verification_scope": "SOURCE_AND_REJECT_PROVENANCE_ONLY",
        "original_rejected_files_remaining": 64,
        "source_modified": False,
        "rt_srcu_hotplug_runtime_verified": False,
        "flash_ready": False,
    })
    return root, inventory, stage93, stage99, base / "report"

def execute(fx: tuple[Path, ...]) -> dict:
    return M["execute"](*fx)

def negative(fn, expected: str) -> None:
    try:
        fn()
    except ValueError as e:
        assert expected in str(e), (expected, str(e))
    else:
        raise AssertionError("Stage100 failed to reject: " + expected)

def align_reject(fx: tuple[Path, ...]) -> None:
    new_sha = hashlib.sha256((fx[0] / M["REJECT"]).read_bytes()).hexdigest()
    M["execute"].__globals__["REJECT_SHA"] = new_sha
    obj = read(fx[1])
    obj["entries"][0]["reject_sha256"] = new_sha
    save(fx[1], obj)

def main() -> None:
    env = M["execute"].__globals__
    saved = env["REJECT_SHA"]
    synthetic_sha = hashlib.sha256(REJECT_CONTENT.encode()).hexdigest()
    env["REJECT_SHA"] = synthetic_sha
    try:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            good = fixture(base / "good")
            source_before = (good[0] / M["SOURCE"]).read_bytes()
            reject_before = (good[0] / M["REJECT"]).read_bytes()
            result = execute(good)
            assert result["original_exp_rcu_rejected_hunks_pending"] == 2
            assert result["original_exp_rcu_rejected_hunk_headers"] == HUNK_HEADERS
            assert all(result["e404_old_selector_token_presence"].values())
            assert result["stage82_reject_inventory_verified"]
            assert result["stage93_linked_rcu_tree_verified"]
            assert result["stage99_srcu_provenance_verified"]
            assert result["original_rejected_files_remaining"] == 64
            assert result["verification_scope"] == "SOURCE_AND_REJECT_PROVENANCE_ONLY"
            assert result["rejected_hunks_semantically_resolved"] == 0
            assert not result["source_modified"] and not result["original_rejects_deleted"]
            assert not result["rt_exp_rcu_cpu_selection_runtime_verified"]
            assert not result["rcu_grace_period_runtime_verified"]
            assert not result["rt_rcu_runtime_semantics_verified"]
            assert not result["device_boot_verified"]
            assert not result["kernel_built"] and not result["flash_ready"]
            assert source_before == (good[0] / M["SOURCE"]).read_bytes()
            assert reject_before == (good[0] / M["REJECT"]).read_bytes()
            assert read(good[4] / M["REPORT"]) == result

            changed_reject = fixture(base / "reject")
            put(changed_reject[0] / M["REJECT"], REJECT_CONTENT + "junk\n")
            negative(lambda: execute(changed_reject), "rejection SHA256 drift")

            bad_count = fixture(base / "count")
            obj = read(bad_count[1])
            obj["entries"][0]["hunk_count"] = 3
            save(bad_count[1], obj)
            negative(lambda: execute(bad_count), "Stage82 expedited RCU")

            bad_header = fixture(base / "header")
            put(bad_header[0] / M["REJECT"],
                REJECT_CONTENT.replace(HUNK_HEADERS[1], "@@ invalid @@"))
            align_reject(bad_header)
            negative(lambda: execute(bad_header), "hunk headers changed")
            env["REJECT_SHA"] = synthetic_sha

            bad_marker = fixture(base / "marker")
            put(bad_marker[0] / M["REJECT"],
                REJECT_CONTENT.replace(M["REJECT_MARKERS"][1], "-other_cpu_path();"))
            align_reject(bad_marker)
            negative(lambda: execute(bad_marker), "CPU selection diff marker drift")
            env["REJECT_SHA"] = synthetic_sha

            bad_stage82 = fixture(base / "stage82")
            obj = read(bad_stage82[1])
            obj["entries"][0]["review_category"] = "other"
            save(bad_stage82[1], obj)
            negative(lambda: execute(bad_stage82), "Stage82 expedited RCU")

            bad_stage93 = fixture(base / "stage93")
            obj = read(bad_stage93[2])
            obj["linked_rcu_exports_missing"] = ["rcu_barrier"]
            save(bad_stage93[2], obj)
            negative(lambda: execute(bad_stage93), "Stage93 linked RCU tree")

            stale_tree = fixture(base / "stale-tree")
            put(stale_tree[0] / M["TREE"], "different tree.c")
            negative(lambda: execute(stale_tree), "Stage93 linked RCU tree")

            bad_stage99 = fixture(base / "stage99")
            obj = read(bad_stage99[3])
            obj["rt_srcu_hotplug_runtime_verified"] = True
            save(bad_stage99[3], obj)
            negative(lambda: execute(bad_stage99), "Stage99 SRCU source")

            empty_source = fixture(base / "empty")
            put(empty_source[0] / M["SOURCE"], "\n ")
            negative(lambda: execute(empty_source), "source empty")

            missing_reject = fixture(base / "missing")
            (missing_reject[0] / "other/00.c.rej").unlink()
            negative(lambda: execute(missing_reject), "original 64 RT rejected")

            missing_git = fixture(base / "git")
            (missing_git[0] / ".git").rmdir()
            negative(lambda: execute(missing_git), "isolated pinned")
    finally:
        env["REJECT_SHA"] = saved
    print("EXP76_STAGE100_EXP_RCU_CPU_SELECTION_REGRESSIONS=11_NEGATIVE_PLUS_PASS; "
          "REJECT_HUNKS=2; FLASH_READY=false")

if __name__ == "__main__":
    main()
