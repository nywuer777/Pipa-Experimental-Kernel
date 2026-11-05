#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 PIPA_RT-vs-QEMU_RT platform config evidence / NO FLASH
"""Audit only true effective Kconfig values; classify vendor boot-risk candidates.

BOOT_PATH_CRITICAL = an item to inspect for early init/probe behaviour.
Only QCOM_SCM has an observed early SMC in EXP76 evidence.
No runtime validation of Qualcomm SCM on physical PIPA is implied.
"""
import argparse
import collections
import hashlib
import json
import re
from pathlib import Path

MATCH = ("QCOM", "MSM", "PDR", "RPMH", "SMEM", "GLINK", "QRTR", "TRUSTZONE")
CRITICAL = set("""
ARCH_QCOM QCOM_SCM QCOM_SCM_64 QRTR QCOM_GDSC COMMON_CLK_QCOM
QCOM_CLK_RPMH QCOM_APCS_IPC MSM_QMP RPMSG_QCOM_GLINK_NATIVE
RPMSG_QCOM_GLINK_SMEM RPMSG_QCOM_GLINK_SPSS QCOM_COMMAND_DB
QCOM_IPCC QCOM_MDT_LOADER QCOM_RPMH QCOM_SMEM QCOM_EARLY_RANDOM
QCOM_SMEM_STATE QCOM_SMP2P MSM_SUBSYSTEM_RESTART MSM_PIL
QCOM_WATCHDOG_V2 QCOM_GLINK QCOM_SMCINVOKE QCOM_PDC
""".split())
OPTIONAL = set("""
QCOM_KGSL QCOM_KGSL_IOMMU MSM_CVP_V4L2 MSM_NPU MSM_GLOBAL_SYNX
MSM_EXT_DISPLAY MSM_BT_POWER MSM_ADSPRPC MSM_HSUSB_PHY MSM_SSPHY_QMP
USB_DWC3_MSM USB_DWC3_QCOM CRYPTO_DEV_QCOM_MSM_QCE
QCOM_QMI_RMNET QCOM_QMI_DFC QCOM_QMI_POWER_COLLAPSE
MSM_SERVICE_NOTIFIER QCOM_QMI_HELPERS QCOM_FSA4480_I2C
MSM_CLK_AOP_QMP MSM_GCC_KONA MSM_VIDEOCC_KONA MSM_DISPCC_KONA
MSM_CAMCC_KONA MSM_GPUCC_KONA MSM_NPUCC_KONA MSM_CDSP_LOADER
QCOM_CDSP_RM QCOM_BIMC_BWMON DEVFREQ_GOV_QCOM_BW_HWMON
DEVFREQ_GOV_QCOM_CACHE_HWMON DEVFREQ_GOV_QCOM_ADRENO_TZ
DEVFREQ_GOV_QCOM_GPUBW_MON QCOM_DEVFREQ_DEVBW QCOM_VADC_COMMON
QCOM_SPMI_ADC5 QCOM_LLCC_PMU QCOM_QFPROM
""".split())
YES = re.compile(r"^(CONFIG_[A-Z0-9_]+)=(.*)$")
NO = re.compile(r"^# (CONFIG_[A-Z0-9_]+) is not set$")


def read(path):
    values = {}
    for line in path.read_text().splitlines():
        m = YES.fullmatch(line) or NO.fullmatch(line)
        if m:
            values[m.group(1)] = (m.group(2) if m.re is YES else "n")
    if len(values) < 200:
        raise RuntimeError("Incomplete effective Kconfig: " + str(path))
    return values


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--pipa", required=True, type=Path)
    cli.add_argument("--qemu", required=True, type=Path)
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args()
    pipa, qemu = read(args.pipa), read(args.qemu)
    if pipa.get("CONFIG_QCOM_SCM") != "y":
        raise RuntimeError("PIPA_RT CONFIG_QCOM_SCM must remain y")
    if qemu.get("CONFIG_QCOM_SCM") != "n":
        raise RuntimeError("QEMU_RT CONFIG_QCOM_SCM was reselected by Kconfig")
    if pipa.get("CONFIG_PREEMPT_RT_FULL") != "y" or qemu.get("CONFIG_PREEMPT_RT_FULL") != "y":
        raise RuntimeError("RT must be enabled in both configs")
    keys = sorted(k for k, v in pipa.items() if v == "y"
                  and any(t in k for t in MATCH))
    entries = []
    for key in keys:
        name = key.removeprefix("CONFIG_")
        category = ("BOOT_PATH_CRITICAL" if name in CRITICAL else
                    "RUNTIME_OPTIONAL" if name in OPTIONAL else "UNKNOWN")
        entries.append({
            "symbol": key, "pipa_rt": pipa[key],
            "qemu_rt": qemu.get(key, "<absent>"),
            "classification": category,
            "verified_early_smc": name == "QCOM_SCM",
            "classification_basis": (
                "Observed early firmware SMC in QEMU and source-symbollized"
                if name == "QCOM_SCM" else
                "Potential early platform/initcall dependency; not proof of actual SMC/HVC"
                if category == "BOOT_PATH_CRITICAL" else
                "Device/service likely gated by platform DT; actual initcall timing unverified"
                if category == "RUNTIME_OPTIONAL" else
                "Unreviewed early-call path"),
        })
    groups = dict(collections.Counter(x["classification"] for x in entries))
    vendor_differences = [
        {"symbol": key, "pipa": pipa.get(key, "<absent>"),
         "qemu": qemu.get(key, "<absent>")}
        for key in sorted(set(pipa) | set(qemu))
        if pipa.get(key) != qemu.get(key) and any(t in key for t in MATCH)
    ]
    record = {
        "schema_version": 1, "stage": "EXP76_QEMU_ONLY_SCM_VENDOR_CONFIG_SCOPE",
        "source": "ACTUAL_FINAL_OLDDEFCONFIG_PIPA_RT_AND_QEMU_RT",
        "pipa_config_sha256": hashlib.sha256(args.pipa.read_bytes()).hexdigest(),
        "qemu_config_sha256": hashlib.sha256(args.qemu.read_bytes()).hexdigest(),
        "vendor_pipa_enabled_count": len(keys), "class_counts": groups,
        "early_smc_hvc_confirmed": 1,
        "early_smc_symbol": "CONFIG_QCOM_SCM",
        "all_vendor_config_differences": vendor_differences,
        "qemu_scm_enabled": False, "pipa_scm_enabled": True,
        "pipa_scm_hardware_verified": False,
        "qemu_scope_includes": ["scheduler", "RCU", "locking", "time", "IRQ",
                                "mm", "arch/arm64", "init"],
        "qemu_scope_excludes": ["Qualcomm TrustZone SCM firmware service",
                                "PIPA physical firmware/hardware validation",
                                "vendor ABI compatibility"],
        "categories_are_risks_not_confirmed_early_probes": True,
        "entries": entries,
        "rt_handoff_ready": False, "flash_ready": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2) + "\n")
    print("EXP76_PIPA_QCOM_SCM=y")
    print("EXP76_QEMU_QCOM_SCM=n")
    print("EXP76_PLATFORM_VENDOR_OPTIONS=", len(entries))
    print("EXP76_PLATFORM_EARLY_SMC_CONFIRMED=1")
    print("EXP76_PLATFORM_RISK_CLASS_COUNTS=", groups)
    print("EXP76_VENDOR_PIPA_QEMU_DIFFS=", len(vendor_differences))


if __name__ == "__main__":
    main()
