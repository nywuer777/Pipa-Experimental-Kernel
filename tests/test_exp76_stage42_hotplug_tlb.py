#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage42 pinned CPU hotplug handshake regressions / NO FLASH
"""Ensure E404 RT CPU pin draining and conditional architecture TLB API."""
from __future__ import annotations

import json
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
TOOL = HERE / "tools/exp76-rt-stage42-hotplug-tlb.py"
D = runpy.run_path(str(TOOL), run_name="stage42_test_fixture")
CORE = (
    '#include <asm/tlb.h>\n'
    + D["CORE_DECL_MARKER"] +
    '{\n\tp->nr_cpus_allowed += delta;\n}\n'
    'int cpu_nr_pinned(int cpu)\n{\n\treturn cpu_rq(cpu)->nr_pinned;\n}\n'
    'void migrate_enable(void)\n{\n'
    '\trq->nr_pinned--;\n'
    '\twake_up_process(takedown_cpu_task);\n'
    + D["CORE_HOOK"] + '}\n'
)
CPU = (
    'static int take_cpu_down(void *arg)\n'
    '{\n\tif (cpu_nr_pinned(cpu))\n\t\treturn -EAGAIN;\n}\n'
    + D["CPU_FUNC"] +
    '{\n\tstruct cpuhp_cpu_state *st;\n\tint err;\n'
    + D["HOTPLUG_SETUP"] +
    '\t/* So now all preempt/rcu users must observe !cpu_active(). */\n'
    + D["STOP_CALL"] + D["FAIL_ANCHOR"] +
    '\n\t\treturn err;\n\t}\n'
    + D["SUCCESS_ANCHOR"] +
    '\n\tirq_unlock_sparse();\n\treturn 0;\n}\n'
)


