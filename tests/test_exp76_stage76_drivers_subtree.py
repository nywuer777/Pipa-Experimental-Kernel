#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage76 DRIVERS tests / NO FLASH
"""Synthetic regression cases for driver Kbuild and all upstream gates."""
from __future__ import annotations

import json
import os
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(
    str(ROOT / "tools/exp76-stage76-drivers-subtree.py"),
    run_name="exp76_stage76_tests",
)
PREV = runpy.run_path(
    str(ROOT / "tests/test_exp76_stage75_crypto_subtree.py"),
    run_name="exp76_stage75_fixture_only",
)
write = PREV["write"]
execute = M["execute"]


def fixture(root: Path, ipc_enabled: bool = True) -> tuple[Path, ...]:
    kernel, out, report, s50, s66, s67, s68, s69, s72, s73, clang = (
        PREV["fixture"](root, ipc_enabled=ipc_enabled)
    )
    write(kernel / "drivers/Makefile", "obj-y += base/ irqchip/ mmc/\n")
    prior = out / "crypto/built-in.a"
    prior.parent.mkdir(parents=True, exist_ok=True)
    prior.write_bytes(b"!<thin>\ncrypto-members")
    s75 = root / "s75.json"
    write(s75, json.dumps({
        "stage": M["STAGE75"]["STAGE"],
        "target": M["STAGE75"]["TARGET"],
        "top_level_directory_scope": M["STAGE75"]["SCOPE"],
        "prior_lib_subtree_gate": True,
        "attempted": True,
        "exit_code": 0,
        "timed_out": False,
        "archive_created": True,
        "archive_has_members": True,
        "archive_inspection_exit_code": 0,
        "archive_members_count": 2,
        "archive_bytes": prior.stat().st_size,
        "remaining_rejected_files": 64,
        "full_kernel_link_performed": False,
        "kernel_built": False,
        "flash_ready": False,
    }))
    make = clang / "make"
    write(make, (
        "#!/usr/bin/env python3\n"
        "# Python 3 / synthetic driver archive make / NO FLASH\n"
        "import os, pathlib, sys\n"
        "assert sys.argv[-1] == 'drivers/built-in.a', sys.argv\n"
        "assert 'vmlinux-dirs=drivers' in sys.argv, sys.argv\n"
        "assert 'vmlinux' not in sys.argv and 'Image' not in sys.argv\n"
        "if os.environ.get('STAGE76_MAKE_ERROR') == 'yes':\n"
        "    print('drivers/base/core.c:112: error: synthetic RT failure')\n"
        "    sys.exit(2)\n"
        "if os.environ.get('STAGE76_NO_ARCHIVE') == 'yes':\n"
        "    sys.exit(0)\n"
        "output = next(x[2:] for x in sys.argv if x.startswith('O='))\n"
        "archive = pathlib.Path(output) / 'drivers/built-in.a'\n"
        "archive.parent.mkdir(parents=True, exist_ok=True)\n"
        "archive.write_bytes(b'!<thin>\\nsynthetic-drivers')\n"
    ))
    make.chmod(0o755)
    ar = clang / "llvm-ar"
    write(ar, (
        "#!/usr/bin/env python3\n"
        "# Python 3 / synthetic driver llvm-ar / NO FLASH\n"
        "import os, pathlib, sys\n"
        "assert sys.argv[1] == 't' and len(sys.argv) == 3\n"
        "assert sys.argv[2].endswith('drivers/built-in.a')\n"
        "if os.environ.get('STAGE76_AR_ERROR') == 'yes':\n"
        "    print('invalid archive', file=sys.stderr)\n"
        "    sys.exit(1)\n"
        "if os.environ.get('STAGE76_AR_EMPTY') == 'yes':\n"
        "    sys.exit(0)\n"
        "print('base/core.o\\nirqchip/irq-gic.o')\n"
    ))
    ar.chmod(0o755)
    return (
        kernel, out, report, s50, s66, s67, s68, s69, s72, s73,
        s75, clang,
    )


def run(args: tuple[Path, ...]) -> dict:
    return execute(*args, 90)


def reject(fn, expected: str) -> None:
    try:
        fn()
    except ValueError as exc:
        assert expected in str(exc), str(exc)
    else:
        raise AssertionError("Missing Stage76 rejection: " + expected)


def change(path: Path, name: str, value) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data[name] = value
    write(path, json.dumps(data))


def envrun(name: str, args: tuple[Path, ...]) -> dict:
    os.environ[name] = "yes"
    try:
        return run(args)
    finally:
        del os.environ[name]


