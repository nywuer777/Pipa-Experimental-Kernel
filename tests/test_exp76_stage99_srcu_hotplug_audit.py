#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage99 SRCU synthetic regression checks / NO FLASH
"""Fail-closed fixtures for six-hunk SRCU provenance and prior RCU gates."""
from __future__ import annotations

import hashlib
import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(
    str(ROOT / "tools/exp76-stage99-srcu-hotplug-audit.py"),
    run_name="stage99_synthetic_helpers",
)
HEADERS = list(M["HUNK_PREFIXES"]) + [
    "@@ -900 +901 @@", "@@ -1000 +1002 @@", "@@ -1100 +1103 @@",
]
REJECT_TEXT = "".join(
    header + "\n unchanged\n" +
    ("-\tpreempt_disable();\n+\tcpus_read_lock();\n" if i == 0 else "") +
    f"-old_{i}();\n+new_{i}();\n"
    for i, header in enumerate(HEADERS)
)

def put(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def json_put(path: Path, value: dict) -> None:
    put(path, json.dumps(value))

def json_get(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def fixture(root: Path) -> tuple[Path, ...]:
    tree = root / "trial"
    (tree / ".git").mkdir(parents=True)
    put(tree / M["REJECT"], REJECT_TEXT)
    put(tree / M["SOURCE"],
        "void srcu_gp_start(struct srcu_struct *sp) {} \n"
        "bool srcu_queue_delayed_work_on(int cpu) { return true; }\n"
        "void srcu_flip(struct srcu_struct *sp) {} \n")
    put(tree / "kernel/sched/cpupri.c.rej", "@@ -1 +1 @@\n-old\n+new\n")
    for i in range(62):
        put(tree / f"other/{i:02d}.c.rej", "@@ -1 +1 @@\n-old\n+new\n")
    inventory = root / "stage82.json"
    json_put(inventory, {
        "stage": M["STAGE82"],
        "remaining_rejected_files": 64,
        "source_modified": False, "rejects_deleted": False,
        "entries": [{
            "source": M["SOURCE"],
            "source_exists": True,
            "review_category": "rcu",
            "reject_sha256": hashlib.sha256(REJECT_TEXT.encode()).hexdigest(),
            "hunk_count": 6,
            "parse_issues": [],
            "hunks": [{"header": h} for h in HEADERS],
        }],
    })
    stage93 = root / "stage93.json"
    json_put(stage93, {
        "stage": M["STAGE93"], "rt_config_verified": True,
        "linked_rcu_exports_missing": [],
        "verification_scope": "SOURCE_AND_LINK_ONLY",
        "original_rejected_files_remaining": 64,
        "rt_rcu_runtime_semantics_verified": False,
        "rcu_grace_period_runtime_verified": False,
    })
    stage98 = root / "stage98.json"
    json_put(stage98, {
        "stage": M["STAGE98"],
        "stage82_inventory_proven": True,
        "stage93_linked_exports_proven": True,
        "original_rcu_update_rejected_hunks_pending": 3,
        "rcu_update_source_matches_stage93": True,
        "verification_scope": "SOURCE_PROVENANCE_ONLY",
        "original_rejected_files_remaining": 64,
        "source_modified": False,
        "rt_rcu_runtime_semantics_verified": False,
    })
    return tree, inventory, stage93, stage98, root / "report"

def run(fx: tuple[Path, ...]) -> dict:
    return M["execute"](*fx)

def reject(action, match: str) -> None:
    try:
        action()
    except ValueError as e:
        assert match in str(e), (match, str(e))
    else:
        raise AssertionError("Stage99 expected refusal: " + match)

def edit(path: Path, key: str, value) -> None:
    data = json_get(path)
    data[key] = value
    json_put(path, data)

def align_reject(fx: tuple[Path, ...]) -> None:
    new = hashlib.sha256((fx[0] / M["REJECT"]).read_bytes()).hexdigest()
    M["execute"].__globals__["REJECT_SHA"] = new
    entry = json_get(fx[1])
    entry["entries"][0]["reject_sha256"] = new
    json_put(fx[1], entry)

def main() -> None:
    globals_dict = M["execute"].__globals__
    original_sha = globals_dict["REJECT_SHA"]
    synthetic_sha = hashlib.sha256(REJECT_TEXT.encode()).hexdigest()
    globals_dict["REJECT_SHA"] = synthetic_sha
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = fixture(root / "good")
            before_source = (good[0] / M["SOURCE"]).read_bytes()
            before_reject = (good[0] / M["REJECT"]).read_bytes()
            result = run(good)
            assert result["original_srcu_rejected_hunks_pending"] == 6
            assert result["original_srcu_rejected_hunk_headers"] == HEADERS
            assert result["stage82_reject_inventory_verified"]
            assert result["stage93_linked_rcu_contract_verified"]
            assert result["stage98_rcu_update_provenance_verified"]
            assert result["original_rejected_files_remaining"] == 64
            assert result["verification_scope"] == "SOURCE_AND_REJECT_PROVENANCE_ONLY"
            assert result["rejected_hunks_semantically_resolved"] == 0
            assert result["source_modified"] is False
            assert result["original_rejects_deleted"] is False
            assert not result["rt_srcu_hotplug_runtime_verified"]
            assert not result["rt_rcu_runtime_semantics_verified"]
            assert not result["device_boot_verified"]
            assert not result["kernel_built"] and not result["flash_ready"]
            assert (good[0] / M["SOURCE"]).read_bytes() == before_source
            assert (good[0] / M["REJECT"]).read_bytes() == before_reject
            assert json_get(good[4] / M["REPORT"]) == result

            # Test each negative fixture in a new isolated synthetic checkout.
            modified_reject = fixture(root / "reject-digest")
            put(modified_reject[0] / M["REJECT"], REJECT_TEXT + "\n")
            reject(lambda: run(modified_reject), "rejection SHA256 drift")

            bad_index = fixture(root / "index")
            entry = json_get(bad_index[1])
            entry["entries"][0]["hunk_count"] = 5
            json_put(bad_index[1], entry)
            reject(lambda: run(bad_index), "Stage82 SRCU reject provenance")

            bad_index_headers = fixture(root / "index-headers")
            entry = json_get(bad_index_headers[1])
            entry["entries"][0]["hunks"][4]["header"] = "@@ -800 +800 @@"
            json_put(bad_index_headers[1], entry)
            reject(lambda: run(bad_index_headers), "six SRCU hunk headers")

            bad_hunk = fixture(root / "hunk")
            put(bad_hunk[0] / M["REJECT"],
                REJECT_TEXT.replace("@@ -900 +901 @@", "@@ broken"))
            align_reject(bad_hunk)
            reject(lambda: run(bad_hunk), "six SRCU hunk headers")
            globals_dict["REJECT_SHA"] = synthetic_sha

            missing_reject_marker = fixture(root / "reject-marker")
            put(missing_reject_marker[0] / M["REJECT"],
                REJECT_TEXT.replace("+\tcpus_read_lock();", "+\tcpu_read_lock();"))
            align_reject(missing_reject_marker)
            reject(lambda: run(missing_reject_marker), "hotplug reject marker missing")
            globals_dict["REJECT_SHA"] = synthetic_sha

            missing_source_marker = fixture(root / "source-marker")
            put(missing_source_marker[0] / M["SOURCE"],
                "srcu_gp_start(\nsrcu_flip(\n")
            reject(lambda: run(missing_source_marker), "SRCU implementation marker missing")

            wrong_stage82 = fixture(root / "stage82")
            edit(wrong_stage82[1], "rejects_deleted", True)
            reject(lambda: run(wrong_stage82), "Stage82 SRCU reject provenance")

            wrong_stage93 = fixture(root / "stage93")
            edit(wrong_stage93[2], "rt_config_verified", False)
            reject(lambda: run(wrong_stage93), "Stage93 linked RCU")

            wrong_stage98 = fixture(root / "stage98")
            edit(wrong_stage98[3], "rcu_update_source_matches_stage93", False)
            reject(lambda: run(wrong_stage98), "Stage98 RCU update")

            missing_reject = fixture(root / "count")
            (missing_reject[0] / "other/00.c.rej").unlink()
            reject(lambda: run(missing_reject), "original 64 RT rejected")

            missing_sentinel = fixture(root / "sentinel")
            (missing_sentinel[0] / "kernel/sched/cpupri.c.rej").unlink()
            reject(lambda: run(missing_sentinel), "original 64 RT rejected")

            missing_git = fixture(root / "git")
            (missing_git[0] / ".git").rmdir()
            reject(lambda: run(missing_git), "isolated pinned")
    finally:
        globals_dict["REJECT_SHA"] = original_sha
    print("EXP76_STAGE99_SRCU_HOTPLUG_REGRESSIONS=12_NEGATIVE_PLUS_PASS; "
          "REJECT_HUNKS=6; FLASH_READY=false")

if __name__ == "__main__":
    main()
