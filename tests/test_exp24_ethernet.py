#!/usr/bin/env python3
"""Hermetic EXP24 checks; no kernel, tablet, network, boot or flash access."""
import importlib.util
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('exp24', ROOT/'tools/exp24-apply-ethernet.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def run():
    source = ROOT/'configs/ethernet.config'
    requested = mod.parse_upload(source)
    assert len(requested) == 22
    desired = {name:'y' for name in requested if name not in mod.UNSUPPORTED}
    assert len(desired) == 21
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        kconfig = root/'drivers/net/usb/Kconfig'
        kconfig.parent.mkdir(parents=True)
        kconfig.write_text('\n'.join('config '+k[7:] for k in desired if k.startswith('CONFIG_USB_')))
        assert mod.check_sources(root, requested)
        config = root/'arch/arm64/configs/vendor/pipa_defconfig'
        config.parent.mkdir(parents=True)
        config.write_text('# CONFIG_MODULES is not set\nCONFIG_PIPA_EXP_SUGOV=y\nCONFIG_PIPA_EXP_SUGOV_RATE_LIMIT_US=1500\n# CONFIG_USB_RTL8152 is not set\n')
        mod.update_config(config, desired)
        assert mod.verify_config(config, desired)
        baseline = config.read_bytes()
        mod.update_config(config, desired)
        assert config.read_bytes() == baseline, 'update is not idempotent'
        config.write_text(baseline.decode().replace('CONFIG_USB_RTL8152=y', 'CONFIG_USB_RTL8152=m'))
        try: mod.verify_config(config, desired)
        except ValueError: pass
        else: raise AssertionError('accepted RTL8152=m instead of builtin')
        kconfig.write_text(kconfig.read_text().replace('config USB_RTL8152', 'config USB_UNKNOWN'))
        try: mod.check_sources(root, requested)
        except ValueError: pass
        else: raise AssertionError('accepted missing Kconfig driver')
        modified = root/'modified.config'
        modified.write_bytes(source.read_bytes() + b'\n')
        try: mod.parse_upload(modified)
        except ValueError: pass
        else: raise AssertionError('accepted mismatching user upload digest')
    print('EXP24 SYNTHETIC KCONFIG TESTS PASS: 21 builtin drivers, idempotent, reject missing/m, bad input SHA')

if __name__ == '__main__':
    run()
