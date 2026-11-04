#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage72 NET tests / NO FLASH
"""Validate real archive-member gating and previous IPC/security Kbuild gates."""
from __future__ import annotations

import json
import os
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT / "tools/exp76-stage72-net-subtree.py"),
                   run_name="stage72_net_tests")
PREV = runpy.run_path(str(ROOT / "tests/test_exp76_stage69_security_subtree.py"),
                      run_name="stage69_fixture_only")
write = PREV["write"]
execute = M["execute"]


def fixture(root: Path, *, ipc_enabled: bool = True) -> tuple[Path, ...]:
    kernel, out, report, s50, s66, s67, s68, clang = PREV["fixture"](
        root, ipc_enabled=ipc_enabled,
    )
    write(kernel / "net/Makefile", "obj-y += socket.o\n")
    config = out / ".config"
    write(config, config.read_text(encoding="utf-8") + "CONFIG_NET=y\n")
    security_archive = out / "security/built-in.a"
    security_archive.parent.mkdir(parents=True, exist_ok=True)
    security_archive.write_bytes(b"!<thin>\nsecurity-members")
    s69 = root / "stage69.json"
    write(s69, json.dumps({
        "stage": M["STAGE69"]["STAGE"],
        "target": M["STAGE69"]["TARGET"],
        "top_level_directory_scope": M["STAGE69"]["SCOPE"],
        "prior_kernel_subtree_gate": True,
        "prior_mm_subtree_gate": True,
        "prior_fs_subtree_gate": True,
        "prior_ipc_subtree_gate": True,
        "ipc_compile_semantics":
            "OBJECTS_PRESENT" if ipc_enabled else "CONFIG_DISABLED",
        "attempted": True,
        "exit_code": 0,
        "timed_out": False,
        "archive_created": True,
        "archive_has_members": True,
        "archive_bytes": security_archive.stat().st_size,
        "remaining_rejected_files": 64,
        "full_kernel_link_performed": False,
        "kernel_built": False,
        "flash_ready": False,
    }))
    fake_make = clang / "make"
    write(fake_make, (
        "#!/usr/bin/env python3\n"
        "# Python 3 / synthetic NET Kbuild / scoped archive / NO FLASH\n"
        "import os, pathlib, sys\n"
        "assert sys.argv[-1] == 'net/built-in.a', sys.argv\n"
        "assert 'vmlinux-dirs=net' in sys.argv, sys.argv\n"
        "assert not any(x.startswith('vmlinux-dirs=') and x != 'vmlinux-dirs=net' for x in sys.argv)\n"
        "assert 'vmlinux' not in sys.argv and 'Image' not in sys.argv\n"
        "print('STAGE72_SCOPED_NET_KBUILD')\n"
        "if os.environ.get('STAGE72_MAKE_ERROR') == 'yes':\n"
        "    print('net/core/dev.c:42: error: synthetic RT mismatch')\n"
        "    sys.exit(2)\n"
        "if os.environ.get('STAGE72_NO_ARCHIVE') == 'yes':\n"
        "    sys.exit(0)\n"
        "out = next(x[2:] for x in sys.argv if x.startswith('O='))\n"
        "archive = pathlib.Path(out) / 'net/built-in.a'\n"
        "archive.parent.mkdir(parents=True, exist_ok=True)\n"
        "if os.environ.get('STAGE72_EMPTY_ARCHIVE') == 'yes':\n"
        "    archive.write_bytes(b'!<arch>\\n')\n"
        "else:\n"
        "    archive.write_bytes(b'!<thin>\\nnet-members')\n"
    ))
    fake_make.chmod(0o755)
    fake_ar = clang / "llvm-ar"
    write(fake_ar, (
        "#!/usr/bin/env python3\n"
        "# Python 3 / synthetic llvm-ar t verifier / NO FLASH\n"
        "import os, pathlib, sys\n"
        "assert sys.argv[1] == 't' and len(sys.argv) == 3, sys.argv\n"
        "assert pathlib.Path(sys.argv[2]).name == 'built-in.a'\n"
        "if os.environ.get('STAGE72_AR_ERROR') == 'yes':\n"
        "    print('invalid archive', file=sys.stderr)\n"
        "    sys.exit(1)\n"
        "if os.environ.get('STAGE72_AR_EMPTY') == 'yes':\n"
        "    sys.exit(0)\n"
        "print('socket.o\\ncore/built-in.a')\n"
    ))
    fake_ar.chmod(0o755)
    return kernel, out, report, s50, s66, s67, s68, s69, clang


def invoke(args: tuple[Path, ...]) -> dict:
    return execute(*args, 90)


def reject(fn, error: str) -> None:
    try:
        fn()
    except ValueError as exc:
        assert error in str(exc), str(exc)
    else:
        raise AssertionError("Expected Stage72 fail-closed error: " + error)


def change(path: Path, field: str, value) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data[field] = value
    write(path, json.dumps(data))


