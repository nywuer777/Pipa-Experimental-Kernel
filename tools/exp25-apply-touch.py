#!/usr/bin/env python3
"""EXP25A: surgical, idempotent NVT IRQ restoration on panel resume.

This patch changes *only* the NVT-ts resume IRQ gate; it intentionally does NOT
alter Novatek firmware, SPI timing, device-tree, power delivery or USB networking.
E404 source pin and toolchain identities are checked by the calling workflow.
"""
import argparse
import sys
from pathlib import Path

TOUCH = Path("drivers/input/touchscreen/nt36532/nt36xxx.c")
OLD = "\tif (!ts->db_wakeup) {\n\t\tnvt_irq_enable(true);\n\t}\n"
NEW = (
    "\t/* EXP25A: the awake panel always requires its touchscreen IRQ.\n"
    "\t * Gesture wakeup may have changed after suspend disabled this IRQ.\n"
    "\t * nvt_irq_enable() is idempotent via ts->irq_enabled.\n"
    "\t */\n"
    "\tnvt_irq_enable(true);\n"
    "\tNVT_LOG(\"EXP25A_IRQ_RESTORE db_wakeup=0x%02x irq_enabled=%u\\n\",\n"
    "\t\tts->db_wakeup, ts->irq_enabled);\n"
)
# Restrict mutation to resume only, not probe/suspend or any other driver.
BEFORE = "static int32_t nvt_ts_resume(struct device *dev)\n{"
AFTER = "\n#if defined(CONFIG_DRM_PANEL)\nstatic int nvt_drm_panel_notifier_callback"
SUSPEND = "\tif (!ts->db_wakeup)\n\t\tnvt_irq_enable(false);"


def transform(text):
    if text.count(BEFORE) != 1 or text.count(AFTER) != 1:
        raise ValueError("NVT resume anchors missing or ambiguous")
    start = text.index(BEFORE)
    end = text.index(AFTER, start)
    fragment = text[start:end]
    if text.count(SUSPEND) != 1:
        raise ValueError("original NVT suspend IRQ behavior not found")
    if NEW in fragment and OLD not in fragment:
        return text, False
    if fragment.count(OLD) != 1 or NEW in fragment:
        raise ValueError("original NVT resume IRQ gate missing or ambiguous")
    return text[:start] + fragment.replace(OLD, NEW, 1) + text[end:], True


def verify_source(text):
    changed, modified = transform(text)
    if modified or changed != text:
        raise ValueError("EXP25A IRQ restore is not applied")
    if text.count("EXP25A_IRQ_RESTORE") != 1:
        raise ValueError("EXP25A diagnostic signature not unique")
    if text.count(SUSPEND) != 1:
        raise ValueError("NVT suspend IRQ gate unexpectedly modified")


def verify_config(config):
    text = config.read_text()
    required = (
        "CONFIG_TOUCHSCREEN_NT36532_HOSTDL_SPI=y",
        "CONFIG_USB_RTL8152=y",
        "CONFIG_PIPA_EXP_SUGOV=y",
        "CONFIG_PIPA_EXP_SUGOV_RATE_LIMIT_US=1500",
        "CONFIG_KSU=y",
    )
    for line in required:
        if text.splitlines().count(line) != 1:
            raise ValueError("missing required resolved config: " + line)
    if "CONFIG_MODULES=y" in text:
        raise ValueError("modules enabled unexpectedly")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--kernel", required=True, type=Path)
    p.add_argument("--mode", choices=("apply", "verify"), required=True)
    p.add_argument("--config", type=Path)
    args = p.parse_args()
    target = args.kernel / TOUCH
    if not target.is_file():
        raise ValueError("NVT source missing: " + str(target))
    original = target.read_text()
    patched, changed = transform(original)
    if args.mode == "apply":
        if changed:
            target.write_text(patched)
        verify_source(target.read_text())
    else:
        verify_source(original)
        if not args.config or not args.config.is_file():
            raise ValueError("final resolved .config required for verify")
        verify_config(args.config)
    print("EXP25A_NVT_IRQ_GATE=PASS")
    print("NVT resume IRQ unconditional + one diagnostic marker; original suspend maintained")
    print("FIRMWARE_RECOVERY_UNCHANGED=true; RTL8153_AND_SUGOV_PRESERVED=true")
    print("FLASH_READY=false")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        sys.exit("EXP25A_NVT_IRQ_GATE=FAIL: " + str(exc))
