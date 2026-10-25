#!/usr/bin/env python3
"""EXP27.2: compare immutable EXP25A/EXP27 build artifacts without booting a device."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--baseline", type=Path, required=True)
parser.add_argument("--candidate", type=Path, required=True)
parser.add_argument("--report", type=Path, default=Path("exp27-2-report.json"))
args = parser.parse_args()

B = args.baseline
C = args.candidate
checks = []
files = {}

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as fd:
        for chunk in iter(lambda: fd.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def gate(name, condition, evidence):
    checks.append({"gate": name, "pass": bool(condition), "evidence": str(evidence)})
    print(("PASS" if condition else "FAIL") + ": " + name + ": " + str(evidence))

def fingerprint(name, left, right):
    a, b = B / left, C / right
    exists = a.is_file() and b.is_file() and a.stat().st_size > 0 and b.stat().st_size > 0
    gate(name + "_files_present", exists, str(a) + " | " + str(b))
    if not exists:
        return
    old, new = sha256(a), sha256(b)
    files[name] = {"exp25a_sha256": old, "exp27_sha256": new,
                   "exp25a_bytes": a.stat().st_size, "exp27_bytes": b.stat().st_size}
    gate(name + "_bitwise_identical", old == new, old + " vs " + new)

base = "exp06-work/out/arch/arm64/boot/"
gate("artifact_dirs_exist", B.is_dir() and C.is_dir(), f"{B} | {C}")
for path in ("boot.img", "vendor_boot.img"):
    found = [str(p) for root in (B, C) for p in root.rglob(path)]
    gate("no_flash_image_" + path.replace(".", "_"), not found, found)

fingerprint("resolved_kernel_config", "exp06-work/out/.config", "exp06-work/out/.config")
fingerprint("device_tree_dtb", base + "dtb", base + "dtb")
fingerprint("device_tree_dtbo", base + "dtbo.img", base + "dtbo.img")
fingerprint("touchscreen_source_diff", "exp25-touch-code.diff", "exp25-touch-code.diff")
fingerprint("compiler_fingerprint", "exp06-clang-version.txt", "exp06-clang-version.txt")

for root, role in ((B, "EXP25A"), (C, "EXP27")):
    image = root / (base + "Image")
    ok = image.is_file() and image.stat().st_size > 4 * 1024 * 1024
    gate(role + "_kernel_Image_present", ok, str(image))
    if ok:
        files[role + "_Image"] = {"sha256": sha256(image), "bytes": image.stat().st_size}
        if role == "EXP27":
            gate("candidate_driver_version_literal", b"v1.10.11" in image.read_bytes(),
                 "Informational sanity check; linker Image should contain r8152 version")

cfg = C / "exp06-work/out/.config"
if cfg.is_file():
    txt = cfg.read_text(errors="replace")
    for symbol in ("CONFIG_USB_RTL8152=y", "CONFIG_TOUCHSCREEN_NT36532_HOSTDL_SPI=y",
                   "CONFIG_KSU=y", "CONFIG_PIPA_EXP_SUGOV_RATE_LIMIT_US=1500"):
        gate("config_" + symbol.split("=")[0], symbol in txt.splitlines(), symbol)
    gate("config_modules_disabled", "# CONFIG_MODULES is not set" in txt.splitlines()
         or "CONFIG_MODULES=n" in txt.splitlines(), "no loadable modules")

stage = C / "exp27-r8152-stage-gate.txt"
link = C / "exp24-rtl8153-link-gate.txt"
touch = C / "exp25-touch-final-gate.log"
gate("r8152_source_provenance", stage.is_file()
     and "R8152_TARGET=v1.10.11" in stage.read_text(errors="replace")
     and "92b51c4c46f57b660f3053804ba74f6df9e71c76" in stage.read_text(errors="replace"),
     "linux v5.4.290 blob pinned")
gate("rtl8153_linked", link.is_file() and "EXP24_RTL8153_LINK_PASS" in link.read_text(errors="replace"),
     "post-link RTL8153 symbol gate")
gate("touchscreen_verification_available", touch.is_file() and touch.stat().st_size > 0,
     "EXP25A touchscreen verification report present")

result = {
    "cycle": "EXP27.2",
    "baseline_run": 39190015939,
    "candidate_run": 40152429269,
    "checks": checks,
    "digests": files,
    "result": "PASS" if all(item["pass"] for item in checks) else "FAIL",
    "runtime_test": False,
    "flash_ready": False
}
args.report.parent.mkdir(parents=True, exist_ok=True)
args.report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
print("EXP27_2_STATIC_GATE=" + result["result"] + "; RUNTIME_NOT_TESTED; FLASH_READY=false")
sys.exit(0 if result["result"] == "PASS" else 1)
