#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage69 security regression / NO FLASH
"""Require scoped prior archives and classify empty IPC without pretending compilation."""
from __future__ import annotations

import json
import os
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT / "tools/exp76-stage69-security-subtree.py"),
                   run_name="stage69_security_test")
PREV = runpy.run_path(str(ROOT / "tests/test_exp76_stage68_ipc_subtree.py"),
                      run_name="stage68_fixture_only")
write = PREV["write"]
execute = M["execute"]


def fixture(root: Path, *, ipc_enabled: bool = True) -> tuple[Path, ...]:
    kernel, out, report, s50, s66, s67, clang = PREV["fixture"](root)
    write(kernel / "security/Makefile", "obj-y += commoncap.o security.o\n")
    config = "CONFIG_PREEMPT_RT_FULL=y\nCONFIG_SECURITY=y\n"
    if ipc_enabled:
        config += "CONFIG_SYSVIPC=y\n"
    write(out / ".config", config)
    prior_ipc = out / "ipc/built-in.a"
    prior_ipc.parent.mkdir(parents=True, exist_ok=True)
    ipc_data = b"!<thin>\nIPC-OBJECT" if ipc_enabled else b"!<arch>\n"
    prior_ipc.write_bytes(ipc_data)
    s68 = root / "s68.json"
    write(s68, json.dumps({
        "stage": M["STAGE68"]["STAGE"],
        "target": "ipc/built-in.a",
        "top_level_directory_scope": "vmlinux-dirs=ipc",
        "prior_kernel_subtree_gate": True,
        "prior_mm_subtree_gate": True,
        "prior_fs_subtree_gate": True,
        "attempted": True,
        "exit_code": 0,
        "timed_out": False,
        "archive_created": True,
        "archive_has_members": ipc_enabled,
        "archive_bytes": len(ipc_data),
        "enabled_ipc_configs": ["CONFIG_SYSVIPC"] if ipc_enabled else [],
        "compile_semantics": "OBJECTS_PRESENT" if ipc_enabled else "CONFIG_DISABLED",
        "remaining_rejected_files": 64,
        "full_kernel_link_performed": False,
        "kernel_built": False,
        "flash_ready": False,
    }))
    make = clang / "make"
    write(make, (
        "#!/usr/bin/env python3\n"
        "# Python 3 / synthetic security Kbuild / archive only / NO FLASH\n"
        "import os, pathlib, sys\n"
        "assert sys.argv[-1] == 'security/built-in.a', sys.argv\n"
        "assert 'vmlinux-dirs=security' in sys.argv, sys.argv\n"
        "assert 'vmlinux' not in sys.argv and 'Image' not in sys.argv\n"
        "print('EXP76_STAGE69_SECURITY_ONLY')\n"
        "if os.environ.get('STAGE69_TEST_ERROR') == 'yes':\n"
        "    print('security/security.c:31: error: synthetic RT mismatch')\n"
        "    sys.exit(2)\n"
        "out = next(x[2:] for x in sys.argv if x.startswith('O='))\n"
        "archive = pathlib.Path(out) / 'security/built-in.a'\n"
        "archive.parent.mkdir(parents=True, exist_ok=True)\n"
        "if os.environ.get('STAGE69_EMPTY') == 'yes':\n"
        "    archive.write_bytes(b'!<thin>\\n')\n"
        "else:\n"
        "    archive.write_bytes(b'!<thin>\\nsecurity-members')\n"
    ))
    make.chmod(0o755)
    return kernel, out, report, s50, s66, s67, s68, clang


def invoke(args: tuple[Path, ...]) -> dict:
    return execute(*args, 90)


def reject(fn, message: str) -> None:
    try:
        fn()
    except ValueError as e:
        assert message in str(e), str(e)
    else:
        raise AssertionError("Missing expected Stage69 rejection: " + message)


