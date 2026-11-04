#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage81 block+init regressions / NO FLASH
"""Fail-closed proof for paired Kbuild archives and predecessor provenance."""
from __future__ import annotations

import json
import os
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(
    str(ROOT / "tools/exp76-stage81-block-init-subtrees.py"),
    run_name="stage81_tests",
)
PREV = runpy.run_path(
    str(ROOT / "tests/test_exp76_stage77_compile_h_preflight.py"),
    run_name="stage77_fixture",
)
write = PREV["write"]


def fixture(root: Path) -> tuple[Path, ...]:
    kernel, out, report, s50, s66, s67, s68, s69, s72, s73, s75, clang = (
        PREV["fixture"](root)
    )
    write(kernel / "block/Makefile", "obj-$(CONFIG_BLOCK) += bio.o\n")
    cfg = out / ".config"
    write(cfg, cfg.read_text(encoding="utf-8") + "CONFIG_BLOCK=y\n")
    drivers = out / "drivers/built-in.a"
    drivers.parent.mkdir(parents=True, exist_ok=True)
    drivers.write_bytes(b"!<thin>\nsynthetic-drivers")
    s76 = root / "stage76.json"
    write(s76, json.dumps({
        "stage": M["STAGE76"]["STAGE"],
        "target": M["STAGE76"]["TARGET"],
        "top_level_directory_scope": M["STAGE76"]["SCOPE"],
        "prior_crypto_subtree_gate": True,
        "attempted": True, "exit_code": 0, "timed_out": False,
        "archive_created": True, "archive_has_members": True,
        "archive_inspection_exit_code": 0,
        "archive_members_count": 2,
        "archive_bytes": drivers.stat().st_size,
        "remaining_rejected_files": 64,
        "full_kernel_link_performed": False,
        "kernel_built": False, "flash_ready": False,
    }))
    header = out / "include/generated/compile.h"
    write(header, '#define UTS_MACHINE "aarch64"\n#define UTS_VERSION "#1"\n')
    version = out / "init/version.o"
    version.parent.mkdir(parents=True, exist_ok=True)
    version.write_bytes(b"ELF-nonflash-object")
    s77 = root / "stage77.json"
    write(s77, json.dumps({
        "stage": "EXP76_STAGE77_KBUILD_COMPILE_H_INIT_VERSION_NONFLASH",
        "target": "init/version.o",
        "generated_header": "include/generated/compile.h",
        "prior_crypto_subtree_gate": True,
        "exit_code": 0, "timed_out": False,
        "compile_h_created": True, "compile_h_anchors_valid": True,
        "compile_h_bytes": header.stat().st_size,
        "init_version_object_created": True,
        "remaining_rejected_files": 64,
        "full_kernel_link_performed": False,
        "kernel_built": False, "flash_ready": False,
    }))
    s79 = root / "stage79.json"
    write(s79, json.dumps({
        "stage": "EXP76_STAGE79_FUNCTIONFS_RT_COMPLETION_SWAIT_NONFLASH",
        "target": "drivers/usb/gadget/function/f_fs.c",
        "applied": True, "rt_completion_swait_used": True,
        "nonrt_waitqueue_preserved": True,
        "normal_waitqueue_checks_preserved": True,
        "completion_lifecycle_preserved": True,
        "remaining_rejected_files": 64,
        "full_kernel_link_performed": False,
        "kernel_built": False, "flash_ready": False,
    }))
    make = clang / "make"
    write(make, (
        "#!/usr/bin/env python3\n"
        "# Python 3 / synthetic scoped archive make / NO FLASH\n"
        "import os, pathlib, sys\n"
        "target = sys.argv[-1]\n"
        "assert target in ('block/built-in.a', 'init/built-in.a'), target\n"
        "scope = 'vmlinux-dirs=' + target.split('/')[0]\n"
        "assert scope in sys.argv and 'Image' not in sys.argv\n"
        "assert 'vmlinux' not in sys.argv\n"
        "if os.environ.get('STAGE81_FAIL') == target.split('/')[0]:\n"
        "    print(target + ':7: error: synthetic RT problem')\n"
        "    sys.exit(2)\n"
        "if os.environ.get('STAGE81_NO_ARCHIVE') == target.split('/')[0]:\n"
        "    sys.exit(0)\n"
        "out = pathlib.Path(next(x[2:] for x in sys.argv if x.startswith('O=')))\n"
        "archive = out / target\n"
        "archive.parent.mkdir(parents=True, exist_ok=True)\n"
        "archive.write_bytes(b'!<thin>\\n' + target.encode())\n"
    ))
    make.chmod(0o755)
    ar = clang / "llvm-ar"
    write(ar, (
        "#!/usr/bin/env python3\n"
        "# Python 3 / synthetic llvm-ar for block+init / NO FLASH\n"
        "import os, sys\n"
        "assert len(sys.argv) == 3 and sys.argv[1] == 't'\n"
        "name = sys.argv[2].split('/')[-2]\n"
        "assert name in ('block', 'init'), name\n"
        "if os.environ.get('STAGE81_AR_FAIL') == name:\n"
        "    print('invalid archive', file=sys.stderr)\n"
        "    sys.exit(1)\n"
        "if os.environ.get('STAGE81_AR_EMPTY') == name:\n"
        "    sys.exit(0)\n"
        "print(name + '/test.o')\n"
    ))
    ar.chmod(0o755)
    return kernel, out, report, s76, s77, s79, clang


