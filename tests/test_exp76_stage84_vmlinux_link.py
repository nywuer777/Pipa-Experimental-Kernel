#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage84 vmlinux link regressions / NO FLASH
"""Fail closed on wrong Kbuild, missing archives, stale source or boot files."""
from __future__ import annotations

import hashlib
import json
import os
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(
    str(ROOT / "tools/exp76-stage84-vmlinux-link.py"),
    run_name="exp76_stage84_test_helpers",
)
PREV = runpy.run_path(
    str(ROOT / "tests/test_exp76_stage81_block_init_subtrees.py"),
    run_name="exp76_stage81_fixture",
)
write = PREV["write"]


def fixture(root: Path) -> tuple[Path, ...]:
    kernel, out, report, s76, s77, s79, clang = PREV["fixture"](root)
    makefile = kernel / "Makefile"
    write(makefile, makefile.read_text(encoding="utf-8")
          + "\nall: vmlinux\n"
          + "vmlinux: scripts/link-vmlinux.sh autoksyms_recursive $(vmlinux-deps) FORCE\n")
    write(kernel / "scripts/link-vmlinux.sh", (
        "#!/bin/sh\n"
        "# Synthetic pinned link rule proof\n"
        "vmlinux_link()\n"
        "{\n"
        "    :\n"
        "}\n"
    ))
    for dirname in ("block", "init"):
        archive = out / dirname / "built-in.a"
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(b"!<thin>\nSynthetic archive "+dirname.encode())
    stage81 = root / "stage81.json"
    write(stage81, json.dumps({
        "stage": M["M81"]["STAGE"],
        "prior_drivers_subtree_gate": True,
        "prior_compile_h_gate": True,
        "prior_functionfs_rt_gate": True,
        "all_archives_verified": True,
        "remaining_rejected_files": 64,
        "full_kernel_link_performed": False,
        "kernel_built": False, "flash_ready": False,
        "targets": {
            dirname: {
                "target": f"{dirname}/built-in.a",
                "directory_scope": f"vmlinux-dirs={dirname}",
                "attempted": True,
                "exit_code": 0, "timed_out": False,
                "archive_created": True,
                "archive_has_members": True,
                "archive_inspection_exit_code": 0,
                "archive_members_count": 2,
                "archive_bytes": (out / dirname / "built-in.a").stat().st_size,
            } for dirname in ("block", "init")
        },
    }))
    kconfig = kernel / M["M83"]["SOURCE"]
    write(kconfig, (
        "config CRYPTO_CHACHA20_NEON\n"
        "\tdepends on KERNEL_MODE_NEON && !PREEMPT_RT_BASE\n"
        "config CRYPTO_POLY1305_NEON\n"
        "\tdepends on KERNEL_MODE_NEON && !PREEMPT_RT_BASE\n"
    ))
    stage83 = root / "stage83.json"
    write(stage83, json.dumps({
        "stage": M["M83"]["STAGE"],
        "target": M["M83"]["SOURCE"],
        "applied": True,
        "rejected_hunk_sha256": M["M83"]["REJECT_SHA"],
        "rejected_hunks_reviewed": 1,
        "config_dependencies_patched": sorted(M["M83"]["BLOCKS"]),
        "nonrt_kernel_mode_neon_preserved": True,
        "reject_audit_file_retained": True,
        "remaining_rejected_files": 64,
        "full_kernel_link_performed": False,
        "kernel_built": False, "flash_ready": False,
        "patched_source_sha256": hashlib.sha256(kconfig.read_bytes()).hexdigest(),
    }))
    make = clang / "make"
    write(make, (
        "#!/usr/bin/env python3\n"
        "# Python 3 / bounded synthetic Kbuild linker / NO FLASH\n"
        "import os, pathlib, sys\n"
        "assert sys.argv[-1] == 'vmlinux', sys.argv\n"
        "assert 'Image' not in sys.argv and 'boot.img' not in sys.argv\n"
        "assert 'ARCH=arm64' in sys.argv and 'CC=clang' in sys.argv\n"
        "out = pathlib.Path(next(a[2:] for a in sys.argv if a.startswith('O=')))\n"
        "if os.environ.get('STAGE84_LINK_FAIL') == 'yes':\n"
        "    print('ld.lld: error: undefined symbol: synthetic_rt_contract')\n"
        "    sys.exit(2)\n"
        "if os.environ.get('STAGE84_NO_ELF') == 'yes':\n"
        "    print('link not complete')\n"
        "    sys.exit(0)\n"
        "if os.environ.get('STAGE84_INVALID_ELF') == 'yes':\n"
        "    (out / 'vmlinux').write_bytes(b'NOT-ELF' * 600)\n"
        "    sys.exit(0)\n"
        "(out / 'vmlinux').write_bytes(b'\\x7fELF' + bytes(8192))\n"
    ))
    make.chmod(0o755)
    return kernel, out, report, stage81, stage83, clang


