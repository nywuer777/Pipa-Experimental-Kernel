#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 GitHub Actions / EXP76 Stage94 vendor zram RT lock ABI audit / NO FLASH
"""Classify 11 upstream RT zram rejected hunks against E404's newer lock API.

E404 uses a sleepable per-stream mutex, CPU-hotplug serialization and
wait_on_bit_lock slot locks.  The older RT patch assumes get_cpu_ptr,
spinlock_t zcomp_lock, and zram->comp, which are not the vendor API.
Never silently apply that patch or declare whole RT semantics resolved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

STAGE = "EXP76_STAGE94_ZRAM_VENDOR_LOCK_ABI_REJECT_CLASSIFICATION_NONFLASH"
INVENTORY_STAGE = "EXP76_STAGE82_OUTSTANDING_RT_REJECT_HUNK_INVENTORY_NONFLASH"
REPORT = "stage94-status.json"
REJECTS = {
    "drivers/block/zram/zcomp.c": (
        "0ef1c8f2f98fbe193de0accb44c19bf597d935ca52af60091b24bf5bb1cf1332",
        2, 11, 2, ("get_local_ptr(comp->stream)", "spin_lock(&zstrm->zcomp_lock);")
    ),
    "drivers/block/zram/zcomp.h": (
        "da7cb7ef3b0a88d874485181757209c1fac1f47fdeb7dba4321a2666144b72c3",
        1, 1, 0, ("spinlock_t zcomp_lock;",)
    ),
    "drivers/block/zram/zram_drv.c": (
        "9db66f8c2fcd065ee19a4aac3d85bf9e976704dd10ec4bddbf4ab13fd90906e7",
        7, 41, 2, ("zram_meta_init_table_locks", "zcomp_stream_get(zram->comp)")
    ),
    "drivers/block/zram/zram_drv.h": (
        "551cad7e372b3337bbf99323c9b0eacd3b6bc9e7f6d71f5b271ff8739bc8dc26",
        1, 3, 0, ("spinlock_t lock;",)
    ),
}
STRM = "drivers/block/zram/zcomp.h"
IMPL = "drivers/block/zram/zcomp.c"
ZRAM = "drivers/block/zram/zram_drv.c"
SLOTS = "drivers/block/zram/zram_drv.h"
MARKERS = {
    "vendor_stream_mutex_field": (STRM, "struct mutex lock;"),
    "vendor_stream_per_cpu_storage": (STRM, "struct zcomp_strm __percpu *stream;"),
    "vendor_stream_put_api": (STRM, "void zcomp_stream_put(struct zcomp_strm *zstrm);"),
    "vendor_stream_raw_cpu_ptr": (IMPL, "raw_cpu_ptr(comp->stream)"),
    "vendor_stream_mutex_acquire": (IMPL, "mutex_lock(&zstrm->lock);"),
    "vendor_stream_buffer_liveness_check": (IMPL, "if (likely(zstrm->buffer))"),
    "vendor_stream_mutex_retry_release": (IMPL, "mutex_unlock(&zstrm->lock);"),
    "vendor_stream_hotplug_release": (IMPL, "zcomp_strm_free(comp, zstrm);"),
    "vendor_stream_hotplug_initialization": (
        IMPL, "mutex_init(&per_cpu_ptr(comp->stream, cpu)->lock);"
    ),
    "vendor_stream_hotplug_state_registration": (
        IMPL, "cpuhp_state_add_instance(CPUHP_ZCOMP_PREPARE, &comp->node)"
    ),
    "vendor_stream_hotplug_state_removal": (
        IMPL, "cpuhp_state_remove_instance(CPUHP_ZCOMP_PREPARE, &comp->node)"
    ),
    "vendor_slot_flags": (SLOTS, "unsigned long flags;"),
    "vendor_slot_lockdep_map": (SLOTS, "struct lockdep_map dep_map;"),
    "vendor_slot_trylock_bit": (
        ZRAM, "test_and_set_bit_lock(ZRAM_ENTRY_LOCK, lock)"
    ),
    "vendor_slot_sleepable_wait": (
        ZRAM, "wait_on_bit_lock(lock, ZRAM_ENTRY_LOCK, TASK_UNINTERRUPTIBLE)"
    ),
    "vendor_slot_unlock_wakeup": (
        ZRAM, "clear_and_wake_up_bit(ZRAM_ENTRY_LOCK, lock);"
    ),
    "vendor_slot_lockdep_registration": (
        ZRAM, "zram_slot_lock_init(zram, index);"
    ),
    "vendor_compression_multi_backend": (
        ZRAM, "zram->comps[ZRAM_PRIMARY_COMP]"
    ),
    "vendor_stream_release_by_pointer": (ZRAM, "zcomp_stream_put(zstrm);"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def count_hunks(data: str) -> tuple[int, int, int]:
    lines = data.splitlines()
    hunks = [line for line in lines if line.startswith("@@ ")]
    for hunk in hunks:
        if not re.match(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@", hunk):
            raise ValueError("Stage94 unparseable original RT rejected hunk")
    plus = sum(line.startswith("+") and not line.startswith("+++") for line in lines)
    minus = sum(line.startswith("-") and not line.startswith("---") for line in lines)
    return len(hunks), plus, minus


def section(src: str, start: str, end: str, label: str) -> str:
    if src.count(start) != 1 or src.count(end) != 1:
        raise ValueError("Stage94 vendor zram function boundaries drift: " + label)
    idx = src.index(start)
    stop = src.index(end, idx + len(start))
    return src[idx:stop]


def execute(tree: Path, inventory: Path, report: Path) -> dict:
    if not (tree / ".git").is_dir():
        raise ValueError("Stage94 requires isolated pinned E404 trial Git tree")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage94 requires original 64 RT reject files")
    if not inventory.is_file():
        raise ValueError("Stage94 Stage82 immutable reject inventory missing")
    manifest = json.loads(inventory.read_text(encoding="utf-8"))
    if not (
        manifest.get("stage") == INVENTORY_STAGE
        and manifest.get("remaining_rejected_files") == 64
        and manifest.get("source_modified") is False
        and manifest.get("rejects_deleted") is False
    ):
        raise ValueError("Stage94 Stage82 inventory provenance mismatch")
    source = {}
    source_sha = {}
    rejected_sha = {}
    for relative, (digest, hunks, plus, minus, old_markers) in REJECTS.items():
        src = tree / relative
        reject = tree / (relative + ".rej")
        if not src.is_file() or not reject.is_file():
            raise ValueError("Stage94 E404 zram source or RT rejection absent: " + relative)
        if sha256(reject) != digest:
            raise ValueError("Stage94 pinned zram reject SHA256 mismatch: " + relative)
        entries = [
            e for e in manifest.get("entries", []) if e.get("source") == relative
        ]
        if not (
            len(entries) == 1
            and entries[0].get("reject_sha256") == digest
            and entries[0].get("hunk_count") == hunks
            and entries[0].get("added_lines") == plus
            and entries[0].get("removed_lines") == minus
        ):
            raise ValueError("Stage94 Stage82 zram rejected-hunk inventory drift: " + relative)
        patch = reject.read_text(encoding="utf-8")
        if count_hunks(patch) != (hunks, plus, minus):
            raise ValueError("Stage94 actual zram RT hunk counts mismatch: " + relative)
        for marker in old_markers:
            if marker not in patch:
                raise ValueError("Stage94 original zram RT ABI marker drift: " + marker)
        source[relative] = src.read_text(encoding="utf-8")
        source_sha[relative] = sha256(src)
        rejected_sha[relative] = digest
    for label, (relative, marker) in MARKERS.items():
        if marker not in source[relative]:
            raise ValueError("Stage94 E404 vendor zram concurrency contract drift: " + label)
    header = source[STRM]
    implementation = source[IMPL]
    slots = source[SLOTS]
    zram = source[ZRAM]
    get_fn = section(
        implementation,
        "struct zcomp_strm *zcomp_stream_get(struct zcomp *comp)\n",
        "void zcomp_stream_put(struct zcomp_strm *zstrm)\n",
        "zcomp_stream_get"
    )
    if any(part not in get_fn for part in (
        "for (;;) {", "raw_cpu_ptr(comp->stream)",
        "mutex_lock(&zstrm->lock);", "if (likely(zstrm->buffer))",
        "return zstrm;", "mutex_unlock(&zstrm->lock);"
    )):
        raise ValueError("Stage94 vendor zram stream migration/liveness retry drift")
    put_fn = section(
        implementation,
        "void zcomp_stream_put(struct zcomp_strm *zstrm)\n",
        "int zcomp_compress(struct zcomp *comp, struct zcomp_strm *zstrm,",
        "zcomp_stream_put"
    )
    if "mutex_unlock(&zstrm->lock);" not in put_fn:
        raise ValueError("Stage94 vendor zram stream release API drift")
    dead_fn = section(
        implementation,
        "int zcomp_cpu_dead(unsigned int cpu, struct hlist_node *node)\n",
        "static int zcomp_init(struct zcomp *comp, struct zcomp_params *params)\n",
        "zcomp_cpu_dead"
    )
    lock = dead_fn.find("mutex_lock(&zstrm->lock);")
    free = dead_fn.find("zcomp_strm_free(comp, zstrm);")
    unlock = dead_fn.find("mutex_unlock(&zstrm->lock);")
    if not (0 <= lock < free < unlock):
        raise ValueError("Stage94 hotplug stream destruction not mutex serialized")
    init_fn = section(
        implementation,
        "static int zcomp_init(struct zcomp *comp, struct zcomp_params *params)\n",
        "void zcomp_destroy(struct zcomp *comp)\n",
        "zcomp_init"
    )
    if not (
        "for_each_possible_cpu(cpu)" in init_fn
        and init_fn.index("mutex_init(&per_cpu_ptr(comp->stream, cpu)->lock);")
        < init_fn.index("cpuhp_state_add_instance(CPUHP_ZCOMP_PREPARE")
    ):
        raise ValueError("Stage94 E404 per-CPU mutex init/hotplug ordering drift")
    for old_token in ("spinlock_t zcomp_lock;", "get_local_ptr(comp->stream)",
                      "spin_lock(&zstrm->zcomp_lock);"):
        if old_token in header + implementation:
            raise ValueError("Stage94 imported incompatible older RT zcomp lock ABI")
    if "spinlock_t lock;" in slots:
        raise ValueError("Stage94 legacy RT per-slot spinlock duplicated in E404")
    for legacy in ("zram->comp)", "zcomp_stream_put(zram->comp)"):
        if legacy in zram:
            raise ValueError("Stage94 incompatible pre-E404 zram compressor API imported")
    slot_lock_fn = section(
        zram, "static void zram_slot_lock(struct zram *zram, u32 index)\n",
        "static inline bool init_done(struct zram *zram)\n",
        "zram_slot_lock/unlock"
    )
    if (
        "wait_on_bit_lock(lock, ZRAM_ENTRY_LOCK, TASK_UNINTERRUPTIBLE)" not in slot_lock_fn
        or "clear_and_wake_up_bit(ZRAM_ENTRY_LOCK, lock);" not in slot_lock_fn
        or "mutex_acquire(slot_dep_map(zram, index)" not in slot_lock_fn
        or "mutex_release(slot_dep_map(zram, index)" not in slot_lock_fn
    ):
        raise ValueError("Stage94 vendor sleepable slot-lock contract drift")
    result = {
        "stage": STAGE,
        "source_sha256": source_sha,
        "pinned_rt_reject_sha256": rejected_sha,
        "vendor_zram_lock_invariants_checked": list(MARKERS),
        "vendor_zram_lock_invariant_count": len(MARKERS),
        "reviewed_rejected_hunks": sum(x[1] for x in REJECTS.values()),
        "reviewed_rejected_files": len(REJECTS),
        "classification": "OLD_RT_PATCH_INCOMPATIBLE_WITH_E404_VENDOR_LOCK_ABI",
        "vendor_stream_mutex_and_liveness_retry_verified": True,
        "vendor_stream_cpu_hotplug_serialization_verified": True,
        "vendor_sleepable_zram_slot_bitlock_verified": True,
        "vendor_multiple_compression_backends_preserved": True,
        "source_changed": False,
        "original_rejects_deleted": False,
        "original_rejected_files_remaining": 64,
        "rt_hunks_semantically_resolved": 0,
        "rt_zram_concurrency_runtime_verified": False,
        "rt_scheduler_rcu_runtime_verified": False,
        "device_boot_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage94 original reject evidence modified")
    report.mkdir(parents=True, exist_ok=True)
    (report / REPORT).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", required=True, type=Path)
    p.add_argument("--inventory", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(
        execute(a.tree.resolve(), a.inventory.resolve(), a.report.resolve()),
        indent=2
    ))


if __name__ == "__main__":
    main()
