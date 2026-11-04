#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage93 unified RCU link regressions / NO FLASH
"""Regression fixtures for old-flavor RCU drift and linked RT export contracts."""
from __future__ import annotations

import hashlib
import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(
    str(ROOT / "tools/exp76-stage93-rcu-link-contract.py"),
    run_name="stage93_regression_helpers",
)
RCU_REJECT = (
    "diff --git a/kernel/rcu/tree.c b/kernel/rcu/tree.c\n"
    "--- a/kernel/rcu/tree.c\n"
    "+++ b/kernel/rcu/tree.c\n"
    "@@ -240,6 +240,7 @@ void rcu_sched_qs(void)\n+void rcu_bh_qs(void) {}\n"
)


def put(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8")


def fixture(root: Path) -> tuple[Path, ...]:
    tree = root / "trial"
    output = root / "output"
    (tree / ".git").mkdir(parents=True)
    put(tree / M["TREE_REJECT"], RCU_REJECT)
    put(tree / "kernel/sched/cpupri.c.rej", "@@ -1 +1 @@\n-old\n+new\n")
    for i in range(62):
        put(tree / f"pending/{i:02d}.c.rej", "@@ -1 +1 @@\n-old\n+new\n")
    put(tree / "kernel/rcu/tree.c", (
        "struct rcu_state rcu_state;\n"
        "struct rcu_segcblist rcu_segcblist;\n"
        "static void rcu_core(void) {}\n"
        "void synchronize_rcu(void) {}\n"
        "void rcu_barrier(void) {}\n"
    ))
    put(tree / "kernel/rcu/tree_plugin.h", (
        "#ifndef CONFIG_RCU_FAST_NO_HZ\n"
        "void __rcu_read_lock(void) {}\n"
        "void __rcu_read_unlock(void) {}\n"
        "static void rcu_preempt_deferred_qs(void) {}\n"
        "static void rcu_read_unlock_special(void) {}\n"
        "#endif\n"
    ))
    put(tree / "kernel/rcu/update.c", (
        "#ifndef CONFIG_PREEMPT_RT_FULL\n"
        "int rcu_read_lock_bh_held(void) { return 1; }\n"
        "EXPORT_SYMBOL_GPL(rcu_read_lock_bh_held);\n"
        "#endif\n"
    ))
    put(tree / "include/linux/rcupdate.h", (
        "#ifdef CONFIG_PREEMPT_RT_FULL\n"
        "static inline int rcu_read_lock_bh_held(void)\n"
        "{\n\treturn rcu_read_lock_held();\n}\n"
        "#endif\n"
        "static inline void synchronize_rcu_bh(void)\n"
        "{\n\tsynchronize_rcu();\n}\n"
        "static inline void rcu_barrier_bh(void)\n"
        "{\n\trcu_barrier();\n}\n"
        "static inline void call_rcu_bh(struct rcu_head *head, rcu_callback_t func)\n"
        "{\n\tcall_rcu(head, func);\n}\n"
    ))
    put(tree / "include/linux/rcutree.h", "void rcu_barrier(void);\n")
    index = root / "stage82.json"
    put(index, json.dumps({
        "stage": M["INDEX_STAGE"], "remaining_rejected_files": 64,
        "source_modified": False, "rejects_deleted": False,
        "entries": [{
            "source": "kernel/rcu/tree.c",
            "reject_sha256": hashlib.sha256(RCU_REJECT.encode()).hexdigest(),
            "hunk_count": M["TREE_REJECT_HUNKS"],
        }],
    }))
    put(output / ".config", "CONFIG_SMP=y\nCONFIG_PREEMPT_RT_FULL=y\n")
    put(output / "vmlinux", b"\x7fELF" + bytes(8192))
    put(output / "System.map", "".join(
        f"ffff80000000{i:04x} T {name}\n"
        for i, name in enumerate(M["EXPORTS"])
    ))
    stage47 = root / "stage47.json"
    put(stage47, json.dumps({
        "stage": M["STAGE47"], "applied": True,
        "rcu_postpatch_preprocessor_balanced": True,
        "remaining_rejected_files": 64,
        "rcu_runtime_verified": False,
    }))
    stage92 = root / "stage92.json"
    put(stage92, json.dumps({
        "stage": M["STAGE92"],
        "arm64_stage86_image_link_verified": True,
        "smp_preempt_rt_full_config_verified": True,
        "system_map_symbols_missing": [],
        "verification_scope": "SOURCE_AND_LINK_ONLY",
        "remaining_rejected_files": 64, "device_boot_verified": False,
        "system_map_sha256": hashlib.sha256((output / "System.map").read_bytes()).hexdigest(),
        "vmlinux_elf_sha256": hashlib.sha256((output / "vmlinux").read_bytes()).hexdigest(),
    }))
    return tree, output, index, stage47, stage92, root / "report"


def run(fx: tuple[Path, ...]) -> dict:
    return M["execute"](*fx)


def expect_failure(fn, phrase: str) -> None:
    try:
        fn()
    except ValueError as err:
        assert phrase in str(err), (phrase, str(err))
    else:
        raise AssertionError("Stage93 should reject " + phrase)


def modify_json(path: Path, field: str, value) -> None:
    obj = json.loads(path.read_text(encoding="utf-8"))
    obj[field] = value
    put(path, json.dumps(obj))


def main() -> None:
    original_sha = M["execute"].__globals__["TREE_REJECT_SHA"]
    M["execute"].__globals__["TREE_REJECT_SHA"] = hashlib.sha256(
        RCU_REJECT.encode()
    ).hexdigest()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = fixture(root / "good")
            before = {
                p: (good[0] / p).read_bytes() for p in M["PATHS"]
            }
            result = run(good)
            assert result["stage"] == M["STAGE"]
            assert result["rt_config_verified"]
            assert result["stage47_rcu_preprocessor_guard_proven"]
            assert result["stage92_linked_kernel_proven"]
            assert result["unified_rcu_source_invariant_count"] == len(M["CHECKS"]) == 12
            assert result["unified_rcu_bh_forwarders"] == M["FORWARDERS"]
            assert result["linked_rcu_exports_present"] == list(M["EXPORTS"])
            assert result["linked_rcu_exports_missing"] == []
            assert result["original_rcu_tree_rejected_hunks_pending"] == 18
            assert result["original_rejected_files_remaining"] == 64
            assert result["verification_scope"] == "SOURCE_AND_LINK_ONLY"
            assert not result["rt_rcu_runtime_semantics_verified"]
            assert not result["rcu_grace_period_runtime_verified"]
            assert not result["device_boot_verified"]
            assert not result["kernel_built"] and not result["flash_ready"]
            assert all((good[0] / p).read_bytes() == before[p] for p in before)
            assert json.loads((good[5] / M["REPORT"]).read_text()) == result

            missing_export = fixture(root / "export")
            mp = missing_export[1] / "System.map"
            put(mp, mp.read_text().replace(" T rcu_barrier", " T absent_rcu_barrier"))
            expect_failure(lambda: run(missing_export), "RCU exports absent")

            legacy = fixture(root / "legacy")
            p = legacy[0] / "kernel/rcu/tree.c"
            put(p, p.read_text() + "\nstruct rcu_state rcu_bh_state;\n")
            expect_failure(lambda: run(legacy), "legacy RCU flavor")

            broken_forward = fixture(root / "forward")
            p = broken_forward[0] / "include/linux/rcupdate.h"
            put(p, p.read_text().replace("\tsynchronize_rcu();", "\tlegacy_synchronize_rcu();"))
            expect_failure(lambda: run(broken_forward), "forwarding drift")

            broken_lockdep = fixture(root / "lockdep")
            p = broken_lockdep[0] / "include/linux/rcupdate.h"
            put(p, p.read_text().replace("return rcu_read_lock_held();", "return 1;"))
            expect_failure(lambda: run(broken_lockdep), "rt_lockdep_forward")

            missing_guard = fixture(root / "guard")
            p = missing_guard[0] / "kernel/rcu/update.c"
            put(p, p.read_text().replace("#ifndef CONFIG_PREEMPT_RT_FULL", "#if 1"))
            expect_failure(lambda: run(missing_guard), "unguarded")

            unbalanced = fixture(root / "preproc")
            p = unbalanced[0] / "kernel/rcu/tree_plugin.h"
            put(p, p.read_text() + "\n#ifdef CONFIG_UNKNOWN\n")
            expect_failure(lambda: run(unbalanced), "unclosed preprocessor")

            wrong_stage47 = fixture(root / "stage47")
            modify_json(wrong_stage47[3], "rcu_postpatch_preprocessor_balanced", False)
            expect_failure(lambda: run(wrong_stage47), "Stage47 conditional audit")

            wrong_stage92 = fixture(root / "stage92")
            modify_json(wrong_stage92[4], "arm64_stage86_image_link_verified", False)
            expect_failure(lambda: run(wrong_stage92), "ARM64 linked baseline")

            wrong_config = fixture(root / "config")
            put(wrong_config[1] / ".config", "CONFIG_SMP=y\nCONFIG_PREEMPT=y\n")
            expect_failure(lambda: run(wrong_config), "real PREEMPT_RT_FULL SMP")

            missing_elf = fixture(root / "elf")
            put(missing_elf[1] / "vmlinux", b"BAD!" + bytes(800))
            expect_failure(lambda: run(missing_elf), "vmlinux ELF missing")

            reject_drift = fixture(root / "reject")
            put(reject_drift[0] / M["TREE_REJECT"], RCU_REJECT + "drift\n")
            expect_failure(lambda: run(reject_drift), "rejection SHA256 drift")

            wrong_inventory = fixture(root / "inventory")
            obj = json.loads(wrong_inventory[2].read_text())
            obj["entries"][0]["hunk_count"] = 17
            put(wrong_inventory[2], json.dumps(obj))
            expect_failure(lambda: run(wrong_inventory), "Stage82 RCU reject provenance")

            changed_system_map = fixture(root / "map-sha")
            modify_json(changed_system_map[4], "system_map_sha256", "e" * 64)
            expect_failure(lambda: run(changed_system_map), "System.map drift")

            missing_rej = fixture(root / "reject-count")
            (missing_rej[0] / "pending/00.c.rej").unlink()
            expect_failure(lambda: run(missing_rej), "original 64 RT rejects")

    finally:
        M["execute"].__globals__["TREE_REJECT_SHA"] = original_sha
    print(
        "EXP76_STAGE93_RCU_SOURCE_LINK_REGRESSIONS=15_PASS; "
        "EXPORTS=4; RCU_TREE_REJECT_HUNKS=18; FLASH_READY=false"
    )


if __name__ == "__main__":
    main()
