#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage41 RT migration ABI port regressions / NO FLASH
"""Fail closed on lost RT pinning, saved affinity, stopper, and hotplug paths."""
from __future__ import annotations

import json
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/exp76-rt-stage41-migration-lifecycle.py"
M = runpy.run_path(str(SCRIPT), run_name="exp76_stage41_fixture")


def put(root: Path, relative: str, data: str) -> None:
    file = root / relative
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(data, encoding="utf-8")


def upstream_reject() -> str:
    # A bounded fixture of the actual rejected API / transition contract.
    # Filler comments exercise the full-hunk size floor, not kernel logic.
    fields = [
        "",
        "#if defined(CONFIG_SMP) && defined(CONFIG_PREEMPT_RT_BASE)",
        "static inline void update_nr_migratory(struct task_struct *p, long delta) {}",
        "static inline void migrate_disable_update_cpus_allowed(struct task_struct *p)",
        "{",
        "\tp->cpus_ptr = cpumask_of(smp_processor_id());",
        "\tupdate_nr_migratory(p, -1);",
        "\tp->nr_cpus_allowed = 1;",
        "}",
        "static inline void migrate_enable_update_cpus_allowed(struct task_struct *p)",
        "{",
        "\tp->cpus_ptr = &p->cpus_mask;",
        "\tp->nr_cpus_allowed = cpumask_weight(&p->cpus_mask);",
        "\tupdate_nr_migratory(p, 1);",
        "}",
        "void migrate_disable(void)",
        "{",
        "\tthis_rq()->nr_pinned++;",
        "\tpreempt_lazy_disable();",
        "}",
        "EXPORT_SYMBOL(migrate_disable);",
        "static void migrate_disabled_sched(struct task_struct *p)",
        "{",
        "\tmigrate_disable_update_cpus_allowed(p);",
        "}",
        "static DEFINE_PER_CPU(struct cpu_stop_work, migrate_work);",
        "static DEFINE_PER_CPU(struct migration_arg, migrate_arg);",
        "void migrate_enable(void)",
        "{",
        "\trq->nr_pinned--;",
        "\tpreempt_lazy_enable();",
        "\tif (rq->nr_pinned == 0)",
        "\t\twake_up_process(takedown_cpu_task);",
        "\tWARN_ON_ONCE(!arg->done && !work->disabled && work->arg);",
        "\tstop_one_cpu_nowait(task_cpu(p), migration_cpu_stop,",
        "\t\targ, work);",
        "}",
        "EXPORT_SYMBOL(migrate_enable);",
        "int cpu_nr_pinned(int cpu)",
        "{",
        "\treturn cpu_rq(cpu)->nr_pinned;",
        "}",
        "#elif !defined(CONFIG_SMP) && defined(CONFIG_PREEMPT_RT_BASE)",
        "static void migrate_disabled_sched(struct task_struct *p) {}",
        "void migrate_disable(void) {}",
        "EXPORT_SYMBOL(migrate_disable);",
        "void migrate_enable(void) {}",
        "EXPORT_SYMBOL(migrate_enable);",
        "#else",
        "static void migrate_disabled_sched(struct task_struct *p) {}",
        "#endif",
    ]
    fields.extend(f"/* test fixture line {n:03} */" for n in range(110))
    return (M["MIGRATION_HUNK"] + "\n"
            + "\n".join("+" + line for line in fields) + "\n")


def seed(root: Path) -> None:
    core = (
        "static void migrate_disabled_sched(struct task_struct *p);\n"
        "int __migrate_disabled(struct task_struct *p)\n"
        "{\nreturn p->migrate_disable;\n}\n"
        "static void __set_cpus_allowed_ptr_fake(void)\n{\n"
        + M["ALLOWED_EQUAL"] + "\n"
        + M["SET_ALLOWED"] + "\n}\n"
        + M["CORE_TAIL"]
    )
    put(root, M["CORE"], core)
    put(root, M["REJECT"], upstream_reject())
    put(root, M["SCHED"], "struct task_struct {\n" + M["TASK_ANCHOR"] + "\n};\n")
    put(root, M["RQ"], "struct rq {\n" + M["RQ_ANCHOR"] + "\n")
    put(root, M["RQ_REJECT"], "+" + M["RQ_FIELD"].split("\tint", 1)[1].split("\n")[0]
        + "\n+\tint\t\t\tnr_pinned;\n")
    put(root, M["CPU_H"], "/* generic CPU */\n" + M["CPU_H_ANCHOR"])
    put(root, M["CPU"], "if (cpu_nr_pinned(cpu)) return -EAGAIN;\n"
        "unsigned int n = cpu_nr_pinned(cpu);\n")
    put(root, M["PREEMPT"], "extern void migrate_disable(void);\n"
        "extern void migrate_enable(void);\n"
        "extern void migrate_disable(void);\n"
        "extern void migrate_enable(void);\n")
    put(root, M["OTHER_REJECT"], "pending\n")
    for i in range(61):
        put(root, f"pending/r{i:02d}.rej", "pending\n")