def put(root: Path, name: str, value: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def fixture(root: Path) -> None:
    put(root, D["CORE"], CORE)
    put(root, D["CPU"], CPU)
    put(root, D["ARM64_TLB"], "#include <asm-generic/tlb.h>\n")
    put(root, D["GENERIC_TLB"], "#ifndef _ASM_GENERIC_TLB_H\n#endif\n")
    put(root, D["CPU_REJECT"], "pending\n")
    put(root, D["OTHER_REJECT"], "pending\n")
    for n in range(62):
        put(root, f"pending/r{n:02d}.rej", "pending\n")


def run(root: Path, mode: str = "apply") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), "--tree", str(root),
         "--report", str(root / "report"), "--mode", mode],
        capture_output=True, text=True,
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        good = base / "good"
        fixture(good)
        preview = run(good, "verify")
        assert preview.returncode == 0, preview.stderr
        assert (good / D["CORE"]).read_text() == CORE
        assert (good / D["CPU"]).read_text() == CPU
        applied = run(good)
        assert applied.returncode == 0, applied.stderr
        cpu = (good / D["CPU"]).read_text()
        core = (good / D["CORE"]).read_text()
        assert "struct task_struct *takedown_cpu_task;" in cpu
        assert "WRITE_ONCE(takedown_cpu_task, current);" in cpu
        assert cpu.count("WRITE_ONCE(takedown_cpu_task, NULL);") == 2
        assert "set_current_state(TASK_UNINTERRUPTIBLE)" in cpu
        assert "goto retry_pinned_cpu;" in cpu
        assert "if (err == -EAGAIN)" in cpu
        assert "if (cpu_nr_pinned(cpu))" in cpu
        # An unported source has only the stopper check; the RT loop
        # adds exactly one second call. Do not allow phantom consumers.
        assert CPU.count("cpu_nr_pinned(cpu)") == 1
        assert cpu.count("cpu_nr_pinned(cpu)") == 2
        assert "extern struct task_struct *takedown_cpu_task;" in core
        assert "#ifdef tlb_migrate_finish" in core
        assert core.count("tlb_migrate_finish(p->mm);") == 1
        result = json.loads((good / "report/stage42-status.json").read_text())
        assert result["remaining_rejected_files"] == 64
        assert result["migration_hotplug_runtime_verified"] is False
        assert result["kernel_built"] is False and result["flash_ready"] is False

        # Stage42: CPU hotplug may already have been completely patched
        # by the official RT patch. Reuse that code without duplication.
        upstream = base / "preexisting-upstream"
        fixture(upstream)
        vendor_cpu = (upstream / D["CPU"]).read_text()
        upstream_wait = D["HOTPLUG_RT_WAIT"]
        upstream_wait = upstream_wait.replace(
            "WARN_ON_ONCE(READ_ONCE(takedown_cpu_task));",
            "WARN_ON_ONCE(takedown_cpu_task);"
        ).replace(
            "WRITE_ONCE(takedown_cpu_task, current);",
            "takedown_cpu_task = current;"
        ).replace("retry_pinned_cpu:", "again:").replace(
            "__set_current_state(TASK_RUNNING);", "set_current_state(TASK_RUNNING);"
        ).replace(
            "if (!nr_pinned)", "if (nr_pinned == 0)"
        )
        upstream_cpu = vendor_cpu.replace(
            D["CPU_FUNC"], D["CPU_THREAD_GLOBAL"] + D["CPU_FUNC"], 1
        ).replace(
            D["HOTPLUG_SETUP"], D["HOTPLUG_SETUP"] + upstream_wait, 1
        ).replace(
            D["STOP_CALL"],
            D["STOP_CALL"] + D["STOP_RETRY"].replace(
                "retry_pinned_cpu", "again"
            ),
            1,
        ).replace(
            D["FAIL_ANCHOR"],
            D["FAIL_REPLACEMENT"].replace(
                "WRITE_ONCE(takedown_cpu_task, NULL);",
                "takedown_cpu_task = NULL;"
            ),
            1,
        ).replace(
            D["SUCCESS_ANCHOR"],
            D["SUCCESS_REPLACEMENT"].replace(
                "WRITE_ONCE(takedown_cpu_task, NULL);",
                "takedown_cpu_task = NULL;"
            ),
            1,
        )
        put(upstream, D["CPU"], upstream_cpu)
        kept = run(upstream)
        assert kept.returncode == 0, kept.stderr
        assert (upstream / D["CPU"]).read_text() == upstream_cpu
        assert upstream_cpu.count("cpu_nr_pinned(cpu)") == 2
        assert upstream_cpu.count("nr_pinned = cpu_nr_pinned(cpu);") == 1
        assert (upstream / D["CORE"]).read_text() != CORE
        existing_report = json.loads(
            (upstream / "report/stage42-status.json").read_text())
        assert existing_report["preexisting_upstream_hotplug_reused"] is True

        phantom_consumer = base / "phantom-consumer"
        fixture(phantom_consumer)
        put(phantom_consumer, D["CPU"], upstream_cpu
            + "\nint unexpected_pin_reader(void) { return cpu_nr_pinned(cpu); }\n")
        rejected = run(phantom_consumer)
        assert rejected.returncode != 0
        assert "Complete RT hotplug requires stopper and polling call sites" in rejected.stderr

        missing_poll = base / "missing-upstream-poll"
        fixture(missing_poll)
        put(missing_poll, D["CPU"], upstream_cpu.replace(
            "nr_pinned = cpu_nr_pinned(cpu);",
            "nr_pinned = 0;",
        ))
        invalid = run(missing_poll)
        assert invalid.returncode != 0
        assert "expected one" in invalid.stderr
        assert (missing_poll / D["CORE"]).read_text() == CORE

        incomplete_upstream = base / "incomplete-upstream"
        fixture(incomplete_upstream)
        put(incomplete_upstream, D["CPU"], upstream_cpu.replace(
            "takedown_cpu_task = NULL;", "", 1
        ))
        assert run(incomplete_upstream).returncode != 0
        assert (incomplete_upstream / D["CORE"]).read_text() == CORE

        second = run(good)
        assert second.returncode != 0  # not an idempotent silent port

        absent_hotplug = base / "missing-pin-check"
        fixture(absent_hotplug)
        put(absent_hotplug, D["CPU"], CPU.replace(
            "if (cpu_nr_pinned(cpu))", "if (nr_running(cpu))"))
        assert run(absent_hotplug).returncode != 0
        assert (absent_hotplug / D["CPU"]).read_text().count("takedown_cpu_task") == 0

        changed_hook = base / "arch-hook-drift"
        fixture(changed_hook)
        put(changed_hook, D["ARM64_TLB"],
            "#include <asm-generic/tlb.h>\n#define tlb_migrate_finish(mm) flush_tlb_mm(mm)\n")
        assert run(changed_hook).returncode != 0

        changed_core = base / "lost-upstream-wake"
        fixture(changed_core)
        put(changed_core, D["CORE"], CORE.replace(
            "wake_up_process(takedown_cpu_task);", "wake_up_process(unrelated);"))
        assert run(changed_core).returncode != 0

        missing_retry = base / "missing-stop-machine"
        fixture(missing_retry)
        put(missing_retry, D["CPU"], CPU.replace(D["STOP_CALL"], "err = 0;\n"))
        assert run(missing_retry).returncode != 0

        short_rejects = base / "reject-count"
        fixture(short_rejects)
        (short_rejects / "pending/r00.rej").unlink()
        assert run(short_rejects).returncode != 0

    print("EXP76_STAGE43_HOTPLUG_PIN_CALL_SITES_REGRESSIONS=11_PASS; FLASH_READY=false")


if __name__ == "__main__":
    main()
