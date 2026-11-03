#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage86 ARM64 raw Image regressions / NO FLASH
"""Check actual symbol-map preflight, raw image magic and no boot packaging."""
from __future__ import annotations

import hashlib
import json
import os
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(
    str(ROOT / "tools/exp76-stage86-raw-arm64-image.py"),
    run_name="exp76_stage86_fixture",
)
PREV = runpy.run_path(
    str(ROOT / "tests/test_exp76_stage84_vmlinux_link.py"),
    run_name="exp76_stage84_fixture",
)
write = PREV["write"]


def fixture(root: Path) -> tuple[Path, ...]:
    kernel, out, report, stage81, stage83, clang = PREV["fixture"](root)
    write(kernel / "arch/arm64/boot/Makefile",
          "OBJCOPYFLAGS_Image :=-O binary -S\n"
          "$(obj)/Image: vmlinux FORCE\n\t$(call if_changed,objcopy)\n")
    write(kernel / "arch/arm64/Makefile",
          "Image: vmlinux\n\t$(Q)$(MAKE) $(build)=arch/arm64/boot arch/arm64/boot/$@\n")
    write(kernel / "arch/arm64/kernel/head.S",
          '_head:\n\t.ascii\t"ARM\\x64"\n')
    write(kernel / M["M85"]["MAKE"],
          "obj-$(CONFIG_PREEMPT_RT_FULL) += rwsem-rt-api.o\n")
    write(kernel / M["M85"]["API"],
          "/* Synthetic RT public entry points */\n")
    write(kernel / M["M85"]["RADIX"],
          "/* Synthetic RT idr preload local lock release */\n")

    elf = out / "vmlinux"
    elf.write_bytes(b"\x7fELF" + bytes(8192))
    stage84 = root / "stage84.json"
    write(stage84, json.dumps({
        "stage": M["M84"]["STAGE"],
        "target": "vmlinux", "attempted": True,
        "exit_code": 0, "timed_out": False,
        "vmlinux_created": True, "vmlinux_elf_verified": True,
        "vmlinux_bytes": elf.stat().st_size,
        "remaining_rejected_files": 64,
        "boot_image_generated": False, "flash_performed": False,
        "flash_ready": False,
    }))
    srcs = (M["M85"]["MAKE"], M["M85"]["API"], M["M85"]["RADIX"])
    stage85 = root / "stage85.json"
    write(stage85, json.dumps({
        "stage": M["M85"]["STAGE"],
        "applied": True,
        "rt_public_wrapper_count": 9,
        "rt_public_symbols": list(M["M85"]["PUBLIC_FUNCS"]),
        "non_rt_vendor_rwsem_not_linked": True,
        "idr_preload_end_uses_local_unlock": True,
        "idr_preload_lock_pair_preserved": True,
        "rt_rwsem_lowlevel_preserved": True,
        "rejected_files_remaining": 64,
        "full_kernel_link_performed": False,
        "kernel_built": False,
        "flash_ready": False,
        "source_sha256": {
            s: hashlib.sha256((kernel / s).read_bytes()).hexdigest()
            for s in srcs
        },
    }))
    write(out / "System.map", "\n".join(
        f"ffff800000{i:010x} T {symbol}"
        for i, symbol in enumerate(M["SYMBOLS"])
    ) + "\n")
    make = clang / "make"
    write(make, (
        "#!/usr/bin/env python3\n"
        "# Python 3 / fake ARM64 objcopy Kbuild / NO FLASH\n"
        "import os, pathlib, sys\n"
        "assert sys.argv[-1] == 'Image', sys.argv\n"
        "assert 'OBJCOPY=llvm-objcopy' in sys.argv\n"
        "assert 'ARCH=arm64' in sys.argv\n"
        "assert not any('boot.img' in arg for arg in sys.argv)\n"
        "out = pathlib.Path(next(x[2:] for x in sys.argv if x.startswith('O=')))\n"
        "if os.environ.get('STAGE86_FAIL') == 'yes':\n"
        "    print('llvm-objcopy: error: synthetic failure')\n"
        "    sys.exit(2)\n"
        "if os.environ.get('STAGE86_NO_IMAGE') == 'yes':\n"
        "    sys.exit(0)\n"
        "image = out / 'arch/arm64/boot/Image'\n"
        "image.parent.mkdir(parents=True, exist_ok=True)\n"
        "header = bytearray(8192)\n"
        "header[0x38:0x3c] = (b'BAD!' if os.environ.get('STAGE86_BAD_MAGIC') == 'yes' "
        "else b'ARM\\x64')\n"
        "image.write_bytes(header)\n"
    ))
    make.chmod(0o755)
    write(clang / "llvm-objcopy", "#!/bin/sh\nexit 0\n")
    return kernel, out, root / "stage86", stage84, stage85, clang


def invoke(fixture_args: tuple[Path, ...]) -> dict:
    return M["execute"](*fixture_args, 120)


