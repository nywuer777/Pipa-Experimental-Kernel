#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage77 Kbuild compile.h preflight / NO FLASH
"""Generate real compile.h via the pinned init/version.o Kbuild dependency.

The E404 KernelSU overlay includes generated/compile.h, but the prior
object-only prepare target does not generate it. Kbuild init/version.o
depends on that header. Compile only init/version.o and verify both outputs.
No manual/synthetic header or full kernel link is allowed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import runpy
import subprocess
from pathlib import Path

STAGE75 = runpy.run_path(
    str(Path(__file__).with_name("exp76-stage75-crypto-subtree.py")),
    run_name="exp76_stage75_helpers",
)
STAGE50 = STAGE75["STAGE50"]
STAGE = "EXP76_STAGE77_KBUILD_COMPILE_H_INIT_VERSION_NONFLASH"
TARGET = "init/version.o"
HEADER = "include/generated/compile.h"
OUTPUT = "COMPILE_H_PREP_DIAGNOSTIC.json"
MKFILE_ANCHORS = (
    "$(obj)/version.o: include/generated/compile.h",
    "include/generated/compile.h: FORCE",
    "$(srctree)/scripts/mkcompile_h",
)
HEADER_MACROS = (
    "UTS_MACHINE", "UTS_VERSION", "LINUX_COMPILE_BY",
    "LINUX_COMPILE_HOST", "LINUX_COMPILER",
)


def inspect_compile_h(header: str) -> tuple[bool, list[str], dict[str, str]]:
    """Accept exactly one C string-literal definition for each Kbuild macro.

    Some E404 builds report the machine as arm64 or aarch64. Kbuild decides
    the precise value; a literal comparison to one spelling is not an ABI gate.
    """
    definitions: dict[str, list[str]] = {macro: [] for macro in HEADER_MACROS}
    for line in header.splitlines():
        match = re.fullmatch(
            r'\s*#\s*define\s+([A-Z][A-Z0-9_]*)\s+(.+?)\s*',
            line,
        )
        if match and match.group(1) in definitions:
            definitions[match.group(1)].append(match.group(2))
    issues = []
    values = {}
    for name, occurrences in definitions.items():
        if len(occurrences) != 1:
            issues.append(f"{name}: expected 1 definition, got {len(occurrences)}")
            continue
        value = occurrences[0]
        values[name] = value[:200]
        if not re.fullmatch(r'"(?:[^"\\]|\\.)*"', value):
            issues.append(f"{name}: expected quoted C string literal")
        elif name in ("UTS_MACHINE", "UTS_VERSION") and value == '""':
            issues.append(f"{name}: required nonempty value")
    return not issues, issues, values


def execute(kernel: Path, out: Path, report: Path, stage50: Path,
            stage66: Path, stage67: Path, stage68: Path, stage69: Path,
            stage72: Path, stage73: Path, stage75: Path,
            clang: Path, timeout: int) -> dict:
    if timeout < 60 or timeout > 600:
        raise ValueError("Unsupported Stage77 init/version.o timeout")
    if not (kernel / ".git").is_dir():
        raise ValueError("Stage77 requires isolated E404 trial git checkout")
    if not (kernel / "init/Makefile").is_file():
        raise ValueError("Pinned E404 init/Makefile missing")
    makefile = (kernel / "init/Makefile").read_text(encoding="utf-8")
    for anchor in MKFILE_ANCHORS:
        if makefile.count(anchor) != 1:
            raise ValueError("Pinned init/version compile.h Kbuild rule drift")
    script = kernel / "scripts/mkcompile_h"
    if not script.is_file() or "UTS_VERSION=" not in script.read_text():
        raise ValueError("Pinned E404 mkcompile_h generator missing")
    if not (kernel / "init/version.c").is_file():
        raise ValueError("Pinned init/version.c source missing")
    if not (out / "include/generated/asm-offsets.h").is_file():
        raise ValueError("Stage77 arm64 prepare prerequisite missing")
    config = out / ".config"
    if not config.is_file() or "CONFIG_PREEMPT_RT_FULL=y" not in (
        config.read_text(encoding="utf-8").splitlines()
    ):
        raise ValueError("Stage77 requires PREEMPT_RT_FULL configuration")
    if len(list(kernel.rglob("*.rej"))) != 64:
        raise ValueError("Stage77 requires 64 outstanding PREEMPT_RT rejects")
    if not STAGE75["prerequisites"](
        stage50, stage66, stage67, stage68, stage69, stage72, stage73, out
    ):
        raise ValueError("Stage77 requires verified kernel/MM/FS/IPC/security/NET/LIB")
    prior = STAGE50["read"](stage75)
    archive = out / STAGE75["TARGET"]
    if not (
        prior.get("stage") == STAGE75["STAGE"]
        and prior.get("target") == STAGE75["TARGET"]
        and prior.get("top_level_directory_scope") == STAGE75["SCOPE"]
        and prior.get("prior_lib_subtree_gate") is True
        and prior.get("attempted") is True
        and prior.get("exit_code") == 0
        and prior.get("timed_out") is False
        and prior.get("archive_created") is True
        and prior.get("archive_has_members") is True
        and prior.get("archive_inspection_exit_code") == 0
        and isinstance(prior.get("archive_members_count"), int)
        and prior["archive_members_count"] > 0
        and isinstance(prior.get("archive_bytes"), int)
        and prior["archive_bytes"] > 8
        and prior.get("remaining_rejected_files") == 64
        and prior.get("full_kernel_link_performed") is False
        and prior.get("kernel_built") is False
        and prior.get("flash_ready") is False
        and archive.is_file()
        and archive.stat().st_size == prior["archive_bytes"]
    ):
        raise ValueError("Stage77 CRYPTO archive gate incomplete")
    if not all((clang / f).is_file() for f in ("clang", "ld.lld", "llvm-ar")):
        raise ValueError("Pinned Clang21 toolchain incomplete")
    STAGE50["forbid_images"](out)
    report.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PATH"] = str(clang) + os.pathsep + env.get("PATH", "")
    env.update({"ARCH": "arm64", "CC": "clang", "LD": "ld.lld",
                "HOSTCC": "gcc", "LLVM_IAS": "1"})
    cmd = [
        "make", "-C", str(kernel), "O=" + str(out),
        "ARCH=arm64", "CC=clang", "LD=ld.lld", "HOSTCC=gcc",
        "CROSS_COMPILE=aarch64-linux-gnu-",
        "CLANG_TRIPLE=aarch64-linux-gnu-", "-j2", TARGET,
    ]
    log = report / "init_version_kbuild.log"
    with log.open("w", encoding="utf-8") as stream:
        try:
            rc = subprocess.run(
                cmd, env=env, stdout=stream, stderr=subprocess.STDOUT,
                timeout=timeout, check=False,
            ).returncode
        except subprocess.TimeoutExpired:
            rc = 124
            stream.write("\nEXP76_STAGE77_INIT_VERSION_TIMEOUT\n")
    errors, context = STAGE50["failure_extract"](
        log.read_text(encoding="utf-8", errors="replace")
    )
    hdr = out / HEADER
    obj = out / TARGET
    header_text = hdr.read_text(encoding="utf-8", errors="replace") if hdr.is_file() else ""
    anchors_ok, macro_issues, macro_values = inspect_compile_h(header_text)
    header_exists = hdr.is_file() and hdr.stat().st_size > 0
    object_exists = obj.is_file() and obj.stat().st_size > 0
    if rc == 0 and (not header_exists or not anchors_ok or not object_exists):
        errors.append(
            "init/version.o returned zero but compile.h or version.o missing/invalid"
        )
    result = {
        "stage": STAGE,
        "target": TARGET,
        "generated_header": HEADER,
        "prior_crypto_subtree_gate": True,
        "attempted": True,
        "exit_code": rc,
        "timed_out": rc == 124,
        "compile_h_created": header_exists,
        "compile_h_anchors_valid": anchors_ok,
        "compile_h_macro_issues": macro_issues,
        "compile_h_macro_names": sorted(macro_values),
        "compile_h_uts_machine": macro_values.get("UTS_MACHINE"),
        "compile_h_bytes": hdr.stat().st_size if header_exists else 0,
        "compile_h_sha256": hashlib.sha256(hdr.read_bytes()).hexdigest()
            if header_exists else None,
        "init_version_object_created": object_exists,
        "errors_excerpt": errors[:25],
        "first_error_context": context[:30],
        "remaining_rejected_files": 64,
        "full_kernel_link_performed": False,
        "runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    STAGE50["forbid_images"](out)
    (report / OUTPUT).write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    for stage in (50, 66, 67, 68, 69, 72, 73, 75):
        parser.add_argument(f"--stage{stage}-report", type=Path, required=True)
    parser.add_argument("--clang-bin", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=270)
    a = parser.parse_args()
    result = execute(
        a.kernel.resolve(), a.output.resolve(), a.report.resolve(),
        a.stage50_report.resolve(), a.stage66_report.resolve(),
        a.stage67_report.resolve(), a.stage68_report.resolve(),
        a.stage69_report.resolve(), a.stage72_report.resolve(),
        a.stage73_report.resolve(), a.stage75_report.resolve(),
        a.clang_bin.resolve(), a.timeout,
    )
    print(json.dumps({
        "stage": result["stage"],
        "target": result["target"],
        "exit_code": result["exit_code"],
        "timed_out": result["timed_out"],
        "compile_h_created": result["compile_h_created"],
        "compile_h_anchors_valid": result["compile_h_anchors_valid"],
        "compile_h_macro_issues": result["compile_h_macro_issues"],
        "compile_h_uts_machine": result["compile_h_uts_machine"],
        "init_version_object_created": result["init_version_object_created"],
        "errors_excerpt": result["errors_excerpt"][:8],
        "kernel_built": False,
        "flash_ready": False,
    }, indent=2))


if __name__ == "__main__":
    main()