def main() -> None:
    assert M["TARGET"] == "security/built-in.a"
    assert M["SCOPE"] == "vmlinux-dirs=security"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        good = fixture(root / "good")
        passed = invoke(good)
        assert passed["exit_code"] == 0
        assert passed["archive_created"] is True
        assert passed["archive_has_members"] is True
        assert passed["ipc_compile_semantics"] == "OBJECTS_PRESENT"
        assert all(passed["prior_" + name + "_subtree_gate"]
                   for name in ("kernel", "mm", "fs", "ipc"))
        assert not passed["kernel_built"] and not passed["flash_ready"]
        assert json.loads((good[2] / M["OUTPUT"]).read_text()) == passed

        disabled_ipc = fixture(root / "ipc-disabled", ipc_enabled=False)
        skipped = invoke(disabled_ipc)
        assert skipped["ipc_compile_semantics"] == "CONFIG_DISABLED"
        assert skipped["archive_has_members"] is True
        assert skipped["exit_code"] == 0

        error_case = fixture(root / "compile-error")
        os.environ["STAGE69_TEST_ERROR"] = "yes"
        try:
            failed = invoke(error_case)
        finally:
            del os.environ["STAGE69_TEST_ERROR"]
        assert failed["exit_code"] == 2 and not failed["archive_created"]
        assert "synthetic RT mismatch" in failed["errors_excerpt"][0]

        empty_security = fixture(root / "empty-security")
        os.environ["STAGE69_EMPTY"] = "yes"
        try:
            empty = invoke(empty_security)
        finally:
            del os.environ["STAGE69_EMPTY"]
        assert empty["archive_created"] is True
        assert empty["archive_has_members"] is False
        assert "zero members" in empty["errors_excerpt"][0]

        wrong_ipc_semantics = fixture(root / "wrong-ipc")
        p = wrong_ipc_semantics[6]
        v = json.loads(p.read_text())
        v["compile_semantics"] = "OBJECTS_PRESENT"
        v["archive_has_members"] = True
        write(p, json.dumps(v))
        (wrong_ipc_semantics[1] / "ipc/built-in.a").write_bytes(b"!<thin>\n")
        reject(lambda: invoke(wrong_ipc_semantics), "Stage50/66/67/68")

        missing_fs = fixture(root / "missing-fs")
        (missing_fs[1] / "fs/built-in.a").unlink()
        reject(lambda: invoke(missing_fs), "Stage50/66/67/68")

        bad_ipc_8 = fixture(root / "ipc-empty-configured")
        (bad_ipc_8[1] / "ipc/built-in.a").write_bytes(b"!<thin>\n")
        reject(lambda: invoke(bad_ipc_8), "Stage50/66/67/68")

        mismatch = fixture(root / "missing-security-config")
        write(mismatch[1] / ".config", "CONFIG_PREEMPT_RT_FULL=y\n")
        reject(lambda: invoke(mismatch), "CONFIG_SECURITY=y")

        missing_sec = fixture(root / "missing-security-makefile")
        (missing_sec[0] / "security/Makefile").unlink()
        reject(lambda: invoke(missing_sec), "security/Makefile missing")

        no_git = fixture(root / "missing-git")
        (no_git[0] / ".git").rmdir()
        reject(lambda: invoke(no_git), "isolated E404")

        no_rej = fixture(root / "missing-reject")
        (no_rej[0] / "pending/00.rej").unlink()
        reject(lambda: invoke(no_rej), "64 outstanding")

        image = fixture(root / "unexpected-Image")
        write(image[1] / "arch/arm64/boot/Image", "forbidden")
        reject(lambda: invoke(image), "Unexpected link or boot artifact")

        timeout = fixture(root / "bad-timeout")
        reject(lambda: execute(*timeout, 15), "Unsupported Stage69")
    print("EXP76_STAGE69_SECURITY_REGRESSIONS=13_PASS; KERNEL_BUILT=false; FLASH_READY=false")


if __name__ == "__main__":
    main()
