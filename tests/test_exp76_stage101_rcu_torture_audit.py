#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage101 RCU torture synthetic checks / NO FLASH
"""Fail-closed synthetic regression for rejected legacy RCU-BH torture hunks."""
from __future__ import annotations

import hashlib
import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(
    str(ROOT / "tools/exp76-stage101-rcu-torture-audit.py"),
    run_name="stage101_test_helpers",
)
REJECT_TEXT = (
    M["HEADERS"][0] + "\n unchanged\n"
    + M["REJECT_MARKERS"][0] + "\n"
    + M["HEADERS"][1] + "\n unchanged\n"
    + M["REJECT_MARKERS"][1] + "\n"
    + M["REJECT_MARKERS"][2] + "\n"
    + M["REJECT_MARKERS"][3] + "\n"
)
SYNTH_SHA = hashlib.sha256(REJECT_TEXT.encode("utf-8")).hexdigest()

def put(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")

def put_json(path: Path, value: dict) -> None:
    put(path, json.dumps(value))

def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def fixture(base: Path) -> tuple[Path, ...]:
    tree = base / "tree"
    (tree / ".git").mkdir(parents=True)
    put(tree / M["REJECT"], REJECT_TEXT)
    put(tree / M["SOURCE"],
        "static struct rcu_torture_ops rcu_ops = {};\n"
        "static struct rcu_torture_ops rcu_bh_ops = {};\n")
    put(tree / "kernel/sched/cpupri.c.rej", "@@ -1 +1 @@\n-old\n+new\n")
    for i in range(62):
        put(tree / f"other/{i:02d}.c.rej", "@@ -1 +1 @@\n-old\n+new\n")
    inventory, s93, s95, s100 = (
        base / "stage82.json", base / "stage93.json",
        base / "stage95.json", base / "stage100.json",
    )
    put_json(inventory, {
        "stage": M["STAGE82"], "remaining_rejected_files": 64,
        "source_modified": False, "rejects_deleted": False,
        "entries": [{
            "source": M["SOURCE"], "source_exists": True,
            "review_category": "rcu", "reject_sha256": SYNTH_SHA,
            "hunk_count": 2, "parse_issues": [],
            "hunks": [{"header": h} for h in M["HEADERS"]],
        }],
    })
    put_json(s93, {
        "stage": M["STAGE93"], "rt_config_verified": True,
        "linked_rcu_exports_present": [
            "synchronize_rcu", "rcu_barrier",
            "__rcu_read_lock", "__rcu_read_unlock",
        ],
        "linked_rcu_exports_missing": [],
        "verification_scope": "SOURCE_AND_LINK_ONLY",
        "original_rejected_files_remaining": 64,
        "rt_rcu_runtime_semantics_verified": False,
    })
    put_json(s95, {
        "stage": M["STAGE95"],
        "obsolete_legacy_rcu_flavor_api_absent": True,
        "vendor_unified_gp_api_declared": True,
        "original_rejected_files_remaining": 64,
        "source_modified": False,
        "rt_rcu_runtime_semantics_verified": False,
    })
    put_json(s100, {
        "stage": M["STAGE100"], "stage82_reject_inventory_verified": True,
        "stage93_linked_rcu_tree_verified": True,
        "original_exp_rcu_rejected_hunks_pending": 2,
        "original_rejected_files_remaining": 64,
        "source_modified": False,
        "rt_rcu_runtime_semantics_verified": False,
        "flash_ready": False,
    })
    return tree, inventory, s93, s95, s100, base / "report"

def run(fx: tuple[Path, ...]) -> dict:
    return M["execute"](*fx)

def require_error(action, marker: str) -> None:
    try:
        action()
    except ValueError as err:
        assert marker in str(err), (marker, str(err))
    else:
        raise AssertionError("Stage101 expected refusal: " + marker)

def adjust_reject(fx: tuple[Path, ...]) -> None:
    digest = hashlib.sha256((fx[0] / M["REJECT"]).read_bytes()).hexdigest()
    M["execute"].__globals__["REJECT_SHA"] = digest
    obj = read_json(fx[1])
    obj["entries"][0]["reject_sha256"] = digest
    put_json(fx[1], obj)

def main() -> None:
    globals_dict = M["execute"].__globals__
    old_sha = globals_dict["REJECT_SHA"]
    globals_dict["REJECT_SHA"] = SYNTH_SHA
    try:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            good = fixture(base / "valid")
            source_before = (good[0] / M["SOURCE"]).read_bytes()
            reject_before = (good[0] / M["REJECT"]).read_bytes()
            result = run(good)
            assert result["original_rcutorture_rejected_hunks_pending"] == 2
            assert result["original_rcutorture_hunk_headers"] == list(M["HEADERS"])
            assert result["e404_rcu_bh_torture_ops_present"] is True
            assert result["stage82_reject_inventory_verified"]
            assert result["stage93_unified_rcu_link_verified"]
            assert result["stage95_unified_rcu_headers_verified"]
            assert result["stage100_rcu_exp_provenance_verified"]
            assert result["original_rejected_files_remaining"] == 64
            assert result["rejected_hunks_semantically_resolved"] == 0
            assert not result["rcu_torture_runtime_verified"]
            assert not result["rt_rcu_runtime_semantics_verified"]
            assert not result["rcu_grace_period_runtime_verified"]
            assert not result["device_boot_verified"]
            assert not result["kernel_built"] and not result["flash_ready"]
            assert (good[0] / M["SOURCE"]).read_bytes() == source_before
            assert (good[0] / M["REJECT"]).read_bytes() == reject_before
            assert read_json(good[5] / M["REPORT"]) == result

            reject_sha = fixture(base / "reject-sha")
            put(reject_sha[0] / M["REJECT"], REJECT_TEXT + "extra\n")
            require_error(lambda: run(reject_sha), "reject SHA256 drift")

            bad_index = fixture(base / "index")
            o = read_json(bad_index[1])
            o["entries"][0]["hunk_count"] = 1
            put_json(bad_index[1], o)
            require_error(lambda: run(bad_index), "Stage82 RCU torture")

            bad_header = fixture(base / "header")
            put(bad_header[0] / M["REJECT"],
                REJECT_TEXT.replace(M["HEADERS"][1], "@@ bad @@"))
            adjust_reject(bad_header)
            require_error(lambda: run(bad_header), "hunk headers drift")
            globals_dict["REJECT_SHA"] = SYNTH_SHA

            bad_marker = fixture(base / "marker")
            put(bad_marker[0] / M["REJECT"],
                REJECT_TEXT.replace(M["REJECT_MARKERS"][3],
                                    "+\t.ttype = UNKNOWN_FLAVOR,"))
            adjust_reject(bad_marker)
            require_error(lambda: run(bad_marker), "torture marker drift")
            globals_dict["REJECT_SHA"] = SYNTH_SHA

            bad_source = fixture(base / "source")
            put(bad_source[0] / M["SOURCE"], "nothing\n")
            require_error(lambda: run(bad_source), "source marker missing")

            bad_stage93 = fixture(base / "stage93")
            o = read_json(bad_stage93[2])
            o["linked_rcu_exports_missing"] = ["rcu_barrier"]
            put_json(bad_stage93[2], o)
            require_error(lambda: run(bad_stage93), "Stage93 linked unified")

            bad_stage95 = fixture(base / "stage95")
            o = read_json(bad_stage95[3])
            o["vendor_unified_gp_api_declared"] = False
            put_json(bad_stage95[3], o)
            require_error(lambda: run(bad_stage95), "Stage95 unified")

            bad_stage100 = fixture(base / "stage100")
            o = read_json(bad_stage100[4])
            o["flash_ready"] = True
            put_json(bad_stage100[4], o)
            require_error(lambda: run(bad_stage100), "Stage100 expedited")

            missing_rej = fixture(base / "missing-rej")
            (missing_rej[0] / "other/00.c.rej").unlink()
            require_error(lambda: run(missing_rej), "original 64 RT")

            missing_sentinel = fixture(base / "sentinel")
            (missing_sentinel[0] / "kernel/sched/cpupri.c.rej").unlink()
            require_error(lambda: run(missing_sentinel), "original 64 RT")

            no_git = fixture(base / "git")
            (no_git[0] / ".git").rmdir()
            require_error(lambda: run(no_git), "isolated E404")
    finally:
        globals_dict["REJECT_SHA"] = old_sha
    print("EXP76_STAGE101_RCU_TORTURE_REGRESSIONS=11_NEGATIVE_PLUS_PASS; "
          "REJECT_HUNKS=2; FLASH_READY=false")

if __name__ == "__main__":
    main()
