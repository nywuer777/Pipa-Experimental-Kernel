#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage77 header tests / NO FLASH
"""Test Kbuild-generated compile.h before driver compilation, fail closed."""
from __future__ import annotations

import json
import os
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(
    str(ROOT / "tools/exp76-stage77-compile-h-preflight.py"),
    run_name="exp76_stage77_tests",
)
PREV = runpy.run_path(
    str(ROOT / "tests/test_exp76_stage76_drivers_subtree.py"),
    run_name="exp76_stage76_fixture",
)
write = PREV["write"]


def fixture(root: Path) -> tuple[Path, ...]:
    kernel, out, report, s50, s66, s67, s68, s69, s72, s73, s75, clang = (
        PREV["fixture"](root)
    )
    write(kernel / "init/Makefile", (
        "# Kbuild compile header fixture\n"
        "$(obj)/version.o: include/generated/compile.h\n"
        "include/generated/compile.h: FORCE\n"
        "\t$(Q)$(CONFIG_SHELL) $(srctree)/scripts/mkcompile_h $@\n"
    ))
    write(kernel / "init/version.c", "int init_version_fixture;\n")
    write(kernel / "scripts/mkcompile_h", (
        "#!/bin/sh\n"
        "# Fixture for pinned E404 compile header generator\n"
        "UTS_VERSION=\"test\"\n"
    ))
    make = clang / "make"
    write(make, (
        "#!/usr/bin/env python3\n"
        "# Python 3 / synthetic init/version.o Kbuild / NO FLASH\n"
        "import os, pathlib, sys\n"
        "assert sys.argv[-1] == 'init/version.o', sys.argv\n"
        "assert not any(x.startswith('vmlinux-dirs=') for x in sys.argv)\n"
        "assert 'vmlinux' not in sys.argv and 'Image' not in sys.argv\n"
        "out = next(x[2:] for x in sys.argv if x.startswith('O='))\n"
        "out = pathlib.Path(out)\n"
        "if os.environ.get('STAGE77_MAKE_ERROR') == 'yes':\n"
        "    print('init/version.c:10: error: synthetic RT failure')\n"
        "    sys.exit(2)\n"
        "if os.environ.get('STAGE77_NO_OUTPUT') == 'yes':\n"
        "    sys.exit(0)\n"
        "h = out / 'include/generated/compile.h'\n"
        "h.parent.mkdir(parents=True, exist_ok=True)\n"
        "if os.environ.get('STAGE77_INVALID_HEADER') == 'yes':\n"
        "    h.write_text('#define UTS_MACHINE \"test\"\\n')\n"
        "else:\n"
        "    h.write_text('#define UTS_MACHINE \"arm64\"\\n'\n"
        "                 '#define UTS_VERSION \"#1 PREEMPT\"\\n'\n"
        "                 '#define LINUX_COMPILE_BY \"CI\"\\n'\n"
        "                 '#define LINUX_COMPILE_HOST \"ci\"\\n'\n"
        "                 '#define LINUX_COMPILER \"Clang 21\"\\n')\n"
        "if os.environ.get('STAGE77_NO_OBJECT') != 'yes':\n"
        "    obj = out / 'init/version.o'\n"
        "    obj.parent.mkdir(parents=True, exist_ok=True)\n"
        "    obj.write_bytes(b'ELF-SYNTHETIC-NONFLASH')\n"
    ))
    make.chmod(0o755)
    return kernel, out, report, s50, s66, s67, s68, s69, s72, s73, s75, clang


def invoke(args: tuple[Path, ...]) -> dict:
    return M["execute"](*args, 90)


def reject(fn, expected: str) -> None:
    try:
        fn()
    except ValueError as exc:
        assert expected in str(exc), str(exc)
    else:
        raise AssertionError("Missing Stage77 fail-closed rejection " + expected)


def with_env(var: str, args: tuple[Path, ...]) -> dict:
    os.environ[var] = "yes"
    try:
        return invoke(args)
    finally:
        del os.environ[var]


def change(path: Path, key: str, value) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data[key] = value
    write(path, json.dumps(data))


