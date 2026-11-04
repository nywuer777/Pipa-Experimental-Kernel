#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage97 synthetic RCU provenance regressions / NO FLASH
"""Fail-closed tests for pinned RT tree_plugin reject and Stage93/95 continuity."""
from __future__ import annotations

import hashlib
import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(
    str(ROOT / "tools/exp76-stage97-rcu-tree-plugin-audit.py"),
    run_name="stage97_test_helpers",
)
REJECT_TEXT = "".join(
    f"@@ -{i + 1},2 +{i + 1},2 @@ context\n unchanged\n-old_{i}();\n+new_{i}();\n"
    for i in range(11)
)

def put(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

def put_json(path: Path, obj: dict) -> None:
    put(path, json.dumps(obj))

def edit_json(path: Path, field: str, value) -> None:
    obj = json.loads(path.read_text(encoding="utf-8"))
    obj[field] = value
    put_json(path, obj)

def fixture(base: Path) -> tuple[Path, ...]:
    tree = base / "trial"
    (tree / ".git").mkdir(parents=True)
    put(tree / M["REJECT"], REJECT_TEXT)
    put(tree / M["SOURCE"], "\n".join(M["SOURCE_MARKERS"]) + "\n")
    put(tree / "kernel/sched/cpupri.c.rej", "@@ -1 +1 @@\n-old\n+new\n")
    for i in range(62):
        put(tree / f"other/{i:02d}.c.rej", "@@ -1 +1 @@\n-old\n+new\n")
    reject_sha = hashlib.sha256(REJECT_TEXT.encode()).hexdigest()
    inventory = base / "stage82.json"
    put_json(inventory, {
        "stage": M["STAGE82"], "remaining_rejected_files": 64,
        "source_modified": False, "rejects_deleted": False,
        "entries": [{
            "source": M["SOURCE"], "reject_sha256": reject_sha,
            "hunk_count": 11,
        }],
    })
    stage93 = base / "stage93.json"
    put_json(stage93, {
        "stage": M["STAGE93"], "rt_config_verified": True,
        "linked_rcu_exports_missing": [],
        "linked_rcu_exports_present": [
            "synchronize_rcu", "rcu_barrier",
            "__rcu_read_lock", "__rcu_read_unlock",
        ],
        "original_rejected_files_remaining": 64,
        "verification_scope": "SOURCE_AND_LINK_ONLY",
        "rt_rcu_runtime_semantics_verified": False,
        "source_sha256": {
            M["SOURCE"]: hashlib.sha256((tree / M["SOURCE"]).read_bytes()).hexdigest()
        },
    })
    stage95 = base / "stage95.json"
    put_json(stage95, {
        "stage": M["STAGE95"], "stage93_linked_rcu_exports_verified": True,
        "reviewed_original_rcu_header_rejected_hunks": 5,
        "source_modified": False, "rt_rcu_runtime_semantics_verified": False,
        "original_rejected_files_remaining": 64,
    })
    return tree, inventory, stage93, stage95, base / "report"

def run(fx: tuple[Path, ...]) -> dict:
    return M["execute"](*fx)

def expect_failure(action, phrase: str) -> None:
    try:
        action()
    except ValueError as exc:
        assert phrase in str(exc), (phrase, str(exc))
    else:
        raise AssertionError("Stage97 must reject " + phrase)

def update_source_sha(fx: tuple[Path, ...]) -> None:
    obj = json.loads(fx[2].read_text(encoding="utf-8"))
    obj["source_sha256"][M["SOURCE"]] = hashlib.sha256(
        (fx[0] / M["SOURCE"]).read_bytes()
    ).hexdigest()
    put_json(fx[2], obj)

def main() -> None:
    original_sha = M["execute"].__globals__["REJECT_SHA"]
    M["execute"].__globals__["REJECT_SHA"] = hashlib.sha256(
        REJECT_TEXT.encode()
    ).hexdigest()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            good = fixture(base / "good")
            original_source = (good[0] / M["SOURCE"]).read_bytes()
            original_reject = (good[0] / M["REJECT"]).read_bytes()
            result = run(good)
            assert result["stage"] == M["STAGE"]
            assert result["verification_scope"] == "SOURCE_PROVENANCE_ONLY"
            assert result["original_rcu_plugin_rejected_hunks_pending"] == 11
            assert result["unified_rcu_plugin_source_marker_count"] == 4
            assert result["rcu_plugin_source_matches_stage93"]
            assert result["original_rejected_files_remaining"] == 64
            assert result["rejected_hunks_semantically_resolved"] == 0
            assert not result["rt_rcu_runtime_semantics_verified"]
            assert not result["rcu_grace_period_runtime_verified"]
            assert not result["device_boot_verified"]
            assert not result["kernel_built"] and not result["flash_ready"]
            assert (good[0] / M["SOURCE"]).read_bytes() == original_source
            assert (good[0] / M["REJECT"]).read_bytes() == original_reject
            assert json.loads((good[4] / M["REPORT"]).read_text()) == result

            reject_drift = fixture(base / "reject")
            put(reject_drift[0] / M["REJECT"], REJECT_TEXT + "drift\n")
            expect_failure(lambda: run(reject_drift), "rejection SHA256 drift")

            wrong_index = fixture(base / "inventory")
            obj = json.loads(wrong_index[1].read_text())
            obj["entries"][0]["hunk_count"] = 10
            put_json(wrong_index[1], obj)
            expect_failure(lambda: run(wrong_index), "hunk provenance mismatch")

            malformed = fixture(base / "malformed")
            put(malformed[0] / M["REJECT"], REJECT_TEXT.replace(
                "@@ -1,2 +1,2 @@", "@@ broken"
            ))
            M["execute"].__globals__["REJECT_SHA"] = hashlib.sha256(
                (malformed[0] / M["REJECT"]).read_bytes()
            ).hexdigest()
            obj = json.loads(malformed[1].read_text())
            obj["entries"][0]["reject_sha256"] = M["execute"].__globals__["REJECT_SHA"]
            put_json(malformed[1], obj)
            expect_failure(lambda: run(malformed), "11-hunk structure drift")
            M["execute"].__globals__["REJECT_SHA"] = hashlib.sha256(
                REJECT_TEXT.encode()
            ).hexdigest()

            stale_source = fixture(base / "source-digest")
            put(stale_source[0] / M["SOURCE"], "altered\n")
            expect_failure(lambda: run(stale_source), "source SHA256 drift")

            missing_marker = fixture(base / "missing-marker")
            put(missing_marker[0] / M["SOURCE"],
                (missing_marker[0] / M["SOURCE"]).read_text().replace(
                    "rcu_read_unlock_special(", "old_unlock_special("
                ))
            update_source_sha(missing_marker)
            expect_failure(lambda: run(missing_marker), "source marker missing")

            legacy = fixture(base / "legacy")
            with (legacy[0] / M["SOURCE"]).open("a") as f:
                f.write("struct rcu_state rcu_bh_state;\n")
            update_source_sha(legacy)
            expect_failure(lambda: run(legacy), "legacy RCU flavor")

            wrong_stage93 = fixture(base / "stage93")
            edit_json(wrong_stage93[2], "rt_config_verified", False)
            expect_failure(lambda: run(wrong_stage93), "Stage93 linked RCU baseline")

            wrong_stage95 = fixture(base / "stage95")
            edit_json(wrong_stage95[3], "reviewed_original_rcu_header_rejected_hunks", 4)
            expect_failure(lambda: run(wrong_stage95), "Stage95 RCU header")

            wrong_stage82 = fixture(base / "stage82")
            edit_json(wrong_stage82[1], "remaining_rejected_files", 63)
            expect_failure(lambda: run(wrong_stage82), "Stage82 plugin hunk")

            missing_reject = fixture(base / "count")
            (missing_reject[0] / "other/00.c.rej").unlink()
            expect_failure(lambda: run(missing_reject), "original 64 RT reject")

            missing_sentinel = fixture(base / "sentinel")
            (missing_sentinel[0] / "kernel/sched/cpupri.c.rej").unlink()
            expect_failure(lambda: run(missing_sentinel), "original 64 RT reject")
    finally:
        M["execute"].__globals__["REJECT_SHA"] = original_sha
    print("EXP76_STAGE97_RCU_TREE_PLUGIN_REGRESSIONS=12_PASS; "
          "REJECT_HUNKS=11; SOURCE_ONLY=true; FLASH_READY=false")

if __name__ == "__main__":
    main()