def invoke(args: tuple[Path, ...]) -> dict:
    return M["execute"](*args, 90)


def reject(fn, message: str) -> None:
    try:
        fn()
    except ValueError as err:
        assert message in str(err), str(err)
    else:
        raise AssertionError("Stage84 failed to reject " + message)


def patch_json(path: Path, name: str, value) -> None:
    data = json.loads(path.read_text())
    data[name] = value
    write(path, json.dumps(data))


def with_env(variable: str, args: tuple[Path, ...]) -> dict:
    os.environ[variable] = "yes"
    try:
        return invoke(args)
    finally:
        del os.environ[variable]


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        good = fixture(root / "good")
        result = invoke(good)
        assert result["stage"] == M["STAGE"]
        assert result["target"] == "vmlinux"
        assert result["attempted"] is True
        assert result["exit_code"] == 0 and not result["timed_out"]
        assert result["vmlinux_created"] and result["vmlinux_elf_verified"]
        assert result["vmlinux_bytes"] >= 8192
        assert not result["boot_image_generated"] and not result["flash_performed"]
        assert not result["kernel_built"] and not result["flash_ready"]
        assert json.loads((good[2] / M["REPORT"]).read_text()) == result

        fail = with_env("STAGE84_LINK_FAIL", fixture(root / "link-failure"))
        assert fail["exit_code"] == 2
        assert not fail["vmlinux_created"] and not fail["vmlinux_elf_verified"]
        assert any("undefined symbol" in x for x in fail["first_compiler_linker_errors"])

        none = with_env("STAGE84_NO_ELF", fixture(root / "no-elf"))
        assert none["exit_code"] == 0 and not none["vmlinux_elf_verified"]
        assert "no valid ELF" in none["first_compiler_linker_errors"][-1]

        bad_elf = with_env("STAGE84_INVALID_ELF", fixture(root / "bad-elf"))
        assert bad_elf["vmlinux_created"] and not bad_elf["vmlinux_elf_verified"]

        missing_stage81 = fixture(root / "stage81-invalid")
        patch_json(missing_stage81[3], "all_archives_verified", False)
        reject(lambda: invoke(missing_stage81), "provenance failed")

        missing_archive = fixture(root / "missing-archive")
        (missing_archive[1] / "init/built-in.a").unlink()
        reject(lambda: invoke(missing_archive), "provenance failed")

        missing_stage83 = fixture(root / "stage83-invalid")
        patch_json(missing_stage83[4], "applied", False)
        reject(lambda: invoke(missing_stage83), "provenance failed")

        altered_kconfig = fixture(root / "source-hash-mismatch")
        write(altered_kconfig[0] / M["M83"]["SOURCE"], "unreviewed change\n")
        reject(lambda: invoke(altered_kconfig), "differs from reviewed")

        image = fixture(root / "boot-image")
        write(image[1] / "arch/arm64/boot/Image.gz", "forbidden")
        reject(lambda: invoke(image), "forbidden boot image")

        prelinked = fixture(root / "prelinked")
        write(prelinked[1] / "vmlinux", "stale link")
        reject(lambda: invoke(prelinked), "no preexisting")

        missing_reject = fixture(root / "rejects-drift")
        (missing_reject[0] / "pending/00.rej").unlink()
        reject(lambda: invoke(missing_reject), "64 unresolved")

        config = fixture(root / "bad-config")
        path = config[1] / ".config"
        write(path, path.read_text().replace("CONFIG_BLOCK=y\n", ""))
        reject(lambda: invoke(config), "PREEMPT_RT_FULL=y and BLOCK=y")

        make_drift = fixture(root / "make-drift")
        path = make_drift[0] / "Makefile"
        write(path, path.read_text().replace(
            "vmlinux: scripts/link-vmlinux.sh autoksyms_recursive $(vmlinux-deps) FORCE",
            "vmlinux: other-linker",
        ))
        reject(lambda: invoke(make_drift), "target rule drift")

        wrong_timeout = fixture(root / "wrong-timeout")
        reject(lambda: M["execute"](*wrong_timeout, 20), "60..900")

    print(
        "EXP76_STAGE84_VMLINUX_LINK_REGRESSIONS=14_PASS; "
        "FLASH_READY=false"
    )


if __name__ == "__main__":
    main()
