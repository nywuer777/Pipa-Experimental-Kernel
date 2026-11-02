#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage46 cross-subsystem regression / NO FLASH
"""Exercise gated nine-object compilation and reject accidental kernel image/link."""
from __future__ import annotations

import json
import os
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/exp76-stage46-cross-subsystem-coverage.py"
M = runpy.run_path(str(SCRIPT), run_name="stage46_fixture")
TARGETS = M["CROSS_TARGETS"]
PRIOR = M["PRIOR_TARGETS"]
BASE = M["BASELINE"]
execute = M["execute"]
compile_one = M["compile_one"]
gate_prior = M["gate_prior"]


def write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def setup(root: Path) -> tuple[Path, Path, Path, Path, Path, Path]:
    kernel, out, report = root / "kernel-src", root / "out", root / "report"
    clang = root / "clangbin"
    clang.mkdir(parents=True)
    write(clang / "clang", "fixture")
    write(clang / "ld.lld", "fixture")
    make = clang / "make"
    make.write_text(
        "#!/usr/bin/env python3\n"
        "# Python 3 / fixture make emulator / only literal object targets / NO FLASH\n"
        "import os, sys\n"
        "name = sys.argv[-1]\n"
        "assert name.endswith('.o'), name\n"
        "print('FIXTURE_TARGET=' + name)\n"
        "if os.getenv('EXP76_TEST_FAIL_TARGET') == name:\n"
        "    print(name + ':7: error: deliberate fixture regression')\n"
        "    sys.exit(2)\n"
        "sys.exit(0)\n", encoding="utf-8"
    )
    make.chmod(0o755)
    (kernel / ".git").mkdir(parents=True)
    for target in TARGETS:
        write(kernel / (target[:-2] + ".c"), "/* pinned E404 fixture */\n")
    for i in range(64):
        write(kernel / f"rejects/r{i:02d}.rej", "rejected\n")
    write(out / ".config", "CONFIG_PREEMPT_RT_FULL=y\n# CONFIG_LTO_CLANG is not set\n")
    write(out / "include/generated/asm-offsets.h", "#define ASM_OFFSETS_PRESENT 1\n")
    baseline = root / "OBJECT_DIAGNOSTIC.json"
    prior = root / "OBJECT_COVERAGE.json"
    write(baseline, json.dumps({
        "config_preempt_rt_full": True,
        "targets": {name: {"attempted": True, "compiled": True, "exit_code": 0}
                    for name in BASE},
    }))
    write(prior, json.dumps({
        "stage": "EXP76_STAGE30_RT_OBJECT_COVERAGE_NONFLASH",
        "baseline_3_objects_compiled": True,
        "all_extra_objects_compiled": True,
        "objects_attempted": 9, "objects_compiled": 9,
        "targets": {name: {"attempted": True, "compiled": True, "exit_code": 0}
                    for name in PRIOR},
    }))
    return kernel, out, report, baseline, prior, clang


def expect_fail(callback, expected: str) -> None:
    try:
        callback()
    except ValueError as error:
        assert expected in str(error), (expected, error)
        return
    raise AssertionError("Expected failure: " + expected)


def run(args: tuple[Path, ...]) -> dict:
    return execute(*args, 20)


def main() -> None:
    assert len(TARGETS) == 9 and len(set(TARGETS)) == 9
    assert set(TARGETS).isdisjoint(PRIOR)
    assert all(t.endswith(".o") and "built-in" not in t for t in TARGETS)
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        good = setup(root / "good")
        assert gate_prior(good[3], good[4])
        report = run(good)
        assert report["baseline_12_objects_compiled"] is True
        assert report["objects_attempted"] == 9
        assert report["objects_compiled"] == 9
        assert report["all_cross_objects_compiled"] is True
        assert report["remaining_rejected_files"] == 64
        assert report["link_performed"] is False
        assert report["kernel_built"] is False and report["flash_ready"] is False
        assert set(report["targets"]) == set(TARGETS)
        for item in TARGETS:
            assert "FIXTURE_TARGET=" + item in (
                good[2] / (item.replace("/", "_") + ".log")
            ).read_text()
        assert json.loads((good[2] / M["OUTPUT_FILE"]).read_text()) == report

        blocked = setup(root / "blocked")
        old = json.loads(blocked[4].read_text())
        old["targets"].pop(PRIOR[0])
        write(blocked[4], json.dumps(old))
        result = run(blocked)
        assert result["baseline_12_objects_compiled"] is False
        assert result["objects_attempted"] == 0
        assert all(v["skip_reason"] == "PRIOR_12_OBJECT_GATE_FAILED"
                   for v in result["targets"].values())

        failed = setup(root / "failed")
        os.environ["EXP76_TEST_FAIL_TARGET"] = "kernel/irq/manage.o"
        try:
            result = run(failed)
        finally:
            del os.environ["EXP76_TEST_FAIL_TARGET"]
        assert result["objects_attempted"] == 9
        assert result["objects_compiled"] == 8
        assert result["all_cross_objects_compiled"] is False
        fault = result["targets"]["kernel/irq/manage.o"]
        assert fault["exit_code"] == 2 and not fault["compiled"]
        assert "deliberate fixture regression" in fault["errors_excerpt"][0]

        reject = setup(root / "reject")
        (reject[0] / "rejects/r00.rej").unlink()
        expect_fail(lambda: run(reject), "64 still-rejected")

        no_config = setup(root / "wrong-config")
        write(no_config[1] / ".config", "CONFIG_PREEMPT_RT_FULL=n\n")
        expect_fail(lambda: run(no_config), "CONFIG_PREEMPT_RT_FULL=y")

        preexisting_image = setup(root / "image")
        write(preexisting_image[1] / "vmlinux", "forbidden\n")
        expect_fail(lambda: run(preexisting_image), "Forbidden boot/link artifact")

        no_source = setup(root / "missing-source")
        (no_source[0] / (TARGETS[0][:-2] + ".c")).unlink()
        expect_fail(lambda: run(no_source), "Missing E404 source")

        not_allowed = setup(root / "disallowed")
        env = dict(os.environ)
        env["PATH"] = str(not_allowed[5]) + os.pathsep + env.get("PATH", "")
        for item in ("vmlinux", "Image", "boot.img", "kernel/sched/core.o"):
            expect_fail(
                lambda item=item: compile_one(not_allowed[0], not_allowed[1],
                                             not_allowed[2], item, env, 20),
                "Disallowed object target",
            )
    print("EXP76_STAGE46_CROSS_SUBSYSTEM_REGRESSIONS=9_PASS; FLASH_READY=false")


if __name__ == "__main__":
    main()
