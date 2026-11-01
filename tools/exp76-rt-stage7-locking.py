#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage7 locking Kbuild + percpu-rwsem RT port
"""Reconcile two SHA-locked RT rejects in a temporary kernel source checkout.

Keep vendor Kbuild objects non-RT-only, add RT-specific locking objects,
and recognize the already-present rcuwait_wait_event state argument.
No compilation, no boot image, no flash.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

MAKE = "kernel/locking/Makefile"
RWSEM = "kernel/locking/percpu-rwsem.c"
EXPECTED = {
    MAKE: "54a73eaacf53f52659ff9679da3acc6f51a9e73973bbe3ca6e58dd498da04896",
    RWSEM: "d344f32ffd3b6b36199be57c71530d7b39b2b619b2ebfbe85f0f015d59c8296b",
}
UPSTREAM_RT_OBJS = "obj-$(CONFIG_PREEMPT_RT_FULL) += mutex-rt.o rwsem-rt.o rwlock-rt.o\n"
RT_BLOCK = (
    "obj-y += semaphore.o percpu-rwsem.o\n"
    "ifneq ($(CONFIG_PREEMPT_RT_FULL),y)\n"
    "obj-y += mutex.o rwsem.o\n"
    "endif\n"
)
LEGACY_START = "obj-y += mutex.o semaphore.o rwsem.o percpu-rwsem.o\n"
SEM_PAIR = (
    "obj-$(CONFIG_RWSEM_GENERIC_SPINLOCK) += rwsem-spinlock.o\n"
    "obj-$(CONFIG_RWSEM_XCHGADD_ALGORITHM) += rwsem-xadd.o\n"
)


def prepare(tree: Path):
    for name, digest in EXPECTED.items():
        src = tree / name
        rej = tree / (name + ".rej")
        if not src.is_file() or not rej.is_file():
            raise ValueError("Missing pinned source/reject: " + name)
        got = hashlib.sha256(rej.read_bytes()).hexdigest()
        if got != digest:
            raise ValueError("Rejected hunk hash mismatch " + name + ": " + got)

    for name in ("mutex-rt.c", "rwsem-rt.c", "rwlock-rt.c"):
        if not (tree / "kernel/locking" / name).is_file():
            raise ValueError("Missing RT locking implementation: " + name)

    path = tree / MAKE
    before = path.read_text(encoding="utf-8")
    if UPSTREAM_RT_OBJS in before:
        raise ValueError("RT locking objects already linked; source drift")
    if before.count("obj-$(CONFIG_QUEUED_RWLOCKS) += qrwlock.o\n") != 1:
        raise ValueError("Cannot identify RT link insertion point")
    if before.count(LEGACY_START) == 1:
        candidate = before.replace(LEGACY_START, RT_BLOCK, 1)
        legacy_layout = "replaced-unconditional-legacy-locking"
    elif before.count(RT_BLOCK) == 1 and LEGACY_START not in before:
        candidate = before
        legacy_layout = "upstream-RT-guard-already-applied"
    else:
        raise ValueError("Unexpected mutex.o/rwsem.o build guard layout; source excerpt:\n" + "\n".join(f"{i+1:02d}: {line}" for i, line in enumerate(before.splitlines()[:55])))

    # The vendor tree may not contain generic rwsem-algorithm objects.
    # Do not invent entries for absent source/config variants.
    if candidate.count(SEM_PAIR) == 1:
        candidate = candidate.replace(
            SEM_PAIR, "ifneq ($(CONFIG_PREEMPT_RT_FULL),y)\n" + SEM_PAIR + "endif\n", 1
        )
        generic_state = "guarded-existing-generic-algorithms"
    elif ("CONFIG_RWSEM_GENERIC_SPINLOCK" not in candidate
          and "CONFIG_RWSEM_XCHGADD_ALGORITHM" not in candidate):
        generic_state = "vendor-source-has-no-generic-algorithm-objects"
    else:
        raise ValueError("Unrecognized generic rwsem Makefile layout")

    insertion = "obj-$(CONFIG_QUEUED_RWLOCKS) += qrwlock.o\n"
    candidate = candidate.replace(insertion, UPSTREAM_RT_OBJS + insertion, 1)
    if candidate.count(UPSTREAM_RT_OBJS) != 1 or candidate.count(RT_BLOCK) != 1:
        raise ValueError("RT locking object/legacy guard not unique")

    rwsem = (tree / RWSEM).read_text(encoding="utf-8")
    expected_call = (
        "rcuwait_wait_event(&sem->writer, readers_active_check(sem), "
        "TASK_UNINTERRUPTIBLE);"
    )
    if rwsem.count(expected_call) != 1:
        raise ValueError("Vendor percpu rwsem already-compatible call not found")
    if "rcuwait_wait_event(&sem->writer, readers_active_check(sem));" in rwsem:
        raise ValueError("Found legacy two-argument rcuwait call")
    rcuwait = (tree / "include/linux/rcuwait.h").read_text(encoding="utf-8")
    if "#define rcuwait_wait_event(w, condition, state)" not in rcuwait:
        raise ValueError("rcuwait API does not accept TASK_UNINTERRUPTIBLE")
    if not re.search(r"\bTASK_UNINTERRUPTIBLE\b", rwsem):
        raise ValueError("Missing wait state")
    return candidate, legacy_layout, generic_state


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tree", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--mode", choices=("verify", "apply"), required=True)
    a = p.parse_args()
    tree = a.tree.resolve()
    candidate, legacy_layout, generic_state = prepare(tree)
    if a.mode == "apply":
        (tree / MAKE).write_text(candidate, encoding="utf-8")
        for relative in EXPECTED:
            (tree / (relative + ".rej")).unlink()

    remaining = len(list(tree.rglob("*.rej")))
    report = {
        "stage": "EXP76_RT_STAGE7_PARTIAL_SOURCE_ONLY",
        "mode": a.mode,
        "locking_makefile_port": a.mode == "apply",
        "legacy_locking": legacy_layout,
        "generic_rwsem": generic_state,
        "rt_locking_objects": ["mutex-rt.o", "rwsem-rt.o", "rwlock-rt.o"],
        "percpu_rcuwait_3arg_already_in_vendor": True,
        "remaining_rejected_files": remaining,
        "kernel_compiled": False,
        "rt_config_enabled": False,
        "flash_ready": False
    }
    a.report.mkdir(parents=True, exist_ok=True)
    (a.report / "stage7-result.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    if a.mode == "apply" and remaining != 71:
        raise SystemExit("FAIL_CLOSED: expected 71 remaining rejected files")


if __name__ == "__main__":
    main()
