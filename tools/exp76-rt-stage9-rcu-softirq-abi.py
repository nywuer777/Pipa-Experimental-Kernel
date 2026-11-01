#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 RCU-softirq API generation gate / NO FLASH
"""Identify incompatibility between RT 4.19.325 RCU and E404 newer RCU.

This tool does not apply PREEMPT_RT: it ensures an old-flavor RCU diff
is never misrepresented as a semantic port into E404's new-flavor tree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

CHECKS = {
    "kernel/rcu/tree.c": {
        "new_generation_required": (
            "struct rcu_state rcu_state",
            "rcu_segcblist",
            "rcu_preempt_deferred_qs",
            "rcu_softirq_qs",
            "rcu_core",
        ),
        "old_flavor_forbidden": (
            "rcu_bh_state",
            "rcu_sched_state",
            "for_each_rcu_flavor",
        ),
    },
    "kernel/softirq.c": {
        "new_generation_required": ("DEFINE_PER_CPU(__u32, active_softirqs)",),
        "old_flavor_forbidden": (),
    },
}
ABI_PROBES = {
    "include/linux/sched.h": (
        "softirqs_raised",
        "sleeping_lock",
        "pi_blocked_on",
        "CONFIG_PREEMPT_RT_FULL",
    ),
    "kernel/softirq.c": (
        "ktimer_softirqd",
        "softirq_check_pending_idle",
        "run_ksoftirqd",
        "softirq_set_runner",
        "CONFIG_PREEMPT_RT_FULL",
    ),
    "kernel/rcu/tree.c": (
        "rcu_bh_qs",
        "rcu_softirq_qs",
        "rcu_cpu_kthread",
        "rcu_segcblist",
        "rcu_core",
    ),
}


def inspect(tree: Path) -> dict:
    texts = {}
    paths = set(CHECKS) | set(ABI_PROBES) | {"include/linux/irq_work.h"}
    for path in paths:
        candidate = tree / path
        if not candidate.is_file():
            raise ValueError("Missing kernel source: " + path)
        texts[path] = candidate.read_text(encoding="utf-8")
    results = {}
    for path, requirements in CHECKS.items():
        data = texts[path]
        required = {token: data.count(token) for token in requirements["new_generation_required"]}
        forbidden = {token: data.count(token) for token in requirements["old_flavor_forbidden"]}
        if any(v == 0 for v in required.values()) or any(v != 0 for v in forbidden.values()):
            raise ValueError(
                "E404 API generation has changed; inspect source instead of auto-port: "
                + json.dumps({"path": path, "required": required, "forbidden": forbidden})
            )
        results[path] = {
            "sha256": hashlib.sha256((tree / path).read_bytes()).hexdigest(),
            "new_generation_symbols": required,
            "obsolete_rt140_symbols_absent": forbidden,
        }
    probes = {
        path: {symbol: texts[path].count(symbol) for symbol in symbols}
        for path, symbols in ABI_PROBES.items()
    }
    rej = tree / "kernel/rcu/tree.c.rej"
    if not rej.is_file():
        raise ValueError("Expected RCU 18-hunk reject still required")
    hunks = len(re.findall(r"(?m)^@@ -\d+", rej.read_text(encoding="utf-8")))
    if hunks != 18:
        raise ValueError(f"Expected 18 unresolved RCU hunks, got {hunks}")
    irq = texts["include/linux/irq_work.h"]
    if "atomic_t flags;" not in irq:
        raise ValueError("Vendor IRQ work flags type changed")
    return {
        "stage": "EXP76_RT_STAGE9_RCU_SOFTIRQ_GENERATION_GATE",
        "rcu_reject_hunks_pending": hunks,
        "rcu_compatibility": results,
        "post_patch_abi_probes": probes,
        "rt140_rcu_blind_port_permitted": False,
        "softirq_port_pending": True,
        "rcu_port_pending": True,
        "kernel_compiled": False,
        "rt_enabled": False,
        "flash_ready": False,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    a = p.parse_args()
    result = inspect(a.tree.resolve())
    a.report.mkdir(parents=True, exist_ok=True)
    (a.report / "stage9-api-generation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("EXP76_RT_STAGE9=RCU_SOFTIRQ_GENERATION_AUDITED; PORT_NOT_COMPLETE; FLASH_READY=false")


if __name__ == "__main__":
    main()