def invoke(args: tuple[Path, ...]) -> dict:
    return M["execute"](*args, 90)


def reject(fn, expected: str) -> None:
    try:
        fn()
    except ValueError as error:
        assert expected in str(error), str(error)
    else:
        raise AssertionError("Missing Stage81 fail-closed: " + expected)


def set_json(path: Path, key: str, value) -> None:
    data = json.loads(path.read_text())
    data[key] = value
    write(path, json.dumps(data))


def with_env(name: str, value: str, args: tuple[Path, ...]) -> dict:
    os.environ[name] = value
    try:
        return invoke(args)
    finally:
        del os.environ[name]


def main() -> None:
    assert M["TARGETS"] == ("block/built-in.a", "init/built-in.a")
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        good = fixture(root / "good")
        passed = invoke(good)
        assert passed["stage"] == M["STAGE"]
        assert passed["all_archives_verified"] is True
        assert passed["prior_drivers_subtree_gate"] is True
        assert passed["prior_compile_h_gate"] is True
        assert passed["prior_functionfs_rt_gate"] is True
        for name in ("block", "init"):
            obj = passed["targets"][name]
            assert obj["target"] == name + "/built-in.a"
            assert obj["archive_created"] and obj["archive_has_members"]
            assert obj["archive_inspection_exit_code"] == 0
            assert obj["archive_members_count"] == 1
            assert obj["exit_code"] == 0 and not obj["timed_out"]
        assert not passed["kernel_built"] and not passed["flash_ready"]
        assert json.loads((good[2] / M["OUTPUT"]).read_text()) == passed

        compiler = fixture(root / "compile-error")
        failed = with_env("STAGE81_FAIL", "block", compiler)
        assert not failed["all_archives_verified"]
        assert failed["targets"]["block"]["exit_code"] == 2
        assert "synthetic RT problem" in failed["targets"]["block"]["errors_excerpt"][0]
        assert failed["targets"]["init"]["archive_has_members"]

        no_archive = fixture(root / "no-archive")
        absent = with_env("STAGE81_NO_ARCHIVE", "init", no_archive)
        assert not absent["all_archives_verified"]
        assert "without creating" in absent["targets"]["init"]["errors_excerpt"][0]
        assert absent["targets"]["block"]["archive_has_members"]

        ar_fail = fixture(root / "ar-fail")
        inspected = with_env("STAGE81_AR_FAIL", "block", ar_fail)
        assert inspected["targets"]["block"]["archive_inspection_exit_code"] == 1
        assert not inspected["all_archives_verified"]

        ar_empty = fixture(root / "ar-empty")
        empty = with_env("STAGE81_AR_EMPTY", "init", ar_empty)
        assert empty["targets"]["init"]["archive_members_count"] == 0
        assert not empty["all_archives_verified"]

        bad_driver = fixture(root / "bad-driver")
        set_json(bad_driver[3], "archive_has_members", False)
        reject(lambda: invoke(bad_driver), "provenance gates incomplete")

        bad_driver_archive = fixture(root / "bad-driver-archive")
        (bad_driver_archive[1] / "drivers/built-in.a").unlink()
        reject(lambda: invoke(bad_driver_archive), "provenance gates incomplete")

        invalid_header = fixture(root / "invalid-header")
        set_json(invalid_header[4], "compile_h_anchors_valid", False)
        reject(lambda: invoke(invalid_header), "provenance gates incomplete")

        absent_header = fixture(root / "absent-header")
        (absent_header[1] / "include/generated/compile.h").unlink()
        reject(lambda: invoke(absent_header), "provenance gates incomplete")

        old_functionfs = fixture(root / "no-functionfs")
        set_json(old_functionfs[5], "applied", False)
        reject(lambda: invoke(old_functionfs), "provenance gates incomplete")

        missing_block_make = fixture(root / "no-block")
        (missing_block_make[0] / "block/Makefile").unlink()
        reject(lambda: invoke(missing_block_make), "Makefile missing")

        disabled_block = fixture(root / "no-config-block")
        cfg = disabled_block[1] / ".config"
        write(cfg, cfg.read_text().replace("CONFIG_BLOCK=y\n", ""))
        reject(lambda: invoke(disabled_block), "CONFIG_BLOCK=y")

        lost_reject = fixture(root / "lost-reject")
        (lost_reject[0] / "pending/00.rej").unlink()
        reject(lambda: invoke(lost_reject), "64 outstanding")

        forged_image = fixture(root / "forged-image")
        write(forged_image[1] / "arch/arm64/boot/Image", "forbidden")
        reject(lambda: invoke(forged_image), "Unexpected link or boot artifact")

        bad_timeout = fixture(root / "bad-timeout")
        reject(lambda: M["execute"](*bad_timeout, 12), "60..600")
    print(
        "EXP76_STAGE81_BLOCK_INIT_REGRESSIONS=15_PASS; "
        "KERNEL_BUILT=false; FLASH_READY=false"
    )


if __name__ == "__main__":
    main()
