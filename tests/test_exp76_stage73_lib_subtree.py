#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage73 LIB Kbuild tests / NO FLASH
"""Validate bounded lib archive build, llvm-ar members and all prior gates."""
from __future__ import annotations

import json
import os
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT / "tools/exp76-stage73-lib-subtree.py"),
                   run_name="exp76_stage73_lib_tests")
PREV = runpy.run_path(str(ROOT / "tests/test_exp76_stage72_net_subtree.py"),
                      run_name="exp76_stage72_fixture_only")
write = PREV["write"]
execute = M["execute"]


def fixture(root: Path, *, ipc_enabled: bool = True) -> tuple[Path, ...]:
    kernel, out, report, s50, s66, s67, s68, s69, clang = PREV["fixture"](
        root, ipc_enabled=ipc_enabled,
    )
    write(kernel / "lib/Makefile", "obj-y += string.o rbtree.o\n")
    net_archive = out / "net/built-in.a"
    net_archive.parent.mkdir(parents=True, exist_ok=True)
    net_archive.write_bytes(b"!<thin>\nnet-object-members")
    s72 = root / "s72.json"
    write(s72, json.dumps({
        "stage": M["STAGE72"]["STAGE"],
        "target": "net/built-in.a",
        "top_level_directory_scope": "vmlinux-dirs=net",
        "prior_security_subtree_gate": True,
        "attempted": True,
        "exit_code": 0,
        "timed_out": False,
        "archive_created": True,
        "archive_has_members": True,
        "archive_inspection_exit_code": 0,
        "archive_members_count": 2,
        "archive_bytes": net_archive.stat().st_size,
        "remaining_rejected_files": 64,
        "full_kernel_link_performed": False,
        "kernel_built": False,
        "flash_ready": False,
    }))
    make = clang / "make"
    write(make, (
        "#!/usr/bin/env python3\n"
        "# Python 3 / synthetic scoped lib Kbuild / NO FLASH\n"
        "import os, pathlib, sys\n"
        "assert sys.argv[-1] == 'lib/built-in.a', sys.argv\n"
        "assert 'vmlinux-dirs=lib' in sys.argv, sys.argv\n"
        "assert 'vmlinux-dirs=net' not in sys.argv, sys.argv\n"
        "assert 'vmlinux' not in sys.argv and 'Image' not in sys.argv\n"
        "print('EXP76_STAGE73_LIB_SCOPE')\n"
        "if os.environ.get('STAGE73_MAKE_ERROR') == 'yes':\n"
        "    print('lib/string.c:22: error: synthetic RT mismatch')\n"
        "    sys.exit(2)\n"
        "if os.environ.get('STAGE73_NO_ARCHIVE') == 'yes':\n"
        "    sys.exit(0)\n"
        "out = next(x[2:] for x in sys.argv if x.startswith('O='))\n"
        "p = pathlib.Path(out) / 'lib/built-in.a'\n"
        "p.parent.mkdir(parents=True, exist_ok=True)\n"
        "p.write_bytes(b'!<thin>\\nsynthetic-lib')\n"
    ))
    make.chmod(0o755)
    ar = clang / "llvm-ar"
    write(ar, (
        "#!/usr/bin/env python3\n"
        "# Python 3 / synthetic llvm-ar lib membership / NO FLASH\n"
        "import os, pathlib, sys\n"
        "assert sys.argv[1] == 't' and len(sys.argv) == 3\n"
        "assert sys.argv[2].endswith('lib/built-in.a')\n"
        "if os.environ.get('STAGE73_AR_FAIL') == 'yes':\n"
        "    print('invalid archive', file=sys.stderr)\n"
        "    sys.exit(1)\n"
        "if os.environ.get('STAGE73_AR_EMPTY') == 'yes':\n"
        "    sys.exit(0)\n"
        "print('string.o\\nrbtree.o')\n"
    ))
    ar.chmod(0o755)
    return kernel, out, report, s50, s66, s67, s68, s69, s72, clang


def invoke(args: tuple[Path, ...]) -> dict:
    return execute(*args, 90)


def reject(fn, message: str) -> None:
    try:
        fn()
    except ValueError as err:
        assert message in str(err), str(err)
    else:
        raise AssertionError("Expected Stage73 fail-closed: " + message)


def alter(path: Path, key: str, value) -> None:
    obj = json.loads(path.read_text(encoding="utf-8"))
    obj[key] = value
    write(path, json.dumps(obj))


