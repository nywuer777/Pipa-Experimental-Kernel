#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage30 object coverage regression / NO FLASH
"""Test nonflash object target allowlist, migration warning and baseline gates."""
from __future__ import annotations

import json
import os
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "exp76-stage30-object-coverage.py"
namespace = runpy.run_path(str(SCRIPT), run_name="stage30_fixture")
inspect_migration = namespace["inspect_migration"]
diagnostic_lines = namespace["diagnostic_lines"]
baseline_passed = namespace["baseline_passed"]
run_object = namespace["run_object"]
EXTRA_OBJECTS = namespace["EXTRA_OBJECTS"]
BASELINE = namespace["BASELINE"]


def check() -> None:
    assert len(EXTRA_OBJECTS) == 9
    assert len(set(EXTRA_OBJECTS)) == 9
    assert all(name.endswith(".o") and not name.endswith("built-in.o") for name in EXTRA_OBJECTS)
    assert not any(name in EXTRA_OBJECTS for name in ("vmlinux", "Image", "boot.img"))
    missing = inspect_migration(
        "static void migrate_disabled_sched(struct task_struct *p);\n"
        "void check(void) { migrate_disabled_sched(current); }\n"
    )
    assert missing["migrate_disabled_sched_declarations"] == 1
    assert missing["migrate_disabled_sched_definitions"] == 0
    assert missing["migrate_disabled_sched_missing_local_definition"] is True
    assert missing["runtime_migration_contract_verified"] is False
    present = inspect_migration(
        "static void migrate_disabled_sched(struct task_struct *p)\n"
        "{\n  do_migrate(p);\n}\n"
    )
    assert present["migrate_disabled_sched_definitions"] == 1
    assert present["migrate_disabled_sched_missing_local_definition"] is False
    excerpt = diagnostic_lines(
        "include/x.c:17: warning: function 'migrate_disabled_sched' has internal linkage but is not defined\n"
        "include/y.c:22: error: undefined member\n"
    )
    assert len(excerpt) == 2 and "migrate_disabled_sched" in excerpt[0]

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        baseline = root / "OBJECT_DIAGNOSTIC.json"
        baseline.write_text(json.dumps({
            "config_preempt_rt_full": True,
            "targets": {name: {"compiled": True} for name in BASELINE},
        }))
        assert baseline_passed(baseline)
        baseline.write_text(json.dumps({
            "config_preempt_rt_full": True,
            "targets": {name: {"compiled": name != BASELINE[-1]} for name in BASELINE},
        }))
        assert not baseline_passed(baseline)

        fakebin = root / "fakebin"
        fakebin.mkdir()
        make = fakebin / "make"
        make.write_text(
            "#!/usr/bin/env python3\n"
            "# Python 3 / unit fixture / emulate build command\n"
            "import sys\n"
            "print('kernel/locking/rtmutex.c:1: warning: fixture only')\n"
            "sys.exit(0)\n",
            encoding="utf-8",
        )
        make.chmod(0o755)
        kernel = root / "kernel-src"
        (kernel / "kernel/locking").mkdir(parents=True)
        (kernel / "kernel/locking/rtmutex.c").write_text("/* fixture */\n")
        output, report = root / "out", root / "report"
        output.mkdir()
        report.mkdir()
        env = dict(os.environ)
        env["PATH"] = str(fakebin) + os.pathsep + env["PATH"]
        obj = run_object(kernel, output, report, "kernel/locking/rtmutex.o", env, 10)
        assert obj["compiled"] and obj["exit_code"] == 0
        assert len(obj["errors_excerpt"]) == 1
        assert (report / "kernel_locking_rtmutex.o.log").is_file()
        for name in ("vmlinux", "Image", "boot.img", "kernel/sched/core.o"):
            try:
                run_object(kernel, output, report, name, env, 10)
                raise AssertionError("Unexpected build target allowed: " + name)
            except ValueError:
                pass


if __name__ == "__main__":
    check()
    print("EXP76_STAGE30_COVERAGE_REGRESSION=5_PASS; KERNEL_BUILT=false; FLASH_READY=false")
