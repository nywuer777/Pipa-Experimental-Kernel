#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / Stage66 memory Kbuild regression / NO FLASH
"""Reject broad Kbuild traversal, missing Stage50 gate and forbidden artifacts."""
from __future__ import annotations

import json
import os
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT / "tools/exp76-stage66-mm-subtree.py"),
                   run_name="exp76_stage66_test")
execute = M["execute"]


def write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")


def fixture(root: Path) -> tuple[Path, Path, Path, Path, Path]:
    kernel, out, report, prior, clang = (
        root / "kernel", root / "out", root / "report",
        root / "prior.json", root / "clang",
    )
    (kernel / ".git").mkdir(parents=True)
    write(kernel / "mm/Makefile", "obj-y += slab_common.o\n")
    write(kernel / "scripts/Makefile.build",
          "$(obj)/built-in.a: $(real-obj-y) FORCE\n")
    write(kernel / "Makefile", (
        "vmlinux-dirs\t:= $(patsubst %/,%,$(filter %/,\n"
        "$(sort $(vmlinux-deps)): $(vmlinux-dirs) ;\n"
        "$(vmlinux-dirs): prepare scripts\n"
        "\t$(Q)$(MAKE) $(build)=$@ need-builtin=1\n"
    ))
    write(out / ".config", "CONFIG_PREEMPT_RT_FULL=y\n")
    write(out / "include/generated/asm-offsets.h", "#define E404 1\n")
    archive = out / "kernel/built-in.a"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_bytes(b"!<thin>\nvalid-stage50")
    for i in range(64):
        write(kernel / f"pending/{i:02d}.rej", "unresolved\n")
    write(prior, json.dumps({
        "stage": M["EXPECTED_STAGE50"],
        "target": "kernel/built-in.a",
        "top_level_directory_scope": "vmlinux-dirs=kernel",
        "baseline_22_objects_compiled": True,
        "attempted": True,
        "exit_code": 0,
        "archive_created": True,
        "archive_bytes": len(archive.read_bytes()),
        "remaining_rejected_files": 64,
        "full_kernel_link_performed": False,
        "kernel_built": False,
        "flash_ready": False,
    }))
    clang.mkdir(parents=True)
    for bin_name in ("clang", "ld.lld", "llvm-ar"):
        write(clang / bin_name, "pinned compiler fixture\n")
    fake = clang / "make"
    write(fake, (
        "#!/usr/bin/env python3\n"
        "# Python 3 / synthetic Kbuild make shim / mm only / NO FLASH\n"
        "import os, pathlib, sys\n"
        "assert sys.argv[-1] == 'mm/built-in.a', sys.argv\n"
        "assert 'vmlinux-dirs=mm' in sys.argv, sys.argv\n"
        "assert 'vmlinux-dirs=kernel' not in sys.argv, sys.argv\n"
        "assert 'vmlinux' not in sys.argv and 'Image' not in sys.argv\n"
        "print('EXP76_FAKE_MM_ONLY')\n"
        "if os.environ.get('EXP76_TEST_MM_FAIL') == 'yes':\n"
        "    print('mm/vmscan.c:42: error: synthetic PREEMPT_RT conflict')\n"
        "    sys.exit(2)\n"
        "out = next(x[2:] for x in sys.argv if x.startswith('O='))\n"
        "a = pathlib.Path(out) / 'mm/built-in.a'\n"
        "a.parent.mkdir(parents=True, exist_ok=True)\n"
        "a.write_bytes(b'!<thin>\\nsynthetic-mm')\n"
    ))
    fake.chmod(0o755)
    return kernel, out, report, prior, clang


def reject(fn, message: str) -> None:
    try:
        fn()
    except ValueError as exc:
        assert message in str(exc), str(exc)
    else:
        raise AssertionError("Expected failure: " + message)


def run(parts: tuple[Path, ...]) -> dict:
    return execute(*parts, 90)


def main() -> None:
    assert M["TARGET"] == "mm/built-in.a"
    assert M["SCOPE"] == "vmlinux-dirs=mm"
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        good = fixture(root / "good")
        done = run(good)
        assert done["archive_created"] is True
        assert done["exit_code"] == 0
        assert done["prior_kernel_subtree_gate"] is True
        assert done["top_level_directory_scope"] == "vmlinux-dirs=mm"
        assert done["timed_out"] is False
        assert not done["kernel_built"] and not done["flash_ready"]
        assert "EXP76_FAKE_MM_ONLY" in (
            good[2] / "mm_subtree_make.log"
        ).read_text(encoding="utf-8")
        assert json.loads((good[2] / M["OUTPUT"]).read_text()) == done

        failed = fixture(root / "compile-failure")
        os.environ["EXP76_TEST_MM_FAIL"] = "yes"
        try:
            status = run(failed)
        finally:
            del os.environ["EXP76_TEST_MM_FAIL"]
        assert status["exit_code"] == 2
        assert status["archive_created"] is False
        assert "synthetic PREEMPT_RT conflict" in status["errors_excerpt"][0]

        bad_stage50 = fixture(root / "stage50-failed")
        p = bad_stage50[3]
        value = json.loads(p.read_text())
        value["archive_created"] = False
        write(p, json.dumps(value))
        reject(lambda: run(bad_stage50), "Stage50 scoped")

        bad_prior_scope = fixture(root / "wrong-scope")
        p = bad_prior_scope[3]
        value = json.loads(p.read_text())
        value["top_level_directory_scope"] = "vmlinux-dirs=drivers"
        write(p, json.dumps(value))
        reject(lambda: run(bad_prior_scope), "Stage50 scoped")

        missing_archive = fixture(root / "missing-prior-archive")
        (missing_archive[1] / "kernel/built-in.a").unlink()
        reject(lambda: run(missing_archive), "Stage50 scoped")

        no_mm = fixture(root / "missing-mm-makefile")
        (no_mm[0] / "mm/Makefile").unlink()
        reject(lambda: run(no_mm), "mm/Makefile missing")

        no_git = fixture(root / "no-git")
        (no_git[0] / ".git").rmdir()
        reject(lambda: run(no_git), "isolated E404")

        wrong_config = fixture(root / "wrong-config")
        write(wrong_config[1] / ".config", "CONFIG_PREEMPT_RT_FULL=n\n")
        reject(lambda: run(wrong_config), "PREEMPT_RT_FULL")

        missing_reject = fixture(root / "missing-reject")
        (missing_reject[0] / "pending/00.rej").unlink()
        reject(lambda: run(missing_reject), "64 outstanding")

        altered_root = fixture(root / "drifted-Kbuild")
        write(altered_root[0] / "Makefile", "vmlinux-dirs := drivers\n")
        reject(lambda: run(altered_root), "directory dependency drift")

        boot_product = fixture(root / "unexpected-Image")
        write(boot_product[1] / "arch/arm64/boot/Image", "forbidden\n")
        reject(lambda: run(boot_product), "Unexpected link or boot artifact")

        bad_timeout = fixture(root / "timeout")
        reject(lambda: execute(*bad_timeout, 15), "Unsupported Stage66 timeout")
    print("EXP76_STAGE66_MM_SUBTREE_REGRESSIONS=12_PASS; KERNEL_BUILT=false; FLASH_READY=false")


if __name__ == "__main__":
    main()
