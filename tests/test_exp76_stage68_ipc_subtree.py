#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage68 IPC regression / NO FLASH
"""Require all prior scoped Kbuild gates, preserve RT rejects and block boot."""
from __future__ import annotations

import json
import os
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT / "tools/exp76-stage68-ipc-subtree.py"),
                   run_name="exp76_stage68_regression")
execute = M["execute"]


def write(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def fixture(root: Path) -> tuple[Path, Path, Path, Path, Path, Path, Path]:
    kernel, out, report, s50, s66, s67, clang = (
        root / "kernel", root / "out", root / "report",
        root / "s50.json", root / "s66.json", root / "s67.json",
        root / "clang",
    )
    (kernel / ".git").mkdir(parents=True)
    write(kernel / "ipc/Makefile", "obj-y += util.o msg.o sem.o\n")
    write(kernel / "scripts/Makefile.build",
          "$(obj)/built-in.a: $(real-obj-y) FORCE\n")
    write(kernel / "Makefile", (
        "vmlinux-dirs\t:= $(patsubst %/,%,$(filter %/,\n"
        "$(sort $(vmlinux-deps)): $(vmlinux-dirs) ;\n"
        "$(vmlinux-dirs): prepare scripts\n"
        "\t$(Q)$(MAKE) $(build)=$@ need-builtin=1\n"
    ))
    write(out / ".config", "CONFIG_PREEMPT_RT_FULL=y\nCONFIG_SYSVIPC=y\n")
    write(out / "include/generated/asm-offsets.h", "#define E404 1\n")
    for i in range(64):
        write(kernel / f"pending/{i:02d}.rej", "RT reject\n")
    for directory in ("kernel", "mm", "fs"):
        archive = out / directory / "built-in.a"
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(b"!<thin>\nsynthetic-prior")
    common = {
        "attempted": True, "exit_code": 0, "archive_created": True,
        "archive_bytes": 25, "remaining_rejected_files": 64,
        "full_kernel_link_performed": False,
        "kernel_built": False, "flash_ready": False,
    }
    write(s50, json.dumps({
        **common, "stage": "EXP76_STAGE50_KERNEL_SUBTREE_KBUILD_ARCHIVE_NONFLASH",
        "target": "kernel/built-in.a",
        "top_level_directory_scope": "vmlinux-dirs=kernel",
        "baseline_22_objects_compiled": True,
    }))
    write(s66, json.dumps({
        **common, "stage": "EXP76_STAGE66_MM_SUBTREE_KBUILD_ARCHIVE_NONFLASH",
        "target": "mm/built-in.a", "top_level_directory_scope": "vmlinux-dirs=mm",
        "prior_kernel_subtree_gate": True, "timed_out": False,
    }))
    write(s67, json.dumps({
        **common, "stage": "EXP76_STAGE67_FS_SUBTREE_KBUILD_ARCHIVE_NONFLASH",
        "target": "fs/built-in.a", "top_level_directory_scope": "vmlinux-dirs=fs",
        "prior_kernel_subtree_gate": True, "prior_mm_subtree_gate": True,
        "timed_out": False,
    }))
    clang.mkdir(parents=True)
    for compiler in ("clang", "ld.lld", "llvm-ar"):
        write(clang / compiler, "pinned Android clang fixture\n")
    fake_make = clang / "make"
    write(fake_make, (
        "#!/usr/bin/env python3\n"
        "# Python 3 / synthetic make / IPC archive target / NO FLASH\n"
        "import os, pathlib, sys\n"
        "assert sys.argv[-1] == 'ipc/built-in.a', sys.argv\n"
        "assert 'vmlinux-dirs=ipc' in sys.argv, sys.argv\n"
        "assert not any(x.startswith('vmlinux-dirs=') and x != 'vmlinux-dirs=ipc' for x in sys.argv)\n"
        "assert 'vmlinux' not in sys.argv and 'Image' not in sys.argv\n"
        "print('STAGE68_IPC_SCOPE_CONFIRMED')\n"
        "if os.environ.get('STAGE68_TEST_ERROR') == 'yes':\n"
        "    print('ipc/sem.c:31: error: synthetic RT conflict')\n"
        "    sys.exit(2)\n"
        "out = next(x[2:] for x in sys.argv if x.startswith('O='))\n"
        "p = pathlib.Path(out) / 'ipc/built-in.a'\n"
        "p.parent.mkdir(parents=True, exist_ok=True)\n"
        "if os.environ.get('STAGE68_TEST_EMPTY') == 'yes':\n"
        "    p.write_bytes(b'!<thin>\\n')\n"
        "elif os.environ.get('STAGE68_TEST_EMPTY') == 'normal':\n"
        "    p.write_bytes(b'!<arch>\\n')\n"
        "elif os.environ.get('STAGE68_TEST_EMPTY') == 'invalid':\n"
        "    p.write_bytes(b'not-an-ar')\n"
        "else:\n"
        "    p.write_bytes(b'!<thin>\\nsynthetic-ipc')\n"
    ))
    fake_make.chmod(0o755)
    return kernel, out, report, s50, s66, s67, clang


def reject(fn, reason: str) -> None:
    try:
        fn()
    except ValueError as exc:
        assert reason in str(exc), str(exc)
    else:
        raise AssertionError("Expected fail-closed Stage68 gate: " + reason)


def run(args: tuple[Path, ...]) -> dict:
    return execute(*args, 90)


def main() -> None:
    assert M["TARGET"] == "ipc/built-in.a"
    assert M["SCOPE"] == "vmlinux-dirs=ipc"
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        good = fixture(root / "good")
        passed = run(good)
        assert passed["archive_created"] and passed["exit_code"] == 0
        assert passed["prior_kernel_subtree_gate"]
        assert passed["prior_mm_subtree_gate"]
        assert passed["prior_fs_subtree_gate"]
        assert passed["timed_out"] is False
        assert passed["archive_has_members"] is True
        assert passed["enabled_ipc_configs"] == ["CONFIG_SYSVIPC"]
        assert passed["compile_semantics"] == "OBJECTS_PRESENT"
        assert passed["top_level_directory_scope"] == "vmlinux-dirs=ipc"
        assert passed["remaining_rejected_files"] == 64
        assert not passed["kernel_built"] and not passed["flash_ready"]
        assert (good[1] / "ipc/built-in.a").is_file()
        assert json.loads((good[2] / M["OUTPUT"]).read_text()) == passed

        failed = fixture(root / "compile-error")
        os.environ["STAGE68_TEST_ERROR"] = "yes"
        try:
            result = run(failed)
        finally:
            del os.environ["STAGE68_TEST_ERROR"]
        assert result["exit_code"] == 2 and not result["archive_created"]
        assert "synthetic RT conflict" in result["errors_excerpt"][0]

        disabled = fixture(root / "disabled-by-config")
        write(disabled[1] / ".config", "CONFIG_PREEMPT_RT_FULL=y\n")
        os.environ["STAGE68_TEST_EMPTY"] = "yes"
        try:
            config_disabled = run(disabled)
        finally:
            del os.environ["STAGE68_TEST_EMPTY"]
        assert config_disabled["exit_code"] == 0
        assert config_disabled["archive_created"] is True
        assert config_disabled["archive_bytes"] == 8
        assert config_disabled["archive_has_members"] is False
        assert config_disabled["enabled_ipc_configs"] == []
        assert config_disabled["compile_semantics"] == "CONFIG_DISABLED"
        assert config_disabled["archive_magic_hex"] == b"!<thin>\n".hex()
        assert config_disabled["errors_excerpt"] == []

        disabled_normal = fixture(root / "disabled-normal-ar")
        write(disabled_normal[1] / ".config", "CONFIG_PREEMPT_RT_FULL=y\n")
        os.environ["STAGE68_TEST_EMPTY"] = "normal"
        try:
            normal_ar = run(disabled_normal)
        finally:
            del os.environ["STAGE68_TEST_EMPTY"]
        assert normal_ar["compile_semantics"] == "CONFIG_DISABLED"
        assert normal_ar["archive_has_members"] is False
        assert normal_ar["archive_magic_hex"] == b"!<arch>\n".hex()
        assert normal_ar["errors_excerpt"] == []

        invalid_header = fixture(root / "invalid-ar-magic")
        write(invalid_header[1] / ".config", "CONFIG_PREEMPT_RT_FULL=y\n")
        os.environ["STAGE68_TEST_EMPTY"] = "invalid"
        try:
            unrecognized = run(invalid_header)
        finally:
            del os.environ["STAGE68_TEST_EMPTY"]
        assert unrecognized["compile_semantics"] == "ERROR_UNKNOWN_ARCHIVE"
        assert unrecognized["archive_has_members"] is False
        assert len(unrecognized["errors_excerpt"]) == 1

        invalid_empty = fixture(root / "unexpected-empty")
        os.environ["STAGE68_TEST_EMPTY"] = "yes"
        try:
            unexpected = run(invalid_empty)
        finally:
            del os.environ["STAGE68_TEST_EMPTY"]
        assert unexpected["archive_created"] is True
        assert unexpected["archive_has_members"] is False
        assert unexpected["compile_semantics"] == "ERROR_EMPTY_WITH_IPC_CONFIG_ENABLED"
        assert len(unexpected["errors_excerpt"]) == 1

        bad_kernel = fixture(root / "kernel-gate")
        p = bad_kernel[3]
        j = json.loads(p.read_text())
        j["archive_created"] = False
        write(p, json.dumps(j))
        reject(lambda: run(bad_kernel), "Stage50/66/67")

        bad_mm = fixture(root / "mm-gate")
        p = bad_mm[4]
        j = json.loads(p.read_text())
        j["exit_code"] = 2
        write(p, json.dumps(j))
        reject(lambda: run(bad_mm), "Stage50/66/67")

        bad_fs = fixture(root / "fs-gate")
        p = bad_fs[5]
        j = json.loads(p.read_text())
        j["top_level_directory_scope"] = "vmlinux-dirs=drivers"
        write(p, json.dumps(j))
        reject(lambda: run(bad_fs), "Stage50/66/67")

        no_fs_archive = fixture(root / "missing-fs-archive")
        (no_fs_archive[1] / "fs/built-in.a").unlink()
        reject(lambda: run(no_fs_archive), "Stage50/66/67")

        no_ipc = fixture(root / "missing-ipc")
        (no_ipc[0] / "ipc/Makefile").unlink()
        reject(lambda: run(no_ipc), "ipc/Makefile missing")

        no_git = fixture(root / "missing-git")
        (no_git[0] / ".git").rmdir()
        reject(lambda: run(no_git), "isolated E404")

        config_drift = fixture(root / "no-rt-config")
        write(config_drift[1] / ".config", "CONFIG_PREEMPT_RT_FULL=n\n")
        reject(lambda: run(config_drift), "CONFIG_PREEMPT_RT_FULL=y")

        no_reject = fixture(root / "lost-reject")
        (no_reject[0] / "pending/00.rej").unlink()
        reject(lambda: run(no_reject), "64 unresolved")

        root_drift = fixture(root / "root-makefile-drift")
        write(root_drift[0] / "Makefile", "vmlinux-dirs := drivers\n")
        reject(lambda: run(root_drift), "dependency scope drift")

        unexpected_boot = fixture(root / "unexpected-vmlinux")
        write(unexpected_boot[1] / "vmlinux", "not allowed\n")
        reject(lambda: run(unexpected_boot), "Unexpected link or boot artifact")

        timeout = fixture(root / "timeout")
        reject(lambda: execute(*timeout, 15), "Unsupported Stage68 IPC")
    print("EXP76_STAGE68_IPC_SUBTREE_REGRESSIONS=17_PASS; KERNEL_BUILT=false; FLASH_READY=false")


if __name__ == "__main__":
    main()
