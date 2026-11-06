#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / QEMU ARM64 PL011 PTY BREAK+t SysRq / NO FLASH
"""Launch pinned RT QEMU with a serial PTY, request SysRq-t, archive every byte.

QEMU exit 0 is not guest success. A NUL byte is NOT a serial BREAK, so this
uses both the requested NUL and a PTY BREAK ioctl plus the 't' command. The
record distinguishes an attempted SysRq from actual guest acknowledgement.
"""
import argparse
import errno
import fcntl
import hashlib
import json
import os
import re
import select
import signal
import subprocess
import termios
import time
import tty
from pathlib import Path

PTY_RE = re.compile(rb"char device redirected to (/dev/pts/\d+)")
PANIC = (b"Kernel panic", b"Internal error: Oops", b"Oops: ")
GUEST_MARK = b"EXP76_QEMU_RT_SMOKE=GUEST_RUNNING"


def hash_bytes(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--image", type=Path, required=True)
    p.add_argument("--initrd", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--timeout", type=int, default=35)
    args = p.parse_args()
    if args.timeout < 15:
        raise ValueError("At least 15 seconds required for two BREAK attempts")
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    image = args.image.resolve()
    initrd = args.initrd.resolve()
    if not image.is_file() or not initrd.is_file():
        raise FileNotFoundError("Pinned Image and smoke initramfs required")
    append = ("earlycon=pl011,0x09000000 console=ttyAMA0,115200 "
              "loglevel=8 ignore_loglevel printk.time=1 nokaslr panic=5 "
              "init=/init initcall_debug=1 sysrq_always_enabled=1")
    cmd = [
        "qemu-system-aarch64", "-M", "virt", "-cpu", "cortex-a72",
        "-smp", "4", "-m", "512", "-nodefaults", "-serial", "pty",
        "-monitor", "none", "-display", "none", "-nic", "none",
        "-no-reboot", "-kernel", str(image), "-initrd", str(initrd),
        "-append", append,
    ]
    (out / "qemu-argv.json").write_text(json.dumps(cmd, indent=2) + "\n")
    (out / "qemu-append.txt").write_text(append + "\n")
    qemu = subprocess.Popen(
        cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, bufsize=0,
    )
    os.set_blocking(qemu.stdout.fileno(), False)
    pty_fd = None
    pty_name = None
    term_attr = None
    output = bytearray()
    host_output = bytearray()
    attempts = []
    t0 = time.monotonic()
    checkpoints = [5, 12]

    def try_sysrq():
        if pty_fd is None:
            return {"at_s": round(time.monotonic()-t0, 3), "status": "PTY_NOT_FOUND"}
        attempt = {"at_s": round(time.monotonic()-t0, 3),
                   "pty": pty_name, "null_byte_sent": False,
                   "break_ioctls": [], "t_byte_sent": False}
        try:
            os.write(pty_fd, b"\x00")
            attempt["null_byte_sent"] = True
        except OSError as e:
            attempt["null_errno"] = e.errno
        # TCSBRK is a real POSIX break request. PTYs may ignore it.
        try:
            termios.tcsendbreak(pty_fd, 0)
            attempt["break_ioctls"].append("TCSBRK_OK")
        except (OSError, termios.error) as e:
            attempt["break_ioctls"].append("TCSBRK_FAIL_" + str(e))
        if hasattr(termios, "TIOCSBRK") and hasattr(termios, "TIOCCBRK"):
            try:
                fcntl.ioctl(pty_fd, termios.TIOCSBRK)
                time.sleep(.15)
                fcntl.ioctl(pty_fd, termios.TIOCCBRK)
                attempt["break_ioctls"].append("TIOCSBRK_TIOCCBRK_OK")
            except OSError as e:
                attempt["break_ioctls"].append("TIOCSBRK_FAIL_" + str(e))
        try:
            os.write(pty_fd, b"t")
            attempt["t_byte_sent"] = True
        except OSError as e:
            attempt["t_errno"] = e.errno
        attempt["status"] = "REQUEST_SENT_NOT_PROOF_OF_GUEST_ACK"
        return attempt

    timed_out = False
    try:
        while time.monotonic()-t0 < args.timeout:
            fds = [qemu.stdout.fileno()]
            if pty_fd is not None:
                fds.append(pty_fd)
            ready, _, _ = select.select(fds, [], [], .2)
            for fd in ready:
                try:
                    chunk = os.read(fd, 16384)
                except (BlockingIOError, InterruptedError):
                    continue
                except OSError as e:
                    if e.errno in (errno.EIO, errno.EBADF):
                        continue
                    raise
                if not chunk:
                    continue
                if fd == qemu.stdout.fileno():
                    host_output.extend(chunk)
                    if pty_fd is None:
                        match = PTY_RE.search(host_output)
                        if match:
                            pty_name = match.group(1).decode()
                            pty_fd = os.open(pty_name, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
                            term_attr = termios.tcgetattr(pty_fd)
                            tty.setraw(pty_fd)
                else:
                    output.extend(chunk)
            elapsed = time.monotonic()-t0
            while checkpoints and elapsed >= checkpoints[0]:
                checkpoints.pop(0)
                attempts.append(try_sysrq())
            if GUEST_MARK in output and not any(marker in output for marker in PANIC):
                break
            if qemu.poll() is not None:
                break
        else:
            timed_out = True
    finally:
        if qemu.poll() is None:
            qemu.terminate()
            try:
                qemu.wait(timeout=4)
            except subprocess.TimeoutExpired:
                qemu.kill()
                qemu.wait(timeout=3)
        if pty_fd is not None:
            # Drain any final PTY output after the process is gone.
            for _ in range(8):
                try:
                    chunk = os.read(pty_fd, 65536)
                    if not chunk:
                        break
                    output.extend(chunk)
                except (OSError, BlockingIOError):
                    break
            if term_attr is not None:
                try:
                    termios.tcsetattr(pty_fd, termios.TCSANOW, term_attr)
                except OSError:
                    pass
            os.close(pty_fd)
        # Read final QEMU stdout message after shutdown.
        try:
            while True:
                chunk = os.read(qemu.stdout.fileno(), 8192)
                if not chunk:
                    break
                host_output.extend(chunk)
        except (OSError, BlockingIOError):
            pass
        qemu.stdout.close()
    elapsed = round(time.monotonic()-t0, 6)
    serial = bytes(output)
    host = bytes(host_output)
    (out/"serial-console.txt").write_bytes(serial)
    (out/"qemu-host-output.txt").write_bytes(host)
    acknowledged = (b"SysRq" in serial and
                    (b"Show State" in serial or b"show task" in serial.lower()
                     or b"show blocked" in serial.lower()))
    # The guest marker alone qualifies smoke, not V3 RT semantic verification.
    smoke_pass = (GUEST_MARK in serial and
                  not any(marker in serial for marker in PANIC))
    report = {
        "schema_version": 1, "test_id": "EXP76_R22_SCHED_H10_SYSRQ_PTY",
        "image_sha256": hash_bytes(image.read_bytes()),
        "initramfs_sha256": hash_bytes(initrd.read_bytes()),
        "qemu_exit_code": qemu.returncode, "timed_out": timed_out,
        "duration_seconds": elapsed, "serial_pty": pty_name,
        "sysrq_requests": attempts, "sysrq_guest_acknowledged": acknowledged,
        "serial_console_sha256": hash_bytes(serial),
        "serial_console_bytes": len(serial), "serial_console_lines": len(serial.splitlines()),
        "host_output_sha256": hash_bytes(host), "host_output_bytes": len(host),
        "guest_running": GUEST_MARK in serial,
        "kernel_panic": any(marker in serial for marker in PANIC),
        "smoke_pass": smoke_pass, "kernel_build_performed": False,
        "rt_semantics_verified": False, "rt_handoff_ready": False,
        "flash_ready": False,
    }
    (out/"sysrq-result.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report, indent=2), flush=True)
    print("EXP76_R22_SERIAL_LAST_40_LINES:", flush=True)
    print("\n".join(serial.decode(errors="replace").replace("\r","").splitlines()[-40:]), flush=True)
    # The workflow must continue to artifact upload even when the guest fails.
    # The calling step gates on report.smoke_pass explicitly.


if __name__ == "__main__":
    main()
