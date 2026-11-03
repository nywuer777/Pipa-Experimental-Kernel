#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage75 CRYPTO regressions / NO FLASH
"""Check scoped Kbuild, archive-members evidence and predecessor gates."""
from __future__ import annotations

import json
import os
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(
    str(ROOT / "tools/exp76-stage75-crypto-subtree.py"),
    run_name="exp76_stage75_tests",
)
PREV = runpy.run_path(
    str(ROOT / "tests/test_exp76_stage73_lib_subtree.py"),
    run_name="exp76_stage73_fixture_only",
)
write = PREV["write"]
execute = M["execute"]


def fixture(root: Path, ipc_enabled: bool = True) -> tuple[Path, ...]:
    kernel, out, report, s50, s66, s67, s68, s69, s72, clang = PREV["fixture"](
        root, ipc_enabled=ipc_enabled,
    )
    write(kernel / "crypto/Makefile", "obj-y += crypto.o\n")
    cfg = out / ".config"
    write(cfg, cfg.read_text(encoding="utf-8") + "CONFIG_CRYPTO=y\n")
    prior = out / "lib/built-in.a"
    prior.parent.mkdir(parents=True, exist_ok=True)
    prior.write_bytes(b"!<thin>\nsynthetic-lib-members")
    s73 = root / "s73.json"
    write(s73, json.dumps({
        "stage": M["STAGE73"]["STAGE"],
        "target": "lib/built-in.a",
        "top_level_directory_scope": "vmlinux-dirs=lib",
        "prior_net_subtree_gate": True,
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
        "# Python 3 / synthetic CRYPTO Kbuild / archive-only / NO FLASH\n"
        "import os, pathlib, sys\n"
        "assert sys.argv[-1] == 'crypto/built-in.a', sys.argv\n"
        "assert 'vmlinux-dirs=crypto' in sys.argv, sys.argv\n"
        "assert 'vmlinux' not in sys.argv and 'Image' not in sys.argv\n"
        "if os.environ.get('STAGE75_MAKE_ERROR') == 'yes':\n"
        "    print('crypto/api.c:99: error: synthetic RT failure')\n"
        "    sys.exit(2)\n"
        "if os.environ.get('STAGE75_NO_ARCHIVE') == 'yes':\n"
        "    sys.exit(0)\n"
        "output = next(x[2:] for x in sys.argv if x.startswith('O='))\n"
        "archive = pathlib.Path(output) / 'crypto/built-in.a'\n"
        "archive.parent.mkdir(parents=True, exist_ok=True)\n"
        "archive.write_bytes(b'!<thin>\\ncrypto-members')\n"
    ))
    make.chmod(0o755)
    ar = clang / "llvm-ar"
    write(ar, (
        "#!/usr/bin/env python3\n"
        "# Python 3 / synthetic CRYPTO llvm-ar / NO FLASH\n"
        "import os, pathlib, sys\n"
        "assert sys.argv[1] == 't' and len(sys.argv) == 3\n"
        "assert sys.argv[2].endswith('crypto/built-in.a')\n"
        "if os.environ.get('STAGE75_AR_ERROR') == 'yes':\n"
        "    print('invalid archive', file=sys.stderr)\n"
        "    sys.exit(1)\n"
        "if os.environ.get('STAGE75_AR_EMPTY') == 'yes':\n"
        "    sys.exit(0)\n"
        "print('crypto.o\\nsha256_generic.o')\n"
    ))
    ar.chmod(0o755)
    return (kernel, out, report, s50, s66, s67, s68, s69, s72, s73, clang)


def run(args: tuple[Path, ...]) -> dict:
    return execute(*args, 90)


def reject(fn, message: str) -> None:
    try:
        fn()
    except ValueError as exc:
        assert message in str(exc), str(exc)
    else:
        raise AssertionError("Expected Stage75 fail-closed: " + message)


def modify(path: Path, key: str, value) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data[key] = value
    write(path, json.dumps(data))


def environmental(name: str, args: tuple[Path, ...]) -> dict:
    os.environ[name] = "yes"
    try:
        return run(args)
    finally:
        del os.environ[name]


def main() -> None:
    assert M["TARGET"] == "crypto/built-in.a"
    assert M["SCOPE"] == "vmlinux-dirs=crypto"
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        good = fixture(root / "good")
        result = run(good)
        assert result["exit_code"] == 0
        assert result["archive_created"] and result["archive_has_members"]
        assert result["archive_inspection_exit_code"] == 0
        assert result["archive_members_count"] == 2
        assert result["archive_members_sample"] == [
            "crypto.o", "sha256_generic.o",
        ]
        assert result["prior_lib_subtree_gate"] is True
        assert result["remaining_rejected_files"] == 64
        assert not result["kernel_built"] and not result["flash_ready"]
        assert result == json.loads((good[2] / M["OUTPUT"]).read_text())

        ipc_disabled = fixture(root / "ipc-disabled", ipc_enabled=False)
        assert run(ipc_disabled)["archive_has_members"] is True

        compiler_error = fixture(root / "compiler-failure")
        bad_make = environmental("STAGE75_MAKE_ERROR", compiler_error)
        assert bad_make["exit_code"] == 2 and not bad_make["archive_created"]
        assert "synthetic RT failure" in bad_make["errors_excerpt"][0]

        missing = fixture(root / "no-output")
        absent = environmental("STAGE75_NO_ARCHIVE", missing)
        assert not absent["archive_created"]
        assert "without creating" in absent["errors_excerpt"][0]

        bad_ar = fixture(root / "invalid-ar")
        inspected = environmental("STAGE75_AR_ERROR", bad_ar)
        assert inspected["archive_inspection_exit_code"] == 1
        assert not inspected["archive_has_members"]
        assert "llvm-ar t rejected" in inspected["errors_excerpt"][0]

        empty_ar = fixture(root / "empty-ar")
        empty = environmental("STAGE75_AR_EMPTY", empty_ar)
        assert empty["archive_created"]
        assert not empty["archive_has_members"]
        assert empty["archive_members_count"] == 0
        assert "no verified archive members" in empty["errors_excerpt"][0]

        bad_lib = fixture(root / "lib-failed")
        modify(bad_lib[9], "archive_has_members", False)
        reject(lambda: run(bad_lib), "Stage50/66/67/68/69/72/73")

        bad_lib_size = fixture(root / "lib-size")
        modify(bad_lib_size[9], "archive_bytes", 99)
        reject(lambda: run(bad_lib_size), "Stage50/66/67/68/69/72/73")

        missing_lib = fixture(root / "lib-missing")
        (missing_lib[1] / "lib/built-in.a").unlink()
        reject(lambda: run(missing_lib), "Stage50/66/67/68/69/72/73")

        bad_net = fixture(root / "net-failed")
        modify(bad_net[8], "archive_inspection_exit_code", 3)
        reject(lambda: run(bad_net), "Stage50/66/67/68/69/72/73")

        no_crypto = fixture(root / "no-crypto")
        (no_crypto[0] / "crypto/Makefile").unlink()
        reject(lambda: run(no_crypto), "crypto/Makefile missing")

        bad_cfg = fixture(root / "crypto-config-disabled")
        cfg = bad_cfg[1] / ".config"
        write(cfg, cfg.read_text().replace("CONFIG_CRYPTO=y\n", ""))
        reject(lambda: run(bad_cfg), "CRYPTO=y")

        lost_reject = fixture(root / "lost-reject")
        (lost_reject[0] / "pending/00.rej").unlink()
        reject(lambda: run(lost_reject), "64 outstanding")

        root_drift = fixture(root / "kbuild-drift")
        write(root_drift[0] / "Makefile", "vmlinux-dirs := drivers\n")
        reject(lambda: run(root_drift), "directory dependency drift")

        unwanted_image = fixture(root / "unwanted-image")
        write(unwanted_image[1] / "arch/arm64/boot/Image", "forbidden")
        reject(lambda: run(unwanted_image), "Unexpected link or boot artifact")

        timeout = fixture(root / "bad-timeout")
        reject(lambda: execute(*timeout, 10), "Unsupported Stage75")
    print(
        "EXP76_STAGE75_CRYPTO_SUBTREE_REGRESSIONS=16_PASS; "
        "KERNEL_BUILT=false; FLASH_READY=false"
    )


if __name__ == "__main__":
    main()
