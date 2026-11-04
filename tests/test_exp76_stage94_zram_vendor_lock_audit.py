#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage94 E404 zram concurrency contract regressions / NO FLASH
"""Fail-closed tests for old RT zram reject ABI versus newer E404 locks."""
from __future__ import annotations

import hashlib
import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(
    str(ROOT / "tools/exp76-stage94-zram-vendor-lock-audit.py"),
    run_name="stage94_regression_helpers",
)


def put(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")


def fake_reject(path: str, spec: tuple) -> str:
    _sha, hunks, plus, minus, markers = spec
    lines = [
        f"diff --git a/{path} b/{path}",
        f"--- a/{path}", f"+++ b/{path}",
    ]
    changes = ["+" + marker for marker in markers]
    changes += ["+RT_REJECT_CONTEXT_PLACEHOLDER"] * (plus - len(changes))
    changes += ["-REMOVED_OLD_RT_PLACEHOLDER"] * minus
    for i in range(hunks):
        lines.append(f"@@ -{i+1},1 +{i+1},1 @@ rejected section")
        if i == 0:
            lines.extend(changes)
    return "\n".join(lines) + "\n"


def fixture(root: Path) -> tuple[Path, Path, Path]:
    tree = root / "trial"
    (tree / ".git").mkdir(parents=True)
    for i in range(60):
        put(tree / f"other/conflict_{i:02d}.c.rej", "@@ -1 +1 @@\n-old\n+new\n")
    specs = M["REJECTS"]
    entries = []
    for name, spec in specs.items():
        rejected = fake_reject(name, spec)
        put(tree / (name + ".rej"), rejected)
        _, hunks, plus, minus, _ = spec
        entries.append({
            "source": name,
            "reject_sha256": hashlib.sha256(rejected.encode()).hexdigest(),
            "hunk_count": hunks, "added_lines": plus, "removed_lines": minus,
        })
    put(tree / M["STRM"], (
        "struct zcomp_strm { struct mutex lock; };\n"
        "struct zcomp_strm __percpu *stream;\n"
        "void zcomp_stream_put(struct zcomp_strm *zstrm);\n"
    ))
    put(tree / M["IMPL"], (
        "struct zcomp_strm *zcomp_stream_get(struct zcomp *comp)\n"
        "{\n"
        "\tfor (;;) {\n"
        "\t\tstruct zcomp_strm *zstrm = raw_cpu_ptr(comp->stream);\n"
        "\t\tmutex_lock(&zstrm->lock);\n"
        "\t\tif (likely(zstrm->buffer))\n"
        "\t\t\treturn zstrm;\n"
        "\t\tmutex_unlock(&zstrm->lock);\n"
        "\t}\n"
        "}\n"
        "void zcomp_stream_put(struct zcomp_strm *zstrm)\n"
        "{\n\tmutex_unlock(&zstrm->lock);\n}\n"
        "int zcomp_compress(struct zcomp *comp, struct zcomp_strm *zstrm,"
        " const void *src, unsigned int *dst_len)\n{\nreturn 0;\n}\n"
        "int zcomp_cpu_dead(unsigned int cpu, struct hlist_node *node)\n"
        "{\n\tmutex_lock(&zstrm->lock);\n"
        "\tzcomp_strm_free(comp, zstrm);\n"
        "\tmutex_unlock(&zstrm->lock);\n"
        "\treturn 0;\n}\n"
        "static int zcomp_init(struct zcomp *comp, struct zcomp_params *params)\n"
        "{\n\tfor_each_possible_cpu(cpu)\n"
        "\t\tmutex_init(&per_cpu_ptr(comp->stream, cpu)->lock);\n"
        "\tcpuhp_state_add_instance(CPUHP_ZCOMP_PREPARE, &comp->node);\n"
        "\treturn 0;\n}\n"
        "void zcomp_destroy(struct zcomp *comp)\n"
        "{\n\tcpuhp_state_remove_instance(CPUHP_ZCOMP_PREPARE, &comp->node);\n}\n"
    ))
    put(tree / M["SLOTS"], (
        "struct zram_table_entry {\n"
        "\tunsigned long flags;\n"
        "\tstruct lockdep_map dep_map;\n};\n"
    ))
    put(tree / M["ZRAM"], (
        "static void zram_slot_lock_init(struct zram *zram, u32 index)\n"
        "{\n\tzram_slot_lock_init(zram, index);\n}\n"
        "static bool zram_slot_trylock(struct zram *zram, u32 index)\n"
        "{\n\treturn test_and_set_bit_lock(ZRAM_ENTRY_LOCK, lock);\n}\n"
        "static void zram_slot_lock(struct zram *zram, u32 index)\n"
        "{\n\tmutex_acquire(slot_dep_map(zram, index), 0, 0, _RET_IP_);\n"
        "\twait_on_bit_lock(lock, ZRAM_ENTRY_LOCK, TASK_UNINTERRUPTIBLE);\n}\n"
        "static void zram_slot_unlock(struct zram *zram, u32 index)\n"
        "{\n\tmutex_release(slot_dep_map(zram, index), 1, _RET_IP_);\n"
        "\tclear_and_wake_up_bit(ZRAM_ENTRY_LOCK, lock);\n}\n"
        "static inline bool init_done(struct zram *zram)\n"
        "{\n\treturn true;\n}\n"
        "void zram_compress(void)\n"
        "{\n\tx = zram->comps[ZRAM_PRIMARY_COMP];\n"
        "\tzcomp_stream_put(zstrm);\n}\n"
    ))
    index = root / "stage82.json"
    put(index, json.dumps({
        "stage": M["INVENTORY_STAGE"], "remaining_rejected_files": 64,
        "source_modified": False, "rejects_deleted": False, "entries": entries,
    }))
    return tree, index, root / "report"


def pinned() -> dict:
    original = dict(M["REJECTS"])
    for name, spec in original.items():
        data = fake_reject(name, spec)
        M["REJECTS"][name] = (hashlib.sha256(data.encode()).hexdigest(), *spec[1:])
    return original


def run(fx: tuple[Path, Path, Path]) -> dict:
    return M["execute"](*fx)


def reject(fn, phrase: str) -> None:
    try:
        fn()
    except ValueError as e:
        assert phrase in str(e), (phrase, str(e))
    else:
        raise AssertionError("Stage94 accepted invalid input: " + phrase)


def main() -> None:
    old = pinned()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = fixture(root / "good")
            before = {name: (good[0] / name).read_bytes() for name in M["REJECTS"]}
            status = run(good)
            assert status["stage"] == M["STAGE"]
            assert status["reviewed_rejected_hunks"] == 11
            assert status["reviewed_rejected_files"] == 4
            assert status["vendor_zram_lock_invariant_count"] == len(M["MARKERS"]) == 19
            assert status["vendor_stream_mutex_and_liveness_retry_verified"]
            assert status["vendor_stream_cpu_hotplug_serialization_verified"]
            assert status["vendor_sleepable_zram_slot_bitlock_verified"]
            assert status["vendor_multiple_compression_backends_preserved"]
            assert status["rt_hunks_semantically_resolved"] == 0
            assert status["original_rejected_files_remaining"] == 64
            assert status["source_changed"] is False
            assert status["original_rejects_deleted"] is False
            assert not status["rt_zram_concurrency_runtime_verified"]
            assert not status["rt_scheduler_rcu_runtime_verified"]
            assert not status["device_boot_verified"]
            assert not status["kernel_built"] and not status["flash_ready"]
            assert all((good[0] / name).read_bytes() == before[name] for name in before)
            assert json.loads((good[2] / M["REPORT"]).read_text()) == status

            broken_stream = fixture(root / "stream")
            p = broken_stream[0] / M["IMPL"]
            put(p, p.read_text().replace(
                "if (likely(zstrm->buffer))", "if (1)", 1))
            reject(lambda: run(broken_stream), "vendor_stream_buffer_liveness_check")

            broken_hotplug = fixture(root / "hotplug")
            p = broken_hotplug[0] / M["IMPL"]
            put(p, p.read_text().replace(
                "\tmutex_lock(&zstrm->lock);\n\tzcomp_strm_free",
                "\tzcomp_strm_free", 1))
            reject(lambda: run(broken_hotplug), "hotplug stream destruction")

            broken_cpu_init = fixture(root / "init")
            p = broken_cpu_init[0] / M["IMPL"]
            put(p, p.read_text().replace(
                "for_each_possible_cpu(cpu)", "for_each_online_cpu(cpu)"))
            reject(lambda: run(broken_cpu_init), "mutex init/hotplug ordering")

            broken_slot = fixture(root / "slot")
            p = broken_slot[0] / M["ZRAM"]
            put(p, p.read_text().replace(
                "wait_on_bit_lock(lock, ZRAM_ENTRY_LOCK, TASK_UNINTERRUPTIBLE)",
                "spin_lock(lock)"))
            reject(lambda: run(broken_slot), "vendor_slot_sleepable_wait")

            bad_old_spinlock = fixture(root / "old")
            p = bad_old_spinlock[0] / M["STRM"]
            put(p, p.read_text() + "spinlock_t zcomp_lock;\n")
            reject(lambda: run(bad_old_spinlock), "incompatible older RT zcomp lock ABI")

            bad_vendor_api = fixture(root / "vendor")
            p = bad_vendor_api[0] / M["ZRAM"]
            put(p, p.read_text() + "zcomp_stream_put(zram->comp);\n")
            reject(lambda: run(bad_vendor_api), "pre-E404 zram compressor API")

            wrong_hash = fixture(root / "sha")
            p = wrong_hash[0] / "drivers/block/zram/zcomp.c.rej"
            put(p, p.read_text() + "# modified\n")
            reject(lambda: run(wrong_hash), "SHA256 mismatch")

            changed_index = fixture(root / "index")
            data = json.loads(changed_index[1].read_text())
            data["entries"][0]["hunk_count"] = 3
            put(changed_index[1], json.dumps(data))
            reject(lambda: run(changed_index), "inventory drift")

            missing_git = fixture(root / "git")
            (missing_git[0] / ".git").rmdir()
            reject(lambda: run(missing_git), "isolated pinned E404")

            lost_reject = fixture(root / "lost")
            (lost_reject[0] / "other/conflict_00.c.rej").unlink()
            reject(lambda: run(lost_reject), "original 64")

            missing_index = fixture(root / "manifest")
            missing_index[1].unlink()
            reject(lambda: run(missing_index), "inventory missing")
    finally:
        M["REJECTS"].clear()
        M["REJECTS"].update(old)
    print(
        "EXP76_STAGE94_ZRAM_VENDOR_LOCK_ABI_REGRESSIONS=12_PASS; "
        "OLD_RT_HUNKS_REVIEWED=11; RUNTIME_VERIFIED=false; FLASH_READY=false"
    )


if __name__ == "__main__":
    main()
