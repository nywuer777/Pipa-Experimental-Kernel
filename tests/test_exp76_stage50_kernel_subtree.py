#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 GitHub Actions / EXP76 Stage50 Kbuild archive regression / NO FLASH
"""Enforce exactly kernel/built-in.a, 22 successful objects and no boot products."""
from __future__ import annotations

import json
import os
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/exp76-stage50-kernel-subtree.py"
M = runpy.run_path(str(SCRIPT), run_name="exp76_stage50_fixture")
execute = M["execute"]
gate = M["all_passed"]


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def setup(root: Path) -> tuple[Path, Path, Path, Path, Path, Path, Path]:
    kernel, out, report = root / "kernel", root / "out", root / "report"
    clang = root / "clangbin"
    clang.mkdir(parents=True)
    for name in ("clang", "ld.lld", "llvm-ar"):
        write(clang / name, "test binary placeholder")
    fake = clang / "make"
    write(fake, (
        "#!/usr/bin/env python3\n"
        "# Python 3 / unit test make shim / one archive target only / NO FLASH\n"
        "import os, pathlib, sys\n"
        "assert sys.argv[-1] == 'kernel/built-in.a', sys.argv\n"
        "assert 'vmlinux' not in sys.argv and 'Image' not in sys.argv\n"
        "print('FAKE_KBUILD_KERNEL_ARCHIVE_ONLY')\n"
        "if os.environ.get('EXP76_TEST_ARCHIVE_FAIL') == 'yes':\n"
        "    print('kernel/panic.c:41: error: synthetic RT Kbuild failure')\n"
        "    sys.exit(2)\n"
        "out = next(x[2:] for x in sys.argv if x.startswith('O='))\n"
        "p = pathlib.Path(out) / 'kernel/built-in.a'\n"
        "p.parent.mkdir(parents=True, exist_ok=True)\n"
        "p.write_bytes(b'!<arch>\\nFAKE-ONLY')\n"
    ))
    fake.chmod(0o755)
    (kernel / ".git").mkdir(parents=True)
    write(kernel / "scripts/Makefile.build",
          "$(obj)/built-in.a: $(real-obj-y) FORCE\n")
    write(kernel / "kernel/Makefile", "obj-y += fork.o panic.o\n")
    write(out / ".config", "CONFIG_PREEMPT_RT_FULL=y\n")
    write(out / "include/generated/asm-offsets.h", "#define E404 1\n")
    for i in range(64):
        write(kernel / f"pending/{i:02d}.rej", "rejected\n")

    base, prior, cross = (root / "baseline.json", root / "prior.json",
                          root / "cross.json")
    def items(keys: tuple[str, ...]) -> dict:
        return {k: {"attempted": True, "compiled": True, "exit_code": 0}
                for k in keys}
    write(base, json.dumps({
        "config_preempt_rt_full": True,
        "targets": items(M["BASE"]),
    }))
    write(prior, json.dumps({
        "stage": "EXP76_STAGE30_RT_OBJECT_COVERAGE_NONFLASH",
        "baseline_3_objects_compiled": True,
        "all_extra_objects_compiled": True,
        "objects_compiled": 9, "objects_attempted": 9,
        "targets": items(M["PRIOR"]),
    }))
    write(cross, json.dumps({
        "stage": "EXP76_STAGE46_RT_CROSS_SUBSYSTEM_OBJECTS_NONFLASH",
        "baseline_12_objects_compiled": True,
        "all_cross_objects_compiled": True,
        "objects_compiled": 10, "objects_attempted": 10,
        "remaining_rejected_files": 64,
        "link_performed": False,
        "targets": items(M["CROSS"]),
    }))
    return kernel, out, report, base, prior, cross, clang


def invoke(args: tuple[Path, ...]) -> dict:
    return execute(*args, 90)


def fail(call, message: str) -> None:
    try:
        call()
    except ValueError as exc:
        assert message in str(exc), str(exc)
    else:
        raise AssertionError("Expected rejection: " + message)


def main() -> None:
    assert len(M["BASE"]) + len(M["PRIOR"]) + len(M["CROSS"]) == 22
    assert M["TARGET"] == "kernel/built-in.a"
    assert "vmlinux" in M["BAD_ARTIFACTS"]
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        good = setup(root / "good")
        assert gate(good[3], good[4], good[5])
        done = invoke(good)
        assert done["attempted"] is True
        assert done["exit_code"] == 0
        assert done["archive_created"] is True
        assert done["archive_bytes"] > 0
        assert done["target"] == "kernel/built-in.a"
        assert done["full_kernel_link_performed"] is False
        assert done["kernel_built"] is False and done["flash_ready"] is False
        assert "FAKE_KBUILD_KERNEL_ARCHIVE_ONLY" in (
            good[2] / "kernel_subtree_make.log"
        ).read_text()
        assert json.loads((good[2] / M["OUTPUT"]).read_text()) == done

        # Errors from the aggregate target are useful, not swallowed.
        broken = setup(root / "compile-error")
        os.environ["EXP76_TEST_ARCHIVE_FAIL"] = "yes"
        try:
            status = invoke(broken)
        finally:
            del os.environ["EXP76_TEST_ARCHIVE_FAIL"]
        assert status["exit_code"] == 2
        assert status["archive_created"] is False
        assert status["errors_excerpt"][0].endswith("synthetic RT Kbuild failure")
        assert status["kernel_built"] is False

        # All 22 successes are prerequisites, not just stage count fields.
        missing = setup(root / "missing-object")
        data = json.loads(missing[5].read_text())
        data["targets"]["kernel/rcu/tree.o"]["compiled"] = False
        write(missing[5], json.dumps(data))
        skipped = invoke(missing)
        assert skipped["attempted"] is False
        assert skipped["skip_reason"] == "BASELINE_22_OBJECT_GATE_FAILED"
        assert not (missing[2] / "kernel_subtree_make.log").exists()
        assert skipped["kernel_built"] is False
        assert not gate(missing[3], missing[4], missing[5])

        mismatch = setup(root / "missing-cross-object")
        data = json.loads(mismatch[5].read_text())
        del data["targets"]["kernel/locking/mutex-rt.o"]
        write(mismatch[5], json.dumps(data))
        assert invoke(mismatch)["attempted"] is False

        image = setup(root / "unexpected-image")
        write(image[1] / "vmlinux", "forbidden\n")
        fail(lambda: invoke(image), "Unexpected link or boot artifact")

        bad_rt = setup(root / "wrong-config")
        write(bad_rt[1] / ".config", "CONFIG_PREEMPT_RT_FULL=n\n")
        fail(lambda: invoke(bad_rt), "PREEMPT_RT_FULL not established")

        missing_reject = setup(root / "missing-reject")
        (missing_reject[0] / "pending/00.rej").unlink()
        fail(lambda: invoke(missing_reject), "64 unresolved RT rejects")

        missing_rule = setup(root / "missing-rule")
        write(missing_rule[0] / "scripts/Makefile.build", "no archive rule\n")
        fail(lambda: invoke(missing_rule), "archive construction rule not found")

        bad_timeout = setup(root / "timeout")
        fail(lambda: execute(*bad_timeout, 15), "Unsupported subtree compile timeout")

    print("EXP76_STAGE50_SUBTREE_ARCHIVE_REGRESSIONS=9_PASS; KERNEL_BUILT=false; FLASH_READY=false")


if __name__ == "__main__":
    main()