def call(root: Path, mode: str = "apply") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--tree", str(root),
         "--report", str(root / "report"), "--mode", mode],
        capture_output=True, text=True,
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        good = base / "good"
        seed(good)
        original = {p: (good / p).read_text() for p in
                    (M["CORE"], M["SCHED"], M["RQ"], M["CPU_H"])}
        preview = call(good, "verify")
        assert preview.returncode == 0, preview.stderr
        for p, content in original.items():
            assert (good / p).read_text() == content

        applied = call(good)
        assert applied.returncode == 0, applied.stderr
        c = (good / M["CORE"]).read_text()
        h = (good / M["SCHED"]).read_text()
        rq = (good / M["RQ"]).read_text()
        ch = (good / M["CPU_H"]).read_text()
        for marker in (
            "migrate_disable_saved_mask", "cpu_nr_pinned(int cpu)",
            "rq->nr_pinned--", "this_rq()->nr_pinned++",
            "stop_one_cpu_nowait(task_cpu(p), migration_cpu_stop,",
            "wake_up_process(takedown_cpu_task);",
            "cpumask_copy(&p->cpus_allowed, &p->migrate_disable_saved_mask);",
            "cpumask_copy(&p->migrate_disable_saved_mask, new_mask);",
        ):
            assert marker in c, marker
        assert "cpumask_t\t\t\tmigrate_disable_saved_mask;" in h
        assert "int\t\t\tnr_pinned;" in rq
        assert "extern int cpu_nr_pinned(int cpu);" in ch
        assert "p->cpus_ptr" not in c
        assert "p->cpus_mask" not in c
        assert (good / M["CPU"]).read_text().count("cpu_nr_pinned(cpu)") == 2
        summary = json.loads((good / "report/stage41-status.json").read_text())
        assert summary["remaining_rejected_files"] == 64
        assert summary["runqueue_nr_pinned_counted"] is True
        assert summary["migration_runtime_semantics_verified"] is False
        assert summary["kernel_built"] is False and summary["flash_ready"] is False

        wrong_mask = base / "wrong-mask"
        seed(wrong_mask)
        put(wrong_mask, M["SCHED"], "struct task_struct {\n"
            + M["TASK_ANCHOR"] + "cpumask_t cpus_ptr;\n};\n")
        assert call(wrong_mask).returncode != 0
        assert (wrong_mask / M["CORE"]).read_text() == original[M["CORE"]]

        missing_hotplug = base / "hotplug-drift"
        seed(missing_hotplug)
        put(missing_hotplug, M["CPU"], "return cpu_nr_pinned(cpu);\n")
        assert call(missing_hotplug).returncode != 0

        bad_reject = base / "bad-reject"
        seed(bad_reject)
        p = bad_reject / M["REJECT"]
        p.write_text(p.read_text().replace(
            "+\tthis_rq()->nr_pinned++;",
            "+\tthis_rq()->nr_pinned += 0;",
        ))
        assert call(bad_reject).returncode != 0

        duplicate = base / "duplicate-lifecycle"
        seed(duplicate)
        put(duplicate, M["CORE"], original[M["CORE"]]
            + "\nvoid migrate_disable(void) {}\n")
        assert call(duplicate).returncode != 0

        wrong_rejects = base / "missing-reject"
        seed(wrong_rejects)
        (wrong_rejects / "pending/r00.rej").unlink()
        assert call(wrong_rejects).returncode != 0

    print("EXP76_STAGE41_MIGRATION_LIFECYCLE_REGRESSIONS=7_PASS; FLASH_READY=false")


if __name__ == "__main__":
    main()
