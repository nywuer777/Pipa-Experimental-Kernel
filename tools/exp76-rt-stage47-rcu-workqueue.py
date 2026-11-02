#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage47 rejected RCU closures and raw workqueue lock / NO FLASH
"""Port bounded original E404 RT rejected fixes; require complete cpp balance.

This is a source-port audit, NOT a runtime correctness or full-kernel gate.
No guessed #endif, no global spinlock conversions, and no partial writes.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

UPDATE = "kernel/rcu/update.c"
UPDATE_REJ = "kernel/rcu/update.c.rej"
PLUGIN = "kernel/rcu/tree_plugin.h"
PLUGIN_REJ = "kernel/rcu/tree_plugin.h.rej"
WORK = "kernel/workqueue.c"
WORK_REJ = "kernel/workqueue.c.rej"
OTHER_REJ = "kernel/sched/cpupri.c.rej"

UPDATE_END = "EXPORT_SYMBOL_GPL(rcu_read_lock_bh_held);\n"
UPDATE_APPEND = "#endif /* CONFIG_PREEMPT_RT_FULL: rejected RCU lockdep close */\n"
PLUGIN_END = (
    "\t*nextevt = basemono + dj * TICK_NSEC;\n"
    "\treturn 0;\n"
    "}\n\n"
    "/*\n"
    " * Prepare a CPU for idle"
)
PLUGIN_INSERT = "#endif /* #ifndef CONFIG_PREEMPT_RT_FULL */\n"
WORK_LOCK = "\tworker->sleeping = 1;\n\tspin_lock_irq(&pool->lock);\n"
WORK_LOCK_RT = "\tworker->sleeping = 1;\n\traw_spin_lock_irq(&pool->lock);\n"
WORK_UNLOCK = (
    "\t\tif (next)\n"
    "\t\t\twake_up_process(next->task);\n"
    "\t}\n"
    "\tspin_unlock_irq(&pool->lock);\n"
)
WORK_UNLOCK_RT = WORK_UNLOCK.replace(
    "\tspin_unlock_irq(&pool->lock);\n",
    "\traw_spin_unlock_irq(&pool->lock);\n",
)
DIRECTIVE = re.compile(r"^\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b(.*)$")


def one(body: str, marker: str, path: str) -> None:
    count = body.count(marker)
    if count != 1:
        raise ValueError(f"{path}: expected one {marker!r}, saw {count}")


def require_original_rejected_hunk(contents: str, path: str,
                                   header: str, anchored_addition: str) -> None:
    """Match the correct +#endif by original hunk AND adjacent source context.

    update.c.rej also adds +#endif to guard the boot parameter. Counting
    the bare line across the whole .rej incorrectly rejects valid E404 RT.
    """
    one(contents, header, path)
    hunk = contents.split(header, 1)[1].split("\n@@ ", 1)[0]
    one(hunk, anchored_addition, path + "::" + header.strip())


def unclosed(source: str, name: str) -> list[tuple[int, str]]:
    stack: list[tuple[int, str, bool]] = []
    for line_number, line in enumerate(source.splitlines(), 1):
        m = DIRECTIVE.match(line)
        if not m:
            continue
        operation = m.group(1)
        if operation in ("if", "ifdef", "ifndef"):
            stack.append((line_number, m.group(0).strip(), False))
        elif operation in ("elif", "else"):
            if not stack or stack[-1][2]:
                raise ValueError(f"{name}:{line_number}: invalid #{operation}")
            if operation == "else":
                n, expression, _ = stack[-1]
                stack[-1] = n, expression, True
        else:
            if not stack:
                raise ValueError(f"{name}:{line_number}: orphan #endif")
            stack.pop()
    return [(n, expression) for n, expression, _ in stack]


def prepare(tree: Path) -> tuple[dict[str, str], dict]:
    names = (UPDATE, UPDATE_REJ, PLUGIN, PLUGIN_REJ, WORK, WORK_REJ, OTHER_REJ)
    for name in names:
        if not (tree / name).is_file():
            raise ValueError("Pinned RT overlay source missing: " + name)
    reject_count = len(list(tree.rglob("*.rej")))
    if reject_count != 64:
        raise ValueError(f"Stage47 expected 64 unresolved RT rejects, got {reject_count}")

    u = (tree / UPDATE).read_text(encoding="utf-8")
    p = (tree / PLUGIN).read_text(encoding="utf-8")
    w = (tree / WORK).read_text(encoding="utf-8")
    ru = (tree / UPDATE_REJ).read_text(encoding="utf-8")
    rp = (tree / PLUGIN_REJ).read_text(encoding="utf-8")
    rw = (tree / WORK_REJ).read_text(encoding="utf-8")

    # Match each closer to its original hunk and neighboring context.
    # The valid update.c.rej has TWO +#endif additions in different hunks:
    # the first closes rcu_normal_after_boot; the second closes RT lockdep.
    require_original_rejected_hunk(
        ru, UPDATE_REJ,
        "@@ -314,6 +318,7 @@ int rcu_read_lock_bh_held(void)\n",
        " EXPORT_SYMBOL_GPL(rcu_read_lock_bh_held);\n+#endif\n",
    )
    require_original_rejected_hunk(
        rp, PLUGIN_REJ,
        "@@ -1559,6 +1448,7 @@ int rcu_needs_cpu(u64 basemono, u64 *nextevt)\n",
        " \treturn 0;\n }\n+#endif /* #ifndef CONFIG_PREEMPT_RT_FULL */\n",
    )
    one(rw, "+\traw_spin_lock_irq(&pool->lock);\n", WORK_REJ)
    one(rw, "+\traw_spin_unlock_irq(&pool->lock);\n", WORK_REJ)

    one(u, UPDATE_END, UPDATE)
    one(p, PLUGIN_END, PLUGIN)
    one(w, WORK_LOCK, WORK)
    one(w, WORK_UNLOCK, WORK)
    if UPDATE_APPEND in u or PLUGIN_INSERT in p:
        raise ValueError("RCU rejected closers already restored; re-audit source")
    if WORK_LOCK_RT in w or WORK_UNLOCK_RT in w:
        raise ValueError("Worker raw-spinlock conversion already present")

    # Guard against superficially similar but unrelated upstream C code.
    if not re.search(r"struct worker_pool\s*\{[\s\S]{0,90}raw_spinlock_t\s+lock;", w):
        raise ValueError("Worker pool does not use raw_spinlock_t under RT")
    if "void wq_worker_sleeping(struct task_struct *task)" not in w:
        raise ValueError("Expected original PREEMPT_RT wq_worker_sleeping API")

    u_open = unclosed(u, UPDATE)
    p_open = unclosed(p, PLUGIN)
    if len(u_open) != 1 or "CONFIG_DEBUG_LOCK_ALLOC" not in u_open[0][1]:
        raise ValueError(f"{UPDATE}: unexpected pending conditional: {u_open}")
    if len(p_open) != 1 or "CONFIG_RCU_FAST_NO_HZ" not in p_open[0][1]:
        raise ValueError(f"{PLUGIN}: unexpected pending conditional: {p_open}")

    # The source order is identical to the rejected RT hunks: append the
    # lockdep closer after rcu_read_lock_bh_held(), and the RCU idle closer
    # after the second rcu_needs_cpu() implementation, before idle setup.
    u_new = u.replace(UPDATE_END, UPDATE_END + UPDATE_APPEND, 1)
    p_new = p.replace(PLUGIN_END, PLUGIN_END.replace(
        "\n/*\n * Prepare a CPU for idle",
        "\n" + PLUGIN_INSERT + "\n/*\n * Prepare a CPU for idle",
    ), 1)
    w_new = w.replace(WORK_LOCK, WORK_LOCK_RT, 1).replace(
        WORK_UNLOCK, WORK_UNLOCK_RT, 1
    )
    for filename, body in ((UPDATE, u_new), (PLUGIN, p_new)):
        remaining = unclosed(body, filename)
        if remaining:
            raise ValueError(f"{filename}: conditional still open after RT port: {remaining}")
    if w_new.count(WORK_LOCK_RT) != 1 or w_new.count(WORK_UNLOCK_RT) != 1:
        raise ValueError("Worker raw-spinlock conversion did not preserve a paired lock")
    return {UPDATE: u_new, PLUGIN: p_new, WORK: w_new}, {
        "stage": "EXP76_STAGE47_RCU_PREPROCESSOR_AND_WORKQUEUE_RAW_LOCK",
        "rcu_update_prepatch_unclosed": len(u_open),
        "rcu_plugin_prepatch_unclosed": len(p_open),
        "rcu_postpatch_preprocessor_balanced": True,
        "workqueue_sleeping_pair_ported": True,
        "unrelated_workqueue_spinlock_calls_unchanged": True,
        "remaining_rejected_files": reject_count,
        "rcu_runtime_verified": False,
        "workqueue_runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = parser.parse_args()
    tree = args.tree.resolve()
    changed, report = prepare(tree)
    if args.mode == "apply":
        for name, body in changed.items():
            (tree / name).write_text(body, encoding="utf-8")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage47 reject count changed")
    report["applied"] = args.mode == "apply"
    target = args.report.resolve()
    target.mkdir(parents=True, exist_ok=True)
    (target / "stage47-status.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
