#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 RT Stage12 rcupdate lockdep ABI / NO FLASH
"""Port the RT-conditional RCU-bh lockdep helper on newer E404 RCU.

The E404 call_rcu_bh() wrapper already forwards to call_rcu() independent
of RT config. Only the CONFIG_DEBUG_LOCK_ALLOC declaration needs a new
RT-specific wrapper, matching the already-applied guard in update.c.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

SOURCE = "include/linux/rcupdate.h"
REJECT_SHA256 = "f04f5a3c8feb733936d49bc13eda109f6a213c0867659282a455f7851914ce56"
EXPECTED = "int rcu_read_lock_held(void);\nint rcu_read_lock_bh_held(void);\nint rcu_read_lock_sched_held(void);\n"
REPLACEMENT = (
    "int rcu_read_lock_held(void);\n"
    "#ifdef CONFIG_PREEMPT_RT_FULL\n"
    "static inline int rcu_read_lock_bh_held(void)\n"
    "{\n"
    "\treturn rcu_read_lock_held();\n"
    "}\n"
    "#else\n"
    "int rcu_read_lock_bh_held(void);\n"
    "#endif\n"
    "int rcu_read_lock_sched_held(void);\n"
)
CALL_WRAPPER = (
    "static inline void call_rcu_bh(struct rcu_head *head, rcu_callback_t func)\n"
    "{\n"
    "\tcall_rcu(head, func);\n"
    "}\n"
)


def plan(root: Path):
    source = root / SOURCE
    reject = root / (SOURCE + ".rej")
    update = root / "kernel/rcu/update.c"
    for path in (source, reject, update):
        if not path.is_file():
            raise ValueError("Required pinned E404 source/reject missing: " + str(path))
    digest = hashlib.sha256(reject.read_bytes()).hexdigest()
    if digest != REJECT_SHA256:
        raise ValueError("Wrong rcupdate.h rejected patch SHA256: " + digest)
    patch = reject.read_text(encoding="utf-8")
    if len(re.findall(r"(?m)^@@ -\d+", patch)) != 2:
        raise ValueError("Expected two rcupdate.h RT rejected hunks")
    for expected in (
        "+#define call_rcu_bh\tcall_rcu",
        "+static inline int rcu_read_lock_bh_held(void)",
        "+\treturn rcu_read_lock_held();",
    ):
        if patch.count(expected) != 1:
            raise ValueError("Unexpected RCU compatibility rejected hunk: " + expected)

    header = source.read_text(encoding="utf-8")
    if header.count(CALL_WRAPPER) != 1:
        raise ValueError("Newer E404 call_rcu_bh() forwarding not present")
    if header.count(EXPECTED) != 1:
        raise ValueError("RCU DEBUG_LOCK_ALLOC declarations don't match E404")
    if "#define call_rcu_bh\tcall_rcu" in header:
        raise ValueError("call_rcu_bh alias already defined; conflicting API layout")
    if header.count("static inline int rcu_read_lock_bh_held(void)") != 1:
        raise ValueError("Expected E404 no-lockdep inline helper exactly once")

    body = update.read_text(encoding="utf-8")
    i = body.find("int rcu_read_lock_bh_held(void)")
    if i < 0 or body.count("int rcu_read_lock_bh_held(void)") != 1:
        raise ValueError("Expected E404 debug-lockdep RCU function missing")
    guard = body.rfind("#ifndef CONFIG_PREEMPT_RT_FULL", 0, i)
    if guard < 0 or "#endif" in body[guard:i]:
        raise ValueError("RCU implementation not protected by upstream RT guard")
    end = body.find("#endif", i)
    if end < 0 or "EXPORT_SYMBOL_GPL(rcu_read_lock_bh_held);" not in body[i:end]:
        raise ValueError("Unrecognized RT-guarded debug-lockdep RCU implementation")

    output = header.replace(EXPECTED, REPLACEMENT, 1)
    if output.count("#ifdef CONFIG_PREEMPT_RT_FULL\nstatic inline int rcu_read_lock_bh_held") != 1:
        raise ValueError("Generated RT lockdep inline helper not unique")
    return source, reject, output


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tree", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--mode", choices=("verify", "apply"), required=True)
    a = p.parse_args()
    root = a.tree.resolve()
    source, reject, output = plan(root)
    if a.mode == "apply":
        source.write_text(output, encoding="utf-8")
        reject.unlink()
    remaining = len(list(root.rglob("*.rej")))
    result = {
        "stage": "EXP76_RT_STAGE12_RCUUPDATE_LOCKDEP",
        "applied": a.mode == "apply",
        "vendor_call_rcu_bh_already_forwards": True,
        "debug_lockdep_bh_inlined_on_rt": a.mode == "apply",
        "nonrt_bh_lockdep_declaration_preserved": True,
        "rejected_hunks_resolved": 2 if a.mode == "apply" else 0,
        "remaining_rejected_files": remaining,
        "kernel_compiled": False,
        "rt_enabled": False,
        "flash_ready": False,
    }
    a.report.mkdir(parents=True, exist_ok=True)
    (a.report / "stage12-status.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    if a.mode == "apply" and remaining != 69:
        raise SystemExit("FAIL_CLOSED: expected 69 remaining RT reject files")


if __name__ == "__main__":
    main()
