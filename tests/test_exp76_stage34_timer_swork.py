#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage34 swork timer port regression / NO FLASH
"""Check original rejected-hunk recovery, swork dependencies and fail-closed drift."""
from __future__ import annotations

import json
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
TOOL = HERE / "tools/exp76-rt-stage34-timer-swork.py"
P = runpy.run_path(str(TOOL), run_name="exp76_stage34_fixture")
TIMER = (
    "#include <linux/irq_work.h>\n"
    "#include <linux/init.h>\n"
    "#ifdef CONFIG_NO_HZ_COMMON\n"
    "static struct swork_event timer_update_swork;\n"
    "static void timer_update_keys(struct swork_event *event)\n"
    "{\n}\n"
    + P["OLD"]
    + "#endif\n"
)
REJ = (
    "diff a/kernel/time/timer.c b/kernel/time/timer.c (rejected hunks)\n"
    "@@ -247,9 +246,17 @@ static void timer_update_keys(struct work_struct *work)\n"
    + P["REJ_HUNK"]
)
HEADER = (
    "struct swork_event {\n"
    "  void (*func)(struct swork_event *);\n"
    "};\n"
    "static inline void INIT_SWORK(\n"
    " bool swork_queue(struct swork_event *sev);\n"
    "int swork_get(void);\n"
)
IMPL = (
    "bool swork_queue(struct swork_event *sev)\n{\nreturn true;\n}\n"
    "int swork_get(void)\n{\nreturn 0;\n}\n"
)
MAKEFILE = "obj-y += wait.o wait_bit.o swait.o swork.o completion.o\n"


def put(root: Path, relative: str, body: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def seed(root: Path) -> None:
    for rel, data in (
        ("kernel/time/timer.c", TIMER),
        ("kernel/time/timer.c.rej", REJ),
        ("include/linux/swork.h", HEADER),
        ("kernel/sched/swork.c", IMPL),
        ("kernel/sched/Makefile", MAKEFILE),
        ("kernel/sched/cpupri.c.rej", "pending\n"),
    ):
        put(root, rel, data)
    for i in range(62):
        put(root, f"pending/r{i:02d}.rej", "pending\n")


def invoke(root: Path, mode: str = "apply") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), "--tree", str(root),
         "--report", str(root / "report"), "--mode", mode],
        capture_output=True, text=True,
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        good = base / "good"
        seed(good)
        preview = invoke(good, "verify")
        assert preview.returncode == 0, preview.stderr
        assert (good / "kernel/time/timer.c").read_text() == TIMER
        ok = invoke(good)
        assert ok.returncode == 0, ok.stderr
        result = (good / "kernel/time/timer.c").read_text()
        assert result == TIMER.replace(
            P["INCLUDE_ANCHOR"], P["INCLUDE_ANCHOR"] + P["INCLUDE_SW"]
        ).replace(P["OLD"], P["NEW"])
        assert "swork_queue(&timer_update_swork);" in result
        assert "INIT_SWORK(&timer_update_swork, timer_update_keys);" in result
        assert result.count("early_initcall(hrtimer_init_thread);") == 1
        assert "schedule_work(&timer_update_work)" not in result
        metadata = json.loads((good / "report/stage34-status.json").read_text())
        assert metadata["remaining_rejected_files"] == 64
        assert metadata["swork_backend_and_makefile_verified"] is True
        assert metadata["timer_runtime_semantics_verified"] is False
        assert metadata["kernel_built"] is False and metadata["flash_ready"] is False

        drift_reject = base / "reject-drift"
        seed(drift_reject)
        put(drift_reject, "kernel/time/timer.c.rej", REJ.replace(
            "+\tswork_queue(&timer_update_swork);", "+\tswork_queue(&unknown);"
        ))
        assert invoke(drift_reject).returncode != 0
        assert (drift_reject / "kernel/time/timer.c").read_text() == TIMER

        missing_backend = base / "missing-backend"
        seed(missing_backend)
        (missing_backend / "kernel/sched/swork.c").unlink()
        assert invoke(missing_backend).returncode != 0

        missing_makefile = base / "missing-makefile"
        seed(missing_makefile)
        put(missing_makefile, "kernel/sched/Makefile", "obj-y += wait.o\n")
        assert invoke(missing_makefile).returncode != 0

        changed_timer = base / "changed-timer"
        seed(changed_timer)
        put(changed_timer, "kernel/time/timer.c",
            TIMER.replace("schedule_work(&timer_update_work)", "queue_work(&timer_update_work)"))
        assert invoke(changed_timer).returncode != 0

        extra_reject = base / "extra-reject"
        seed(extra_reject)
        put(extra_reject, "pending/extra.rej", "pending\n")
        assert invoke(extra_reject).returncode != 0
    print("EXP76_STAGE34_TIMER_SWORK_TESTS=7_PASS; FLASH_READY=false")


if __name__ == "__main__":
    main()
