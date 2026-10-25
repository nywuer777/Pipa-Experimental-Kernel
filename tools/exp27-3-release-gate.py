#!/usr/bin/env python3
"""EXP27.3: fail-closed artifact/recovery readiness audit. NEVER boots or flashes hardware."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

BASE_REL = Path("exp06-work/out/arch/arm64/boot")
EXPECTED = {
    "baseline_image_sha256": "2dac2dd05fe3cab8b167ea10bc632512c1508fa4d26db88d002837d0dc681e08",
    "candidate_image_sha256": "a14b536b471c97db877482afe97bcbeb97daa74ebc48a3a344d90ead57d56967",
    "baseline_run": 39190015939,
    "candidate_run": 40152429269,
    "audit_run": 40153757336,
    "candidate_r8152_blob": "92b51c4c46f57b660f3053804ba74f6df9e71c76",
}
MATCH = (
    "exp06-work/out/.config",
    "exp06-work/out/arch/arm64/boot/dtb",
    "exp06-work/out/arch/arm64/boot/dtbo.img",
    "exp25-touch-code.diff",
    "exp06-clang-version.txt",
)
REQUIRED_CONFIG = (
    "CONFIG_USB_RTL8152=y",
    "CONFIG_TOUCHSCREEN_NT36532_HOSTDL_SPI=y",
    "CONFIG_KSU=y",
    "CONFIG_PIPA_EXP_SUGOV_RATE_LIMIT_US=1500",
)
BLOCKED_FILES = ("boot.img", "vendor_boot.img", "vbmeta.img", "dtbo.img")

def filehash(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def verify(base, candidate, audit):
    checks = []
    def check(name, ok, detail=""):
        checks.append({"gate": name, "pass": bool(ok), "detail": str(detail)})
    base, candidate, audit = Path(base), Path(candidate), Path(audit)
    check("dirs_present", base.is_dir() and candidate.is_dir())
    for root, label, sha_name in (
        (base, "exp25a", "baseline_image_sha256"),
        (candidate, "exp27", "candidate_image_sha256"),
    ):
        img = root / BASE_REL / "Image"
        ok = img.is_file() and img.stat().st_size > 4_000_000
        check(label + "_image_exists", ok)
        if ok:
            actual = filehash(img)
            check(label + "_image_hash_pinned", actual == EXPECTED[sha_name],
                  actual)
    for p in MATCH:
        a, b = base / p, candidate / p
        ok = a.is_file() and b.is_file() and a.stat().st_size > 0 and b.stat().st_size > 0
        check("present:" + p, ok)
        if ok:
            check("identical:" + p, filehash(a) == filehash(b))
    cfg = candidate / "exp06-work/out/.config"
    if cfg.is_file():
        lines = set(cfg.read_text(errors="replace").splitlines())
        for sym in REQUIRED_CONFIG:
            check("config:" + sym, sym in lines)
        check("config:no_modules", ("# CONFIG_MODULES is not set" in lines
                                    or "CONFIG_MODULES=n" in lines))
    else:
        check("config_available", False)
    stage = candidate / "exp27-r8152-stage-gate.txt"
    if stage.is_file():
        s = stage.read_text(errors="replace")
        check("r8152_pinned_source", "R8152_TARGET=v1.10.11" in s
              and EXPECTED["candidate_r8152_blob"] in s)
    else:
        check("r8152_pinned_source", False)
    link = candidate / "exp24-rtl8153-link-gate.txt"
    check("r8153_postlink", link.is_file() and
          "EXP24_RTL8153_LINK_PASS" in link.read_text(errors="replace")
          if link.is_file() else False)
    # The previous immutable audit report is additional corroboration.
    try:
        data = json.loads(audit.read_text())
        check("independent_audit_pass", data.get("result") == "PASS"
              and data.get("baseline_run") == EXPECTED["baseline_run"]
              and data.get("candidate_run") == EXPECTED["candidate_run"]
              and bool(data.get("checks"))
              and all(c.get("pass") is True for c in data["checks"]))
    except (OSError, ValueError, TypeError, KeyError):
        check("independent_audit_pass", False)
    for root, label in ((base, "exp25a"), (candidate, "exp27")):
        # A firmware / recovery image must never appear as a build output.
        found = [str(p.relative_to(root)) for p in root.rglob("*")
                 if p.is_file() and p.name in BLOCKED_FILES]
        # dtbo.img is a normal Device Tree overlay, NOT a flashable boot.img.
        found = [p for p in found if Path(p).name != "dtbo.img"]
        check(label + "_no_flashable_boot_outputs", not found, ", ".join(found))
    static_pass = all(c["pass"] for c in checks)
    return {
        "cycle": "EXP27.3",
        "result": "STATIC_PASS" if static_pass else "BLOCKED",
        "checks": checks,
        "artifact_references": EXPECTED.copy(),
        "operator_physical_recovery_verified": False,
        "pipa_runtime_tested": False,
        "touchscreen_postboot_verified": False,
        "usb_pd_recovery_verified": False,
        "temporary_boot_authorized": False,
        "flash_ready": False,
        "reason": ("Artifact integrity passed; hardware recovery, touchscreen and PD "
                   "still unverified. Do not boot, flash or change slots."
                   if static_pass else
                   "Static evidence incomplete or inconsistent; stop before hardware."),
    }

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--audit", type=Path, required=True)
    ap.add_argument("--report", type=Path, default=Path("exp27-3-gate.json"))
    args = ap.parse_args(argv)
    result = verify(args.baseline, args.candidate, args.audit)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print("EXP27_3_STATIC_GATE=" + result["result"])
    for c in result["checks"]:
        print(("PASS" if c["pass"] else "FAIL") + " " + c["gate"] +
              (" " + c["detail"] if c["detail"] else ""))
    print("TEMP_BOOT_AUTHORIZED=false; FLASH_READY=false; NO_DEVICE_COMMANDS")
    return 0 if result["result"] == "STATIC_PASS" else 1

if __name__ == "__main__":
    sys.exit(main())
