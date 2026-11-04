#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage95 RCU header provenance regressions / NO FLASH
"""Synthetic reject inventories and unified RCU header contract failures."""
from __future__ import annotations
import hashlib
import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(
    str(ROOT / "tools/exp76-stage95-rcu-headers-audit.py"),
    run_name="stage95_fixture",
)
HEADERS = M["HEADERS"]


def put(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def reject_text(relative: str) -> str:
    spec = HEADERS[relative]
    chunks = [
        "diff --git a/" + relative + " b/" + relative,
        "--- a/" + relative,
        "+++ b/" + relative,
    ]
    added = list(spec["new"])
    removed = list(spec["old"])
    added += ["+/* RT check */"] * (spec["add"] - len(added))
    removed += ["-/* old RCU flavor */"] * (spec["remove"] - len(removed))
    for n, header in enumerate(spec["headers"]):
        chunks.append(header + " context")
        if n == 0:
            chunks.extend(added)
            chunks.extend(removed)
    return "\n".join(chunks) + "\n"


def fixture(root: Path) -> tuple[Path, Path, Path, Path]:
    tree = root / "trial"
    (tree / ".git").mkdir(parents=True)
    for i in range(61):
        put(tree / f"legacy/other-{i:02d}.rej", "@@ -1 +1 @@\n-old\n+new\n")
    put(tree / "kernel/sched/cpupri.c.rej", "@@ -1 +1 @@\n-old\n+new\n")
    entries = []
    for path, spec in HEADERS.items():
        rejected = reject_text(path)
        put(tree / (path + ".rej"), rejected)
        entries.append({
            "source": path,
            "reject_sha256": hashlib.sha256(rejected.encode()).hexdigest(),
            "hunk_count": spec["hunks"],
            "added_lines": spec["add"],
            "removed_lines": spec["remove"],
        })
    put(tree / "kernel/rcu/rcu.h", (
        "#ifdef CONFIG_TINY_RCU\n"
        "static inline unsigned long rcu_get_gp_seq(void) { return 0; }\n"
        "static inline void rcu_force_quiescent_state(void) { }\n"
        "#else\n"
        "unsigned long rcu_get_gp_seq(void);\n"
        "void rcu_force_quiescent_state(void);\n"
        "#endif\n"
    ))
    put(tree / "kernel/rcu/tree.h", (
        "static void rcu_cpu_kthread_setup(unsigned int cpu);\n"
        "static void rcu_prepare_kthreads(int cpu);\n"
        "static bool rcu_is_callbacks_kthread(void);\n"
        "static void rcu_preempt_boost_start_gp(struct rcu_node *rnp);\n"
    ))
    put(tree / "kernel/rcu/tree.c", (
        "struct rcu_segcblist rcu_segcblist;\n"
        "void rcu_barrier(void) {}\n"
        "void synchronize_rcu(void) {}\n"
    ))
    index = root / "stage82.json"
    put(index, json.dumps({
        "stage": M["INVENTORY_STAGE"],
        "remaining_rejected_files": 64,
        "source_modified": False, "rejects_deleted": False,
        "entries": entries,
    }))
    stage93 = root / "stage93.json"
    put(stage93, json.dumps({
        "stage": M["STAGE93"],
        "rt_config_verified": True,
        "linked_rcu_exports_missing": [],
        "linked_rcu_exports_present": [
            "synchronize_rcu", "rcu_barrier",
            "__rcu_read_lock", "__rcu_read_unlock",
        ],
        "original_rcu_tree_rejected_hunks_pending": 18,
        "original_rejected_files_remaining": 64,
        "verification_scope": "SOURCE_AND_LINK_ONLY",
        "rt_rcu_runtime_semantics_verified": False,
    }))
    return tree, index, stage93, root / "report"


def run(fx: tuple[Path, ...]):
    return M["execute"](*fx)


def reject(fn, reason: str) -> None:
    try:
        fn()
    except ValueError as exc:
        assert reason in str(exc), str(exc)
    else:
        raise AssertionError("Stage95 invalid state accepted: " + reason)


def main() -> None:
    original = {
        path: dict(spec) for path, spec in HEADERS.items()
    }
    for path, spec in HEADERS.items():
        spec["sha"] = hashlib.sha256(reject_text(path).encode()).hexdigest()
    try:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            good = fixture(root / "good")
            source_before = {
                path: (good[0] / path).read_bytes()
                for path in (*HEADERS, M["TREE"])
            }
            data = run(good)
            assert data["stage"] == M["STAGE"]
            assert data["reviewed_original_rcu_header_rejected_files"] == 2
            assert data["reviewed_original_rcu_header_rejected_hunks"] == 5
            assert data["vendor_unified_gp_api_declared"]
            assert data["vendor_rcu_kthread_setup_declared"]
            assert data["obsolete_legacy_rcu_flavor_api_absent"]
            assert data["tiny_rcu_stub_path_preserved"]
            assert data["stage93_linked_rcu_exports_verified"]
            assert data["source_modified"] is False
            assert data["original_rejects_deleted"] is False
            assert data["original_rejected_files_remaining"] == 64
            assert data["rcu_header_hunks_runtime_semantics_resolved"] == 0
            assert not data["rt_rcu_runtime_semantics_verified"]
            assert not data["device_boot_verified"]
            assert not data["kernel_built"] and not data["flash_ready"]
            assert all(
                (good[0] / path).read_bytes() == source_before[path]
                for path in source_before
            )
            assert json.loads((good[3] / M["REPORT"]).read_text()) == data

            wrong_hash = fixture(root / "hash")
            p = wrong_hash[0] / "kernel/rcu/tree.h.rej"
            put(p, p.read_text() + "# drift\n")
            reject(lambda: run(wrong_hash), "SHA256 mismatch")

            wrong_inventory = fixture(root / "inventory")
            obj = json.loads(wrong_inventory[1].read_text())
            obj["entries"][0]["hunk_count"] = 8
            put(wrong_inventory[1], json.dumps(obj))
            reject(lambda: run(wrong_inventory), "provenance mismatch")

            old_bh = fixture(root / "legacy-bh")
            p = old_bh[0] / "kernel/rcu/rcu.h"
            put(p, p.read_text() + "void rcu_bh_force_quiescent_state(void);\n")
            reject(lambda: run(old_bh), "old-flavor RCU ABI reintroduced")

            old_callbacks = fixture(root / "legacy-callback")
            p = old_callbacks[0] / "kernel/rcu/tree.h"
            put(p, p.read_text() + "static void invoke_rcu_callbacks_kthread(void);\n")
            reject(lambda: run(old_callbacks), "old-flavor RCU ABI reintroduced")

            missing_setup = fixture(root / "kthread")
            p = missing_setup[0] / "kernel/rcu/tree.h"
            put(p, p.read_text().replace(
                "static void rcu_cpu_kthread_setup(unsigned int cpu);", ""
            ))
            reject(lambda: run(missing_setup), "unified E404 RCU source contract drift")

            lost_gp = fixture(root / "gp")
            p = lost_gp[0] / "kernel/rcu/rcu.h"
            put(p, p.read_text().replace("void rcu_force_quiescent_state(void);", ""))
            reject(lambda: run(lost_gp), "unified E404 RCU source contract drift")

            lost_tiny = fixture(root / "tiny")
            p = lost_tiny[0] / "kernel/rcu/rcu.h"
            put(p, p.read_text().replace("#ifdef CONFIG_TINY_RCU", "#if 1"))
            reject(lambda: run(lost_tiny), "tiny/tree API variant drift")

            boost_guard = fixture(root / "boost")
            p = boost_guard[0] / "kernel/rcu/tree.h"
            put(p, p.read_text() + "#ifdef CONFIG_RCU_BOOST\n")
            reject(lambda: run(boost_guard), "obsolete RCU_BOOST guard")

            legacy_flavor = fixture(root / "flavor")
            p = legacy_flavor[0] / "kernel/rcu/tree.c"
            put(p, p.read_text() + "struct rcu_state rcu_bh_state;\n")
            reject(lambda: run(legacy_flavor), "old-flavor RCU ABI reintroduced")

            bad_stage93 = fixture(root / "stage93")
            obj = json.loads(bad_stage93[2].read_text())
            obj["linked_rcu_exports_missing"] = ["rcu_barrier"]
            put(bad_stage93[2], json.dumps(obj))
            reject(lambda: run(bad_stage93), "Stage93 unified RCU link contract")

            missing_rej = fixture(root / "reject-count")
            (missing_rej[0] / "legacy/other-00.rej").unlink()
            reject(lambda: run(missing_rej), "64 RT rejects")

            missing_git = fixture(root / "git")
            (missing_git[0] / ".git").rmdir()
            reject(lambda: run(missing_git), "isolated E404 checkout")

    finally:
        HEADERS.clear()
        HEADERS.update(original)
    print(
        "EXP76_STAGE95_RCU_HEADERS_REGRESSIONS=13_PASS; "
        "REJECTED_HUNKS_REVIEWED=5; LEGACY_PORT_NOT_APPLIED; FLASH_READY=false"
    )


if __name__ == "__main__":
    main()
