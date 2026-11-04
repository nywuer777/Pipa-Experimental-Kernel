#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage20 RT header ABI reconciliation / NO FLASH
"""Port the pinned swap.h locallock reject and guard non-RT rwsem owner accesses.

Stage19 selected rwsem_rt.h under PREEMPT_RT_FULL. That struct has no owner.
Keep E404's owner hints on non-RT. Affinity, sleeping_lock lifecycle and
the RCU pointer macro warning remain unverified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SWAP = "include/linux/swap.h"
PERCPU = "include/linux/percpu-rwsem.h"
RT_HEADER = "include/linux/rwsem_rt.h"
LOCALLOCK = "include/linux/locallock.h"
SWAP_REJECT_SHA256 = "445ee7f190e53347b5d25fbbcc9e29ba37a946763323743de2b9044ec8261370"
SWAP_REJECT = (
    "diff a/include/linux/swap.h b/include/linux/swap.h\t(rejected hunks)\n"
    "@@ -12,6 +12,7 @@\n"
    " #include <linux/fs.h>\n"
    " #include <linux/atomic.h>\n"
    " #include <linux/page-flags.h>\n"
    "+#include <linux/locallock.h>\n"
    " #include <asm/page.h>\n"
    " \n"
    " struct notifier_block;\n"
)
SWAP_OLD = "#include <linux/page-flags.h>\n#include <asm/page.h>\n"
SWAP_NEW = (
    "#include <linux/page-flags.h>\n"
    "#include <linux/locallock.h>\n"
    "#include <asm/page.h>\n"
)
OWNER_GUARD = "#ifdef CONFIG_RWSEM_SPIN_ON_OWNER\n"
NONRT_OWNER_GUARD = (
    "#if defined(CONFIG_RWSEM_SPIN_ON_OWNER) && !defined(CONFIG_PREEMPT_RT_FULL)\n"
)


def exactly(src: str, fragment: str, count: int, target: str) -> None:
    actual = src.count(fragment)
    if actual != count:
        raise ValueError(f"{target}: expected {count} copies of {fragment!r}, got {actual}")


def prepare(root: Path) -> dict[str, str]:
    paths = [SWAP, PERCPU, RT_HEADER, LOCALLOCK, SWAP + ".rej"]
    for rel in paths:
        if not (root / rel).is_file():
            raise ValueError("Missing Stage19 source or unresolved RT reject: " + rel)
    rejects_before = len(list(root.rglob("*.rej")))
    if rejects_before != 65:
        raise ValueError(f"Expected Stage19 65 rejected files, found {rejects_before}")

    rej = (root / (SWAP + ".rej")).read_bytes()
    actual_sha = hashlib.sha256(rej).hexdigest()
    if actual_sha != SWAP_REJECT_SHA256 or rej.decode("utf-8") != SWAP_REJECT:
        raise ValueError("Unrecognized RT swap.h include reject: " + actual_sha)

    local_lock = (root / LOCALLOCK).read_text(encoding="utf-8")
    exactly(local_lock, "#define DECLARE_LOCAL_IRQ_LOCK(lvar)", 2, LOCALLOCK)
    swap = (root / SWAP).read_text(encoding="utf-8")
    exactly(swap, SWAP_OLD, 1, SWAP)
    exactly(swap, "DECLARE_LOCAL_IRQ_LOCK(swapvec_lock);", 1, SWAP)
    if "#include <linux/locallock.h>" in swap:
        raise ValueError("locallock already included in swap.h")

    rt = (root / RT_HEADER).read_text(encoding="utf-8")
    exactly(rt, "struct rw_semaphore {", 1, RT_HEADER)
    if "atomic_long_t owner;" in rt or "RWSEM_OWNER_UNKNOWN" in rt:
        raise ValueError("Unexpected RT rwsem owner interface")

    percpu = (root / PERCPU).read_text(encoding="utf-8")
    exactly(percpu, OWNER_GUARD, 2, PERCPU)
    exactly(percpu, "atomic_long_set(&sem->rw_sem.owner, RWSEM_OWNER_UNKNOWN);", 1, PERCPU)
    exactly(percpu, "atomic_long_set(&sem->rw_sem.owner, (long)current);", 1, PERCPU)
    for fragment in ("lock_release(&sem->rw_sem.dep_map, 1, ip);",
                     "lock_acquire(&sem->rw_sem.dep_map, 0, 1, read, 1, NULL, ip);"):
        exactly(percpu, fragment, 1, PERCPU)
    if NONRT_OWNER_GUARD in percpu:
        raise ValueError("percpu-rwsem.h is already Stage20 guarded")

    return {
        SWAP: swap.replace(SWAP_OLD, SWAP_NEW, 1),
        PERCPU: percpu.replace(OWNER_GUARD, NONRT_OWNER_GUARD),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = p.parse_args()
    root = args.tree.resolve()
    updated = prepare(root)
    if args.mode == "apply":
        for rel, body in updated.items():
            (root / rel).write_text(body, encoding="utf-8")
        (root / (SWAP + ".rej")).unlink()
    remaining = len(list(root.rglob("*.rej")))
    if remaining != (64 if args.mode == "apply" else 65):
        raise ValueError("Stage20 reject count mismatch: " + str(remaining))
    status = {
        "stage": "EXP76_RT_STAGE20_SWAP_LOCALLOCK_AND_PERCPU_RWSEM_ABI",
        "applied": args.mode == "apply",
        "swap_locallock_reject_sha256": SWAP_REJECT_SHA256,
        "swap_locallock_include_ported": args.mode == "apply",
        "percpu_owner_access_non_rt_only": args.mode == "apply",
        "remaining_rejected_files": remaining,
        "rcu_assign_pointer_warning_pending": True,
        "scheduler_affinity_abi_pending": True,
        "sleeping_lock_lifecycle_review_required": True,
        "objects_compiled": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    report = args.report.resolve()
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage20-status.json").write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
