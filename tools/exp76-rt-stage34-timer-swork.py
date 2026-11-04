#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage34 RT timer swork rejected-hunk port / NO FLASH
"""Restore timer_update_swork queue and early init lost from timer.c RT reject.

Pin the E404/RT partial-overlay preconditions, the original rejected hunk,
and the in-tree swork worker and Makefile integration. No workqueue fallback
or fake swork implementation; this does not establish full RT correctness.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

TIMER = "kernel/time/timer.c"
REJECT = "kernel/time/timer.c.rej"
SWORK_HEADER = "include/linux/swork.h"
SWORK_IMPL = "kernel/sched/swork.c"
SWORK_MAKEFILE = "kernel/sched/Makefile"
PENDING = "kernel/sched/cpupri.c.rej"
OLD = """void timers_update_nohz(void)
{
	schedule_work(&timer_update_work);
}
"""
NEW = """void timers_update_nohz(void)
{
	swork_queue(&timer_update_swork);
}

static __init int hrtimer_init_thread(void)
{
	WARN_ON(swork_get());
	INIT_SWORK(&timer_update_swork, timer_update_keys);
	return 0;
}
early_initcall(hrtimer_init_thread);
"""
REJ_HUNK = """ void timers_update_nohz(void)
 {
-	schedule_work(&timer_update_work);
+	swork_queue(&timer_update_swork);
 }
 
+static __init int hrtimer_init_thread(void)
+{
+	WARN_ON(swork_get());
+	INIT_SWORK(&timer_update_swork, timer_update_keys);
+	return 0;
+}
+early_initcall(hrtimer_init_thread);
"""
INCLUDE_ANCHOR = "#include <linux/irq_work.h>\n"
INCLUDE_SW = "#include <linux/swork.h>\n"


def one(body: str, fragment: str, path: str) -> None:
    found = body.count(fragment)
    if found != 1:
        raise ValueError(f"{path}: expected 1 occurrence of {fragment!r}, got {found}")


def prepare(root: Path) -> str:
    for p in (TIMER, REJECT, SWORK_HEADER, SWORK_IMPL, SWORK_MAKEFILE, PENDING):
        if not (root / p).is_file():
            raise ValueError("Stage34 pinned RT source missing: " + p)
    rejects = len(list(root.rglob("*.rej")))
    if rejects != 64:
        raise ValueError(f"Stage34 expected 64 RT rejects, saw {rejects}")
    rej = (root / REJECT).read_text(encoding="utf-8")
    one(rej, REJ_HUNK, REJECT)
    sw_h = (root / SWORK_HEADER).read_text(encoding="utf-8")
    for marker in (
        "struct swork_event {",
        "static inline void INIT_SWORK(",
        "bool swork_queue(struct swork_event *sev);",
        "int swork_get(void);",
    ):
        one(sw_h, marker, SWORK_HEADER)
    sw_c = (root / SWORK_IMPL).read_text(encoding="utf-8")
    for marker in ("bool swork_queue(struct swork_event *sev)", "int swork_get(void)"):
        one(sw_c, marker, SWORK_IMPL)
    sw_m = (root / SWORK_MAKEFILE).read_text(encoding="utf-8")
    one(sw_m, "wait.o wait_bit.o swait.o swork.o completion.o", SWORK_MAKEFILE)

    src = (root / TIMER).read_text(encoding="utf-8")
    one(src, OLD, TIMER)
    one(src, "static struct swork_event timer_update_swork;", TIMER)
    one(src, "static void timer_update_keys(struct swork_event *event)", TIMER)
    one(src, INCLUDE_ANCHOR, TIMER)
    if INCLUDE_SW in src or "early_initcall(hrtimer_init_thread)" in src:
        raise ValueError("timer.c already has swork header or early init: refuse duplicate")
    if "static DECLARE_WORK(timer_update_work" in src:
        raise ValueError("Unexpected workqueue source persisted in patched timer.c")
    return src.replace(INCLUDE_ANCHOR, INCLUDE_ANCHOR + INCLUDE_SW, 1).replace(OLD, NEW, 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--mode", required=True, choices=("verify", "apply"))
    args = parser.parse_args()
    tree = args.tree.resolve()
    updated = prepare(tree)
    if args.mode == "apply":
        (tree / TIMER).write_text(updated, encoding="utf-8")
    rejects = len(list(tree.rglob("*.rej")))
    if rejects != 64:
        raise ValueError("Reject count changed during Stage34 timer port")
    status = {
        "stage": "EXP76_STAGE34_RT_TIMER_SWORK_REJECTED_HUNK_RESTORED",
        "applied": args.mode == "apply",
        "rt_rejected_hunk_verified": True,
        "swork_backend_and_makefile_verified": True,
        "swork_queue_and_init_restored": args.mode == "apply",
        "remaining_rejected_files": rejects,
        "timer_object_compiled": False,
        "timer_runtime_semantics_verified": False,
        "complete_rt_migration_lifecycle": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    report = args.report.resolve()
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage34-status.json").write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
