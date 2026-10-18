#!/usr/bin/env python3
"""EXP24: pinned ethernet.config -> builtin pipa defconfig, never silently ignore unsupported options."""
import argparse
import hashlib
import re
import sys
from pathlib import Path

SOURCE_SHA256 = 'bb561eac2eaeb15157b396f7807c30793348b65e14cb4b0821e4a66d8ecc11b0'
UNSUPPORTED = {'CONFIG_USB_NET_AQC111': 'Missing from pinned E404 drivers/net/usb/Kconfig; no AQC111 source/Makefile target'}
SYM = re.compile(r'^\s*(config|menuconfig)\s+([A-Z0-9_]+)\s*$', re.M)
ASSIGN = re.compile(r'^(CONFIG_[A-Z0-9_]+)=(y|m|n)\s*$', re.M)


def parse_upload(path):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        raise ValueError('uploaded ethernet.config SHA256 mismatch')
    requested = {}
    for n, line in enumerate(data.decode('utf-8-sig').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        m = ASSIGN.fullmatch(line)
        if not m or m.group(2) != 'y':
            raise ValueError(f'invalid ethernet.config entry line {n}: {line}')
        if m.group(1) in requested:
            raise ValueError(f'duplicate option {m.group(1)}')
        requested[m.group(1)] = 'y'
    if len(requested) != 22 or set(UNSUPPORTED) - set(requested):
        raise ValueError('unexpected symbol manifest (not pinned 22-option attachment)')
    return requested


def check_sources(kernel, requested):
    source = kernel / 'drivers/net/usb/Kconfig'
    if not source.is_file():
        raise ValueError('USB network Kconfig missing')
    usb_symbols = {m.group(2) for m in SYM.finditer(source.read_text())}
    for name in requested:
        if name.startswith(('CONFIG_USB_',)) and name not in UNSUPPORTED and name[7:] not in usb_symbols:
            # USB base options are in drivers/usb/core/Kconfig, not here.
            if name not in ('CONFIG_USB_NET_DRIVERS', 'CONFIG_USB_USBNET'):
                raise ValueError(f'USB Kconfig symbol absent: {name}')
    if 'USB_NET_AQC111' in usb_symbols:
        raise ValueError('Source unexpectedly supports AQC111; re-review exclusion before enabling')
    return usb_symbols


def update_config(file, desired):
    if not file.exists():
        raise ValueError(f'missing required defconfig/config: {file}')
    lines = file.read_text().splitlines(keepends=True)
    match = re.compile(r'^(?:# )?(CONFIG_[A-Z0-9_]+)(?:=(?:y|n|m|[^\s]+)| is not set)\s*$')
    seen = set()
    result = []
    modified = []
    for line in lines:
        m = match.fullmatch(line.rstrip('\r\n'))
        if m and m.group(1) in desired:
            name = m.group(1)
            if name in seen:
                raise ValueError(f'duplicate config symbol in {file}: {name}')
            seen.add(name)
            new = f'{name}=y\n'
            if line != new:
                modified.append(name)
            result.append(new)
        else:
            result.append(line)
    for name in desired:
        if name not in seen:
            modified.append(name)
            result.append(f'{name}=y\n')
    file.write_text(''.join(result))
    return modified


def verify_config(file, desired):
    txt = file.read_text()
    if 'CONFIG_MODULES=n' not in txt and '# CONFIG_MODULES is not set' not in txt:
        raise ValueError('MODULES may be enabled; builtin policy not proven')
    if 'CONFIG_PIPA_EXP_SUGOV=y' not in txt or 'CONFIG_PIPA_EXP_SUGOV_RATE_LIMIT_US=1500' not in txt:
        raise ValueError('EXP06 schedutil patch not preserved')
    for name in desired:
        if len(re.findall(rf'^{re.escape(name)}=y$', txt, re.M)) != 1:
            raise ValueError(f'{name} not resolved to builtin y')
    return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True, type=Path)
    p.add_argument('--kernel', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--mode', choices=('apply','verify'), required=True)
    args = p.parse_args()
    requested = parse_upload(args.source)
    check_sources(args.kernel, requested)
    desired = {x:'y' for x in requested if x not in UNSUPPORTED}
    assert len(desired) == 21
    print('EXP24 requested=22 source_supported=21 unsupported=CONFIG_USB_NET_AQC111')
    print('EXP24 excluded AQC111: Kconfig, source, Makefile target absent in pinned E404 (not silently enabled)')
    config = args.kernel / 'arch/arm64/configs/vendor/pipa_defconfig' if args.mode == 'apply' else args.out / '.config'
    if args.mode == 'apply':
        modified = update_config(config, desired)
        print('EXP24 apply builtin defconfig: symbols_changed=' + str(len(modified)))
        # EXP01's builder may reuse out/.config rather than running pipa_defconfig again.
        # Align both possible inputs, then require final resolved .config after build.
        out_config = args.out / '.config'
        if out_config.is_file():
            changed_out = update_config(out_config, desired)
            print('EXP24 apply already-existing out/.config: symbols_changed=' + str(len(changed_out)))
    else:
        verify_config(config, desired)
        print('EXP24 final resolved kernel .config: ALL 21 SUPPORTED CONFIG SYMBOLS = y; EXP06 SUGOV 1500 PRESERVED; MODULES DISABLED')
    print('EXP24 CONFIG_GATE=PASS')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as exc:
        sys.exit('EXP24 CONFIG_GATE=FAIL: '+str(exc))