def with_env(name: str, args: tuple[Path, ...]) -> dict:
    os.environ[name] = "yes"
    try:
        return invoke(args)
    finally:
        del os.environ[name]


def main() -> None:
    assert M["TARGET"] == "net/built-in.a"
    assert M["SCOPE"] == "vmlinux-dirs=net"
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        good = fixture(root / "good")
        result = invoke(good)
        assert result["archive_created"] is True
        assert result["archive_has_members"] is True
        assert result["archive_members_count"] == 2
        assert result["archive_members_sample"] == [
            "socket.o", "core/built-in.a",
        ]
        assert result["archive_inspection_exit_code"] == 0
        assert result["exit_code"] == 0 and result["timed_out"] is False
        assert result["errors_excerpt"] == []
        assert result["top_level_directory_scope"] == "vmlinux-dirs=net"
        assert result["prior_security_subtree_gate"] is True
        assert result["full_kernel_link_performed"] is False
        assert not result["kernel_built"] and not result["flash_ready"]
        assert json.loads((good[2] / M["OUTPUT"]).read_text()) == result

        disabled_ipc = fixture(root / "disabled-ipc", ipc_enabled=False)
        checked = invoke(disabled_ipc)
        assert checked["archive_has_members"] is True

        make_error = fixture(root / "compile-error")
        failed = with_env("STAGE72_MAKE_ERROR", make_error)
        assert failed["exit_code"] == 2
        assert failed["archive_created"] is False
        assert failed["archive_inspection_exit_code"] is None
        assert "synthetic RT mismatch" in failed["errors_excerpt"][0]

        missing_archive = fixture(root / "no-archive")
        empty = with_env("STAGE72_NO_ARCHIVE", missing_archive)
        assert empty["archive_created"] is False
        assert empty["archive_has_members"] is False
        assert "without creating" in empty["errors_excerpt"][0]

        ar_error = fixture(root / "invalid-archive")
        invalid = with_env("STAGE72_AR_ERROR", ar_error)
        assert invalid["archive_created"] is True
        assert invalid["archive_inspection_exit_code"] == 1
        assert invalid["archive_has_members"] is False
        assert "llvm-ar t rejected" in invalid["errors_excerpt"][0]

        ar_empty = fixture(root / "empty-ar")
        no_members = with_env("STAGE72_AR_EMPTY", ar_empty)
        assert no_members["archive_created"] is True
        assert no_members["archive_members_count"] == 0
        assert no_members["archive_has_members"] is False
        assert "llvm-ar found no NET" in no_members["errors_excerpt"][0]

        previous_failure = fixture(root / "security-failed")
        change(previous_failure[7], "archive_has_members", False)
        reject(lambda: invoke(previous_failure), "Stage50/66/67/68/69")

        previous_scope = fixture(root / "security-wrong-scope")
        change(previous_scope[7], "top_level_directory_scope",
               "vmlinux-dirs=drivers")
        reject(lambda: invoke(previous_scope), "Stage50/66/67/68/69")

        earlier_fs = fixture(root / "fs-gate")
        (earlier_fs[1] / "fs/built-in.a").unlink()
        reject(lambda: invoke(earlier_fs), "Stage50/66/67/68/69")

        no_security_archive = fixture(root / "security-archive-missing")
        (no_security_archive[1] / "security/built-in.a").unlink()
        reject(lambda: invoke(no_security_archive), "Stage50/66/67/68/69")

        no_net = fixture(root / "missing-net-makefile")
        (no_net[0] / "net/Makefile").unlink()
        reject(lambda: invoke(no_net), "net/Makefile missing")

        no_git = fixture(root / "missing-git")
        (no_git[0] / ".git").rmdir()
        reject(lambda: invoke(no_git), "isolated E404")

        no_config = fixture(root / "NET-disabled")
        write(no_config[1] / ".config",
              "CONFIG_PREEMPT_RT_FULL=y\nCONFIG_SECURITY=y\n")
        reject(lambda: invoke(no_config), "NET=y")

        no_reject = fixture(root / "reject-missing")
        (no_reject[0] / "pending/00.rej").unlink()
        reject(lambda: invoke(no_reject), "64 unresolved")

        kbuild_drift = fixture(root / "makefile-drift")
        write(kbuild_drift[0] / "Makefile", "vmlinux-dirs := drivers\n")
        reject(lambda: invoke(kbuild_drift), "directory dependency drift")

        unexpected_image = fixture(root / "unexpected-image")
        write(unexpected_image[1] / "arch/arm64/boot/Image", "forbidden")
        reject(lambda: invoke(unexpected_image),
               "Unexpected link or boot artifact")

        short_timeout = fixture(root / "timeout")
        reject(lambda: execute(*short_timeout, 15), "Unsupported Stage72")
    print(
        "EXP76_STAGE72_NET_SUBTREE_REGRESSIONS=17_PASS; "
        "KERNEL_BUILT=false; FLASH_READY=false"
    )


if __name__ == "__main__":
    main()