def main() -> None:
    assert M["TARGET"] == "drivers/built-in.a"
    assert M["SCOPE"] == "vmlinux-dirs=drivers"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        good = fixture(root / "good")
        passed = run(good)
        assert passed["archive_created"] is True
        assert passed["archive_has_members"] is True
        assert passed["archive_inspection_exit_code"] == 0
        assert passed["archive_members_count"] == 2
        assert passed["archive_members_sample"] == [
            "base/core.o", "irqchip/irq-gic.o",
        ]
        assert passed["prior_crypto_subtree_gate"] is True
        assert passed["exit_code"] == 0 and passed["timed_out"] is False
        assert passed["remaining_rejected_files"] == 64
        assert not passed["full_kernel_link_performed"]
        assert not passed["kernel_built"] and not passed["flash_ready"]
        assert json.loads((good[2] / M["OUTPUT"]).read_text()) == passed

        no_ipc = fixture(root / "ipc-disabled", ipc_enabled=False)
        assert run(no_ipc)["archive_has_members"]

        make_error = fixture(root / "compile-error")
        error = envrun("STAGE76_MAKE_ERROR", make_error)
        assert error["exit_code"] == 2 and not error["archive_created"]
        assert "synthetic RT failure" in error["errors_excerpt"][0]

        missing = fixture(root / "missing-output")
        no_archive = envrun("STAGE76_NO_ARCHIVE", missing)
        assert no_archive["exit_code"] == 0
        assert not no_archive["archive_created"]
        assert "without creating" in no_archive["errors_excerpt"][0]

        bad_ar = fixture(root / "bad-ar")
        ar_error = envrun("STAGE76_AR_ERROR", bad_ar)
        assert ar_error["archive_created"] and not ar_error["archive_has_members"]
        assert ar_error["archive_inspection_exit_code"] == 1
        assert "llvm-ar t rejected" in ar_error["errors_excerpt"][0]

        no_members = fixture(root / "no-members")
        empty = envrun("STAGE76_AR_EMPTY", no_members)
        assert empty["archive_created"] and not empty["archive_has_members"]
        assert empty["archive_members_count"] == 0
        assert "no verified object members" in empty["errors_excerpt"][0]

        bad_crypto = fixture(root / "bad-crypto")
        change(bad_crypto[10], "archive_has_members", False)
        reject(lambda: run(bad_crypto), "Stage50/66/67/68/69/72/73/75")

        bad_crypto_size = fixture(root / "bad-crypto-size")
        change(bad_crypto_size[10], "archive_bytes", 99)
        reject(lambda: run(bad_crypto_size), "Stage50/66/67/68/69/72/73/75")

        missing_crypto = fixture(root / "missing-crypto")
        (missing_crypto[1] / "crypto/built-in.a").unlink()
        reject(lambda: run(missing_crypto), "Stage50/66/67/68/69/72/73/75")

        bad_lib = fixture(root / "bad-lib")
        change(bad_lib[9], "archive_has_members", False)
        reject(lambda: run(bad_lib), "Stage50/66/67/68/69/72/73/75")

        no_driver_makefile = fixture(root / "missing-driver-makefile")
        (no_driver_makefile[0] / "drivers/Makefile").unlink()
        reject(lambda: run(no_driver_makefile), "drivers/Makefile missing")

        no_git = fixture(root / "missing-git")
        (no_git[0] / ".git").rmdir()
        reject(lambda: run(no_git), "isolated E404")

        wrong_config = fixture(root / "wrong-config")
        cfg = wrong_config[1] / ".config"
        write(cfg, cfg.read_text().replace("CONFIG_CRYPTO=y\n", ""))
        reject(lambda: run(wrong_config), "prior enabled subsystems")

        missing_reject = fixture(root / "missing-reject")
        (missing_reject[0] / "pending/00.rej").unlink()
        reject(lambda: run(missing_reject), "64 outstanding")

        kbuild_drift = fixture(root / "kbuild-drift")
        write(kbuild_drift[0] / "Makefile", "vmlinux-dirs := drivers\n")
        reject(lambda: run(kbuild_drift), "dependency drift")

        wrong_image = fixture(root / "unintended-image")
        write(wrong_image[1] / "arch/arm64/boot/Image", "forbidden")
        reject(lambda: run(wrong_image), "Unexpected link or boot artifact")

        bad_timeout = fixture(root / "invalid-timeout")
        reject(lambda: execute(*bad_timeout, 10), "Unsupported Stage76")
    print(
        "EXP76_STAGE76_DRIVERS_SUBTREE_REGRESSIONS=17_PASS; "
        "KERNEL_BUILT=false; FLASH_READY=false"
    )


if __name__ == "__main__":
    main()