def main() -> None:
    assert M["TARGET"] == "init/version.o"
    assert M["HEADER"] == "include/generated/compile.h"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        good = fixture(root / "good")
        status = invoke(good)
        assert status["exit_code"] == 0
        assert status["compile_h_created"] and status["compile_h_anchors_valid"]
        assert status["compile_h_macro_issues"] == []
        assert status["compile_h_uts_machine"] == '"arm64"'
        assert len(status["compile_h_macro_names"]) == 5
        assert status["init_version_object_created"]
        assert status["compile_h_bytes"] > 70
        assert len(status["compile_h_sha256"]) == 64
        assert status["prior_crypto_subtree_gate"] is True
        assert not status["kernel_built"] and not status["flash_ready"]
        assert json.loads((good[2] / M["OUTPUT"]).read_text()) == status

        # The real pinned toolchain may emit either arm64 or aarch64;
        # neither form should cause a false-negative Kbuild header gate.
        good_header = (
            '#define UTS_MACHINE "aarch64"\n'
            '#define UTS_VERSION "#1 PREEMPT"\n'
            '#define LINUX_COMPILE_BY "CI"\n'
            '#define LINUX_COMPILE_HOST "ci"\n'
            '#define LINUX_COMPILER "Clang 21"\n'
        )
        accepted, issues, macros = M["inspect_compile_h"](good_header)
        assert accepted and issues == [] and macros["UTS_MACHINE"] == '"aarch64"'
        missing, errors, _ = M["inspect_compile_h"](
            good_header.replace('#define LINUX_COMPILER "Clang 21"\n', '')
        )
        assert not missing and any("LINUX_COMPILER" in x for x in errors)
        duplicated, errors, _ = M["inspect_compile_h"](
            good_header + '#define UTS_VERSION "duplicate"\n'
        )
        assert not duplicated and any("UTS_VERSION" in x for x in errors)
        invalid_string, errors, _ = M["inspect_compile_h"](
            good_header.replace('"#1 PREEMPT"', 'not_quoted')
        )
        assert not invalid_string and any("quoted" in x for x in errors)

        error = with_env("STAGE77_MAKE_ERROR", fixture(root / "compile-error"))
        assert error["exit_code"] == 2
        assert error["compile_h_created"] is False
        assert "synthetic RT failure" in error["errors_excerpt"][0]

        no_output = with_env("STAGE77_NO_OUTPUT", fixture(root / "no-output"))
        assert not no_output["compile_h_created"]
        assert not no_output["init_version_object_created"]
        assert "missing/invalid" in no_output["errors_excerpt"][0]

        invalid = with_env("STAGE77_INVALID_HEADER", fixture(root / "bad-header"))
        assert invalid["compile_h_created"] and not invalid["compile_h_anchors_valid"]
        assert invalid["compile_h_macro_issues"]
        assert "missing/invalid" in invalid["errors_excerpt"][0]

        no_object = with_env("STAGE77_NO_OBJECT", fixture(root / "no-object"))
        assert no_object["compile_h_anchors_valid"]
        assert not no_object["init_version_object_created"]
        assert "missing/invalid" in no_object["errors_excerpt"][0]

        missing_earlier = fixture(root / "crypto-report-failed")
        change(missing_earlier[10], "archive_has_members", False)
        reject(lambda: invoke(missing_earlier), "CRYPTO archive gate incomplete")

        lost_archive = fixture(root / "missing-crypto-archive")
        (lost_archive[1] / "crypto/built-in.a").unlink()
        reject(lambda: invoke(lost_archive), "CRYPTO archive gate incomplete")

        no_version = fixture(root / "no-version-source")
        (no_version[0] / "init/version.c").unlink()
        reject(lambda: invoke(no_version), "init/version.c source missing")

        no_mkcompile = fixture(root / "no-mkcompile")
        (no_mkcompile[0] / "scripts/mkcompile_h").unlink()
        reject(lambda: invoke(no_mkcompile), "mkcompile_h generator missing")

        drift = fixture(root / "init-make-drift")
        write(drift[0] / "init/Makefile", "obj-y += main.o\n")
        reject(lambda: invoke(drift), "Kbuild rule drift")

        no_rt = fixture(root / "no-rt")
        write(no_rt[1] / ".config", "CONFIG_SECURITY=y\n")
        reject(lambda: invoke(no_rt), "PREEMPT_RT_FULL configuration")

        no_reject = fixture(root / "no-reject")
        (no_reject[0] / "pending/00.rej").unlink()
        reject(lambda: invoke(no_reject), "64 outstanding")

        forbidden_image = fixture(root / "forbidden-image")
        write(forbidden_image[1] / "arch/arm64/boot/Image", "not allowed")
        reject(lambda: invoke(forbidden_image), "Unexpected link or boot artifact")

        bad_timeout = fixture(root / "invalid-timeout")
        reject(lambda: M["execute"](*bad_timeout, 10), "Unsupported Stage77")
    print(
        "EXP76_STAGE77_COMPILE_H_REGRESSIONS=18_PASS; "
        "KERNEL_BUILT=false; FLASH_READY=false"
    )


if __name__ == "__main__":
    main()
