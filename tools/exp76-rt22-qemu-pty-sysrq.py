#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / QEMU ARM64 RT SysRq serial PTY guest task dump / NO FLASH
"""Boot pinned Image with PL011 serial PTY; send real tty BREAK + t at 5 seconds.

This is a diagnostic only: SysRq and a host exit code do not imply guest boot
success. Full guest PTY bytes and host diagnostics are saved separately.
"""
import argparse
import hashlib
import json
import os
import re
import selectors
import shlex
import subprocess
import termios
import time
import tty
from pathlib import Path

PTY_RE = re.compile(rb"char device redirected to (/dev/pts/[0-9]+)")
BOOT_APPEND = (
    "earlycon=pl011,0x09000000 console=ttyAMA0,115200 "
    "loglevel=8 ignore_loglevel printk.time=1 nokaslr panic=5 "
    "initcall_debug=1 sysrq_always_enabled=1 init=/init"
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True, type=Path)
    ap.add_argument("--initrd", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--max-seconds", type=float, default=38.0)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for item in (args.image, args.initrd):
        if not item.is_file() or item.stat().st_size == 0:
            raise RuntimeError("Missing QEMU input: " + str(item))
    cmd = [
        "qemu-system-aarch64", "-M", "virt", "-cpu", "cortex-a72",
        "-smp", "4", "-m", "512", "-nodefaults", "-serial", "pty",
        "-monitor", "none", "-display", "none", "-nic", "none", "-no-reboot",
        "-kernel", str(args.image), "-initrd", str(args.initrd),
        "-append", BOOT_APPEND,
    ]
    cmdtext = shlex.join(cmd) + "\n"
    (args.out / "qemu-cmdline.txt").write_text(cmdtext)
    cmd = shlex.split((args.out / "qemu-cmdline.txt").read_text())
    start = time.monotonic()
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, bufsize=0)
    stream = proc.stdout
    assert stream is not None
    os.set_blocking(stream.fileno(), False)
    sel = selectors.DefaultSelector()
    sel.register(stream.fileno(), selectors.EVENT_READ, "qemu_status")
    fd = None
    pty_name = None
    serial = bytearray()
    host = bytearray()
    actions = []
    break_sent = False
    nul_sent = False
    while time.monotonic() - start < args.max_seconds:
        elapsed = time.monotonic() - start
        if fd is not None and elapsed >= 5 and not break_sent:
            try:
                termios.tcsendbreak(fd, 0)
                os.write(fd, b"t")
                actions.append({"seconds":round(elapsed, 6),
                                "action":"termios_tcsendbreak_and_t",
                                "result":"sent"})
            except OSError as e:
                actions.append({"seconds":round(elapsed, 6),
                                "action":"termios_tcsendbreak_and_t",
                                "result":"error", "detail":str(e)})
            break_sent = True
        if fd is not None and elapsed >= 18 and not nul_sent:
            try:
                os.write(fd, b"\x00t")
                actions.append({"seconds":round(elapsed, 6),
                                "action":"NUL_t_fallback_NOT_SERIAL_BREAK", "result":"sent"})
            except OSError as e:
                actions.append({"seconds":round(elapsed, 6),
                                "action":"NUL_t_fallback_NOT_SERIAL_BREAK", "result":str(e)})
            nul_sent = True
        for event, _ in sel.select(timeout=0.15):
            try:
                chunk = os.read(event.fd, 65536)
            except BlockingIOError:
                continue
            except OSError:
                chunk = b""
            if not chunk:
                try:
                    sel.unregister(event.fd)
                except Exception:
                    pass
                continue
            if event.data == "qemu_status":
                host.extend(chunk)
                if fd is None:
                    m = PTY_RE.search(host)
                    if m:
                        pty_name = m.group(1).decode()
                        fd = os.open(pty_name, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
                        tty.setraw(fd, termios.TCSANOW)
                        sel.register(fd, selectors.EVENT_READ, "guest_serial")
            else:
                serial.extend(chunk)
        if proc.poll() is not None:
            # Drain already-buffered serial bytes for a short interval.
            if time.monotonic() - start > .2:
                break
    elapsed = time.monotonic() - start
    was_alive = proc.poll() is None
    if was_alive:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    if fd is not None:
        # Drain any bytes buffered on the PTY before closing it.
        for _ in range(50):
            try:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                serial.extend(chunk)
            except (BlockingIOError, OSError):
                break
        os.close(fd)
    for f in list(sel.get_map().values()):
        try:
            sel.unregister(f.fd)
        except Exception:
            pass
    sel.close()
    serial_data = bytes(serial)
    (args.out / "console-rt-pty.txt").write_bytes(serial_data)
    (args.out / "host-qemu-stderr.txt").write_bytes(bytes(host))
    guest = serial_data.decode("utf-8", "replace").replace("\r", "")
    # Require a real guest SysRq command acknowledgement, not its boot option.
    sysrq_lines = [line for line in guest.splitlines()
                   if re.search(r"\bSysRq\s*:\s*(?:Show State|Show Blocked|HELP|[A-Z])", line, re.I)
                   and "always enabled" not in line.lower()
                   and "kernel command line:" not in line.lower()]
    report = {
        "schema": 1,
        "case": "R22_H10_ALREADY_SATISFIED_QEMU_SYSRQ_SERIAL",
        "source_image_sha256": sha(args.image.read_bytes()),
        "initramfs_sha256": sha(args.initrd.read_bytes()),
        "cmd_sha256": sha(cmdtext.encode()),
        "pty": pty_name,
        "config_required": ["CONFIG_MAGIC_SYSRQ=y", "CONFIG_MAGIC_SYSRQ_SERIAL=y"],
        "duration_seconds": round(time.monotonic()-start,6),
        "max_seconds": args.max_seconds,
        "qemu_exit_code": proc.returncode,
        "host_terminated_for_timeout": was_alive,
        "console_sha256": sha(serial_data),
        "console_bytes": len(serial_data),
        "console_lines": len(serial_data.splitlines()),
        "console_first_40_lines": guest.splitlines()[:40],
        "console_last_90_lines": guest.splitlines()[-90:],
        "host_status_sha256": sha(bytes(host)),
        "host_status_bytes": len(host),
        "pty_actions": actions,
        "sysrq_observed": bool(sysrq_lines),
        "sysrq_evidence_lines": sysrq_lines[-60:],
        "pid1_stack_captured": bool(sysrq_lines and re.search(r"(?:^|\n).*?(?:\bpid[: ]+1\b|\bPID[: ]+1\b|\btask:.*\b1\b)", guest, re.I)),
        "guest_begin": "EXP76_QEMU_RT_SMOKE=BEGIN" in guest,
        "guest_running": "EXP76_QEMU_RT_SMOKE=GUEST_RUNNING" in guest,
        "kernel_panic": "Kernel panic" in guest,
        "qemu_boot_pass": "EXP76_QEMU_RT_SMOKE=GUEST_RUNNING" in guest
                          and "Kernel panic" not in guest,
        "rt_handoff_ready": False,
        "flash_ready": False,
    }
    (args.out / "sysrq-pty-result.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k not in
                      ("console_first_40_lines","console_last_90_lines","sysrq_evidence_lines")},indent=2))
    print("EXP76_R22_CONSOLE_LAST_40")
    print("\n".join(report["console_last_90_lines"][-40:]))
    print("EXP76_R22_PTY_CAPTURE_COMPLETE")

if __name__ == "__main__":
    main()
