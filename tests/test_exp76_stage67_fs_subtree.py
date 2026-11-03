#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage67 FS Kbuild tests / NO FLASH
"""Verify scoped FS Kbuild and fail-closed kernel/mm prerequisites."""
from __future__ import annotations

import json
import os
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT / "tools/exp76-stage67-fs-subtree.py"),
                   run_name="exp76_stage67_regression")
execute = M["execute"]


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def setup(base: Path) -> tuple[Path, Path, Path, Path, Path, Path]:
    kernel, out, report, stage50, stage66, clang = (
        base / "kernel", base / "out", base / "report",
        base / "stage50.json", base / "stage66.json", base / "clang",
    )
    (kernel / ".git").mkdir(parents=True)
    write(kernel / "fs/Makefile", "obj-y += open.o read_write.o\n")
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
    for i in range(64):
        write(kernel / f"pending/{i:02d}.rej", "RT rejection\n")
    for directory in ("kernel", "mm"):
        archive = out / directory / "built-in.a"
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(b"!<thin>\nprior-archive")
    write(stage50, json.dumps({
        "stage": "EXP76_STAGE50_KERNEL_SUBTREE_KBUILD_ARCHIVE_NONFLASH",
        "target": "kernel/built-in.a",
        "top_level_directory_scope": "vmlinux-dirs=kernel",
        "baseline_22_objects_compiled": True,
        "attempted": True,
        "exit_code": 0,
        "archive_created": True,
        "archive_bytes": 20,
        "remaining_rejected_files": 64,
        "full_kernel_link_performed": False,
        "kernel_built": False,
        "flash_ready": False,
    }))
    write(stage66, json.dumps({
        "stage": "EXP76_STAGE66_MM_SUBTREE_KBUILD_ARCHIVE_NONFLASH",
        "target": "mm/built-in.a",
        "top_level_directory_scope": "vmlinux-dirs=mm",
        "prior_kernel_subtree_gate": True,
        "attempted": True,
        "exit_code": 0,
        "timed_out": False,
        "archive_created": True,
        "archive_bytes": 20,
        "remaining_rejected_files": 64,
        "full_kernel_link_performed": False,
        "kernel_built": False,
        "flash_ready": False,
    }))
    clang.mkdir(parents=True)
    for name in ("clang", "ld.lld", "llvm-ar"):
        write(clang / name, "Android Clang21 fixture\n")
    make = clang / "make"
    write(make, (
        "#!/usr/bin/env python3\n"
        "# Python 3 / fixture Kbuild invocation / fs only / NO FLASH\n"
        "import os, pathlib, sys\n"
        "assert sys.argv[-1] == 'fs/built-in.a', sys.argv\n"
        "assert 'vmlinux-dirs=fs' in sys.argv, sys.argv\n"
        "assert not any(x.startswith('vmlinux-dirs=') and x != 'vmlinux-dirs=fs' for x in sys.argv)\n"
        "assert 'vmlinux' not in sys.argv and 'Image' not in sys.argv\n"
        "print('EXP76_STAGE67_FS_SUBTREE_FIXTURE_ONLY')\n"
        "if os.environ.get('EXP76_FS_FAIL') == 'yes':\n"
        "    print('fs/open.c:13: error: synthetic PREEMPT_RT incompatibility')\n"
        "    sys.exit(2)\n"
        "out = next(x[2:] for x in sys.argv if x.startswith('O='))\n"
        "archive = pathlib.Path(out) / 'fs/built-in.a'\n"
        "archive.parent.mkdir(parents=True, exist_ok=True)\n"
        "archive.write_bytes(b'!<thin>\\nsynthetic-fs')\n"
    ))
    make.chmod(0o755)
    return kernel, out, report, stage50, stage66, clang


def reject(fn, label: str) -> None:
    try:
        fn()
    except ValueError as exc:
        assert label in str(exc), str(exc)
    else:
        raise AssertionError("Stage67 must reject " + label)