def reject(callable_, message: str) -> None:
    try:
        callable_()
    except ValueError as exc:
        assert message in str(exc), str(exc)
    else:
        raise AssertionError("Stage86 accepted invalid state: " + message)


def with_env(variable: str, args: tuple[Path, ...]) -> dict:
    os.environ[variable] = "yes"
    try:
        return invoke(args)
    finally:
        del os.environ[variable]


def patch_json(path: Path, key: str, value) -> None:
    data = json.loads(path.read_text())
    data[key] = value
    write(path, json.dumps(data))


def main() -> None:
    assert len(M["SYMBOLS"]) == 10
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        good = fixture(root / "good")
        assert M["preflight"](good[0], good[1], good[3], good[4], good[5])[
            "all_previous_unresolved_symbols_restored"
        ]
        ok = invoke(good)
        assert ok["stage"] == M["STAGE"]
        assert ok["raw_image_created"] and ok["raw_arm64_header_valid"]
        assert ok["raw_arm64_magic_hex"] == "41524d64"
        assert ok["exit_code"] == 0 and not ok["timed_out"]
        assert ok["raw_image_sha256"] == hashlib.sha256(
            (good[1] / M["RAW_IMAGE"]).read_bytes()
        ).hexdigest()
        assert len(ok["public_link_symbols_verified"]) == 10
        assert not ok["public_link_symbols_missing"]
        assert not ok["image_artifact_uploaded"]
        assert not ok["packaged_boot_image_generated"]
        assert not ok["flash_performed"] and not ok["flash_ready"]
        assert not ok["kernel_built"] and not ok["rt_semantic_review_complete"]
        assert json.loads((good[2] / M["REPORT"]).read_text()) == ok

        failed = with_env("STAGE86_FAIL", fixture(root / "error"))
        assert failed["exit_code"] == 2 and not failed["raw_image_created"]
        assert not failed["raw_arm64_header_valid"]
        assert "synthetic failure" in failed["first_compiler_errors"][0]

        absent = with_env("STAGE86_NO_IMAGE", fixture(root / "absent"))
        assert absent["exit_code"] == 0 and not absent["raw_arm64_header_valid"]
        assert "header magic invalid" in absent["first_compiler_errors"][-1]

        invalid = with_env("STAGE86_BAD_MAGIC", fixture(root / "bad-magic"))
        assert invalid["raw_image_created"] and not invalid["raw_arm64_header_valid"]
        assert invalid["raw_arm64_magic_hex"] == "42414421"

        missing_symbol = fixture(root / "missing-symbol")
        mp = missing_symbol[1] / "System.map"
        write(mp, mp.read_text().replace(" T idr_preload_end\n", " T not_preload_end\n"))
        reject(lambda: invoke(missing_symbol), "absent in System.map")

        wrong_elf = fixture(root / "wrong-elf")
        p = wrong_elf[1] / "vmlinux"
        p.write_bytes(b"not-ELF" + bytes(8192 - 3))
        reject(lambda: invoke(wrong_elf), "linked vmlinux provenance")

        bad_report = fixture(root / "bad-report")
        patch_json(bad_report[3], "vmlinux_elf_verified", False)
        reject(lambda: invoke(bad_report), "linked vmlinux provenance")

        source_drift = fixture(root / "source-drift")
        write(source_drift[0] / M["M85"]["API"], "unreviewed change\n")
        reject(lambda: invoke(source_drift), "source hash mismatch")

        missing_api = fixture(root / "missing-api")
        (missing_api[0] / M["M85"]["API"]).unlink()
        reject(lambda: invoke(missing_api), "source hash mismatch")

        lost_rej = fixture(root / "lost-rej")
        (lost_rej[0] / "pending/00.rej").unlink()
        reject(lambda: invoke(lost_rej), "64 retained")

        stale_image = fixture(root / "stale")
        write(stale_image[1] / M["RAW_IMAGE"], "prior run")
        reject(lambda: invoke(stale_image), "no stale")

        unsafe = fixture(root / "boot")
        write(unsafe[1] / "vendor_boot.img", "forbidden")
        reject(lambda: invoke(unsafe), "forbidden packaged")

        no_cfg = fixture(root / "config")
        path = no_cfg[1] / ".config"
        write(path, path.read_text().replace("CONFIG_PREEMPT_RT_FULL=y\n", ""))
        reject(lambda: invoke(no_cfg), "PREEMPT_RT_FULL config")

        changed_arch = fixture(root / "head-drift")
        write(changed_arch[0] / "arch/arm64/kernel/head.S",
              '_head:\n\t.ascii\t"not-arm"\n')
        reject(lambda: invoke(changed_arch), "boot header drift")

        bad_timeout = fixture(root / "timeout")
        reject(lambda: M["execute"](*bad_timeout, 20), "60..600")
    print(
        "EXP76_STAGE86_RAW_ARM64_IMAGE_REGRESSIONS=15_PASS; "
        "REJECTS=64; FLASH_READY=false"
    )


if __name__ == "__main__":
    main()
