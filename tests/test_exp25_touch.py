#!/usr/bin/env python3
"""EXP25A hermetic mutation tests; no device/kernel/boot access."""
import importlib.util
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("exp25", ROOT / "tools/exp25-apply-touch.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def run():
    old = (
        "/* NVT suspend */\n"
        + mod.SUSPEND + "\n"
        + mod.BEFORE + "\n"
        + "\t/* Firmware loading remains untouched */\n"
        + "\tif (nvt_update_firmware(ts->fw_name)) {\n"
        + "\t\tNVT_ERR(\"download firmware failed, ignore check fw state\\n\");\n"
        + "\t}\n"
        + mod.OLD
        + "\tbTouchIsAwake = 1;\n"
        + "\treturn 0;\n"
        + "}\n" + mod.AFTER + "(void) {}\n"
    )
    new, changed = mod.transform(old)
    assert changed
    assert new != old
    assert mod.OLD not in new
    assert mod.SUSPEND in new
    assert new.count("nvt_update_firmware(ts->fw_name)") == 1
    assert new.count("bTouchIsAwake = 1") == 1
    assert new.count("EXP25A_IRQ_RESTORE") == 1
    assert new.replace(mod.NEW, mod.OLD) == old, "unintended source changes"
    mod.verify_source(new)
    same, changed = mod.transform(new)
    assert not changed and same == new, "not idempotent"
    for malformed in (old.replace(mod.OLD, ""),
                      old.replace(mod.BEFORE, ""),
                      old.replace(mod.SUSPEND, ""),
                      old.replace(mod.OLD, mod.OLD * 2)):
        try:
            mod.transform(malformed)
        except ValueError:
            pass
        else:
            raise AssertionError("accepted malformed NVT source")
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / ".config"
        valid = "\n".join((
            "CONFIG_TOUCHSCREEN_NT36532_HOSTDL_SPI=y",
            "CONFIG_USB_RTL8152=y",
            "CONFIG_PIPA_EXP_SUGOV=y",
            "CONFIG_PIPA_EXP_SUGOV_RATE_LIMIT_US=1500",
            "CONFIG_KSU=y",
            "# CONFIG_MODULES is not set",
            "",
        ))
        path.write_text(valid)
        mod.verify_config(path)
        path.write_text(valid.replace("CONFIG_USB_RTL8152=y", "CONFIG_USB_RTL8152=m"))
        try:
            mod.verify_config(path)
        except ValueError:
            pass
        else:
            raise AssertionError("accepted missing builtin Ethernet driver")
    print("EXP25A_HERMETIC_TESTS=PASS")
    print("NVT mutation isolated, idempotent, fail-closed and preserves EXP24")

if __name__ == "__main__":
    run()