def invoke(args: tuple[Path, ...]) -> dict:
    return execute(*args, 90)


def main() -> None:
    assert M["TARGET"] == "fs/built-in.a"
    assert M["SCOPE"] == "vmlinux-dirs=fs"
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        good = setup(root / "good")
        done = invoke(good)
        assert done["exit_code"] == 0
        assert done["archive_created"] is True
        assert done["prior_kernel_subtree_gate"] is True
        assert done["prior_mm_subtree_gate"] is True
        assert done["top_level_directory_scope"] == "vmlinux-dirs=fs"
        assert done["timed_out"] is False
        assert done["remaining_rejected_files"] == 64
        assert done["full_kernel_link_performed"] is False
        assert done["kernel_built"] is False and done["flash_ready"] is False
        assert (good[1] / "fs/built-in.a").is_file()
        assert json.loads((good[2] / M["OUTPUT"]).read_text()) == done

        fail_compiler = setup(root / "compiler-error")
        os.environ["EXP76_FS_FAIL"] = "yes"
        try:
            error = invoke(fail_compiler)
        finally:
            del os.environ["EXP76_FS_FAIL"]
        assert error["exit_code"] == 2
        assert error["archive_created"] is False
        assert "synthetic PREEMPT_RT incompatibility" in error["errors_excerpt"][0]

        bad_kernel = setup(root / "kernel-gate-failed")
        p = bad_kernel[3]
        value = json.loads(p.read_text())
        value["archive_created"] = False
        write(p, json.dumps(value))
        reject(lambda: invoke(bad_kernel), "Stage50 and Stage66")

        bad_mm = setup(root / "mm-gate-failed")
        p = bad_mm[4]
        value = json.loads(p.read_text())
        value["exit_code"] = 2
        write(p, json.dumps(value))
        reject(lambda: invoke(bad_mm), "Stage50 and Stage66")

        bad_scope = setup(root / "wrong-prior-scope")
        p = bad_scope[4]
        value = json.loads(p.read_text())
        value["top_level_directory_scope"] = "vmlinux-dirs=drivers"
        write(p, json.dumps(value))
        reject(lambda: invoke(bad_scope), "Stage50 and Stage66")

        missing_mm = setup(root / "missing-mm-archive")
        (missing_mm[1] / "mm/built-in.a").unlink()
        reject(lambda: invoke(missing_mm), "Stage50 and Stage66")

        missing_fs = setup(root / "missing-fs-makefile")
        (missing_fs[0] / "fs/Makefile").unlink()
        reject(lambda: invoke(missing_fs), "fs/Makefile missing")

        missing_git = setup(root / "missing-git")
        (missing_git[0] / ".git").rmdir()
        reject(lambda: invoke(missing_git), "isolated E404")

        invalid_config = setup(root / "invalid-config")
        write(invalid_config[1] / ".config", "CONFIG_PREEMPT_RT_FULL=n\n")
        reject(lambda: invoke(invalid_config), "PREEMPT_RT_FULL")

        missing_reject = setup(root / "lost-reject")
        (missing_reject[0] / "pending/00.rej").unlink()
        reject(lambda: invoke(missing_reject), "64 outstanding")

        drift = setup(root / "upstream-drift")
        write(drift[0] / "Makefile", "vmlinux-dirs := drivers\n")
        reject(lambda: invoke(drift), "directory dependency drift")

        image = setup(root / "unexpected-boot")
        write(image[1] / "arch/arm64/boot/Image.gz", "invalid artifact\n")
        reject(lambda: invoke(image), "Unexpected link or boot artifact")

        timeout = setup(root / "timeout")
        reject(lambda: execute(*timeout, 15), "Unsupported Stage67 timeout")
    print("EXP76_STAGE67_FS_SUBTREE_REGRESSIONS=13_PASS; KERNEL_BUILT=false; FLASH_READY=false")


if __name__ == "__main__":
    main()