def run_env(name: str, args: tuple[Path, ...]) -> dict:
    os.environ[name] = "yes"
    try:
        return invoke(args)
    finally:
        del os.environ[name]


def main() -> None:
    assert M["TARGET"] == "lib/built-in.a"
    assert M["SCOPE"] == "vmlinux-dirs=lib"
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        good = fixture(root / "good")
        result = invoke(good)
        assert result["archive_created"] is True
        assert result["archive_has_members"] is True
        assert result["archive_members_count"] == 2
        assert result["archive_members_sample"] == ["string.o", "rbtree.o"]
        assert result["archive_inspection_exit_code"] == 0
        assert result["exit_code"] == 0
        assert result["timed_out"] is False
        assert result["prior_net_subtree_gate"] is True
        assert result["top_level_directory_scope"] == "vmlinux-dirs=lib"
        assert not result["kernel_built"] and not result["flash_ready"]
        assert json.loads((good[2] / M["OUTPUT"]).read_text()) == result

        disabled_ipc = fixture(root / "disabled-ipc", ipc_enabled=False)
        assert invoke(disabled_ipc)["archive_has_members"] is True

        make_error = fixture(root / "make-error")
        failed = run_env("STAGE73_MAKE_ERROR", make_error)
        assert failed["exit_code"] == 2 and not failed["archive_created"]
        assert "synthetic RT mismatch" in failed["errors_excerpt"][0]

        no_archive = fixture(root / "no-archive")
        missing = run_env("STAGE73_NO_ARCHIVE", no_archive)
        assert missing["exit_code"] == 0 and not missing["archive_created"]
        assert "without creating" in missing["errors_excerpt"][0]

        ar_error = fixture(root / "ar-error")
        invalid = run_env("STAGE73_AR_FAIL", ar_error)
        assert invalid["archive_created"]
        assert not invalid["archive_has_members"]
        assert invalid["archive_inspection_exit_code"] == 1

        ar_empty = fixture(root / "ar-empty")
        empty = run_env("STAGE73_AR_EMPTY", ar_empty)
        assert empty["archive_created"]
        assert empty["archive_members_count"] == 0
        assert "no verified object members" in empty["errors_excerpt"][0]

        bad_net = fixture(root / "net-report-failed")
        alter(bad_net[8], "archive_inspection_exit_code", 2)
        reject(lambda: invoke(bad_net), "Stage50/66/67/68/69/72")

        bad_net_size = fixture(root / "net-size-drift")
        alter(bad_net_size[8], "archive_bytes", 99)
        reject(lambda: invoke(bad_net_size), "Stage50/66/67/68/69/72")

        bad_net_archive = fixture(root / "net-missing")
        (bad_net_archive[1] / "net/built-in.a").unlink()
        reject(lambda: invoke(bad_net_archive), "Stage50/66/67/68/69/72")

        bad_security = fixture(root / "security-failed")
        alter(bad_security[7], "archive_has_members", False)
        reject(lambda: invoke(bad_security), "Stage50/66/67/68/69/72")

        missing_lib = fixture(root / "no-lib")
        (missing_lib[0] / "lib/Makefile").unlink()
        reject(lambda: invoke(missing_lib), "lib/Makefile missing")

        wrong_config = fixture(root / "no-RT")
        write(wrong_config[1] / ".config", "CONFIG_NET=y\nCONFIG_SECURITY=y\n")
        reject(lambda: invoke(wrong_config), "PREEMPT_RT")

        missing_reject = fixture(root / "missing-reject")
        (missing_reject[0] / "pending/00.rej").unlink()
        reject(lambda: invoke(missing_reject), "64 unresolved")

        invalid_kbuild = fixture(root / "root-drift")
        write(invalid_kbuild[0] / "Makefile", "vmlinux-dirs := drivers\n")
        reject(lambda: invoke(invalid_kbuild), "dependency drift")

        accidental_image = fixture(root / "image-should-not-exist")
        write(accidental_image[1] / "arch/arm64/boot/Image.gz", "forbidden")
        reject(lambda: invoke(accidental_image),
               "Unexpected link or boot artifact")

        bad_timeout = fixture(root / "bad-timeout")
        reject(lambda: execute(*bad_timeout, 15), "Unsupported Stage73")
    print(
        "EXP76_STAGE73_LIB_SUBTREE_REGRESSIONS=16_PASS; "
        "KERNEL_BUILT=false; FLASH_READY=false"
    )


if __name__ == "__main__":
    main()
