#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 GitHub Actions / pinned E404 RT Image CPU stack forensics, no rebuild, no flash
"""Take two raw CPU GDB snapshots of the original pre-init RT Image in QEMU."""
import argparse
import bisect
import hashlib
import json
import re
import shlex
import socket
import subprocess
import time
from pathlib import Path

IMAGE_SHA = "812d46e04131cc1ded7dd26b13728f3d8834ff240d533cac80172dd070e6e907"
ELF_SHA = "933ad5ea6857e79a22f72914c08c3f12b97771728fd16a33609897c4fc3d77c6"
APPEND = ("earlycon=pl011,0x09000000 console=ttyAMA0,115200 loglevel=8 "
          "ignore_loglevel printk.time=1 nokaslr panic=5 initcall_debug=1 init=/init")

def hashfile(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()

def lookup_symbols(path):
    values = []
    for line in path.read_text(errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 3:
            try:
                values.append((int(parts[0], 16), parts[2]))
            except ValueError:
                continue
    values.sort()
    keys = [v[0] for v in values]
    def symbol(pc):
        i = bisect.bisect_right(keys, pc) - 1
        if i < 0:
            return None
        return {"name": values[i][1], "offset": hex(pc - values[i][0])}
    return symbol

def tcp_ready(port):
    for _ in range(60):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return True
        except OSError:
            time.sleep(0.15)
    return False

def gdb_capture(elf, port, output, index, resolve):
    cmd = ["gdb-multiarch", "-q", "-nx", "-batch"]
    for ex in ("set confirm off", "set pagination off", "set architecture aarch64",
               "file " + str(elf), "target remote 127.0.0.1:" + str(port),
               "info threads", "thread apply all info registers",
               "thread apply all bt 24", "detach", "quit"):
        cmd.extend(["-ex", ex])
    (output / ("gdb-command-%d.txt" % index)).write_text(shlex.join(cmd) + "\n")
    t0 = time.monotonic()
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=25)
        code, data, timed = result.returncode, result.stdout, False
    except subprocess.TimeoutExpired as exc:
        code, data, timed = 124, exc.stdout or b"", True
    dest = output / ("gdb-snapshot-%d.txt" % index)
    dest.write_bytes(data)
    text = data.decode("utf-8", "replace")
    pcs = []
    for match in re.finditer(r"(?m)^\s*pc\s+0x([0-9a-fA-F]+)\b", text):
        pc = int(match.group(1), 16)
        pcs.append({"pc": hex(pc), "symbol": resolve(pc)})
    return {"snapshot": index, "exit_code": code, "timed_out": timed,
            "duration_seconds": round(time.monotonic()-t0, 4),
            "raw_file": dest.name, "raw_sha256": hashfile(dest),
            "raw_bytes": len(data), "cpu_pcs": pcs,
            "frame_lines": len(re.findall(r"(?m)^#\d+\s+", text)),
            "gdb_errors": [line[:220] for line in text.splitlines()
                           if ("Error" in line or "warning:" in line)][:12]}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--port", type=int, default=12367)
    parser.add_argument("--interval", type=float, default=5.0)
    opts = parser.parse_args()
    out, root = opts.out.resolve(), opts.root.resolve()
    out.mkdir(parents=True, exist_ok=True)
    image = root / "outputs/qemu-rt/arch/arm64/boot/Image"
    elf = root / "outputs/qemu-rt/vmlinux"
    system_map = root / "outputs/qemu-rt/System.map"
    config = root / "outputs/qemu-rt/.config"
    initrd = root / "smoke-initramfs.cpio.gz"
    assert hashfile(image) == IMAGE_SHA, "pinned Image changed"
    assert hashfile(elf) == ELF_SHA, "pinned vmlinux changed"
    assert "# CONFIG_FTRACE is not set" in config.read_text()
    resolve = lookup_symbols(system_map)
    console = out / "console-rt.txt"
    cmd = ["qemu-system-aarch64", "-M", "virt", "-cpu", "cortex-a72",
           "-smp", "4", "-m", "512", "-nodefaults",
           "-serial", "file:" + str(console), "-monitor", "none",
           "-display", "none", "-nic", "none", "-no-reboot",
           "-gdb", "tcp:127.0.0.1:" + str(opts.port),
           "-kernel", str(image), "-initrd", str(initrd), "-append", APPEND]
    (out / "qemu-command.txt").write_text(shlex.join(cmd) + "\n")
    start = time.monotonic()
    with (out / "qemu-stderr.txt").open("wb") as err:
        process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                   stderr=err, stdin=subprocess.DEVNULL)
        snapshots = []
        problem = None
        try:
            if not tcp_ready(opts.port):
                problem = "QEMU_GDB_LISTENER_UNAVAILABLE"
            else:
                for idx in (1, 2):
                    time.sleep(opts.interval)
                    if process.poll() is not None:
                        problem = "QEMU_EXITED_BEFORE_SNAPSHOT"
                        break
                    snapshots.append(gdb_capture(elf, opts.port, out, idx, resolve))
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=4)
    data = console.read_bytes() if console.exists() else b""
    lines = data.decode("utf-8", "replace").splitlines()
    points = [float(n) for line in lines
              for n in re.findall(r"^\[\s*(\d+\.\d+)\]", line)]
    report = {
        "schema_version": 1, "track": "C-GDB", "source_run_id": 42250522391,
        "image_sha256": hashfile(image), "vmlinux_sha256": hashfile(elf),
        "system_map_sha256": hashfile(system_map),
        "config_sha256": hashfile(config), "initramfs_sha256": hashfile(initrd),
        "qemu_guest_smp": 4, "qemu_exit_code": process.returncode,
        "duration_seconds": round(time.monotonic()-start, 4),
        "console_sha256": hashlib.sha256(data).hexdigest(),
        "console_bytes": len(data), "console_lines": len(lines),
        "console_last_20": lines[-20:],
        "reached_ms": round(1000*max(points), 3) if points else None,
        "guest_running": b"EXP76_QEMU_RT_SMOKE=GUEST_RUNNING" in data,
        "gdb_snapshots": snapshots, "error": problem,
        "ftrace_available": False, "build_performed": False,
        "flash_ready": False,
        "interpretation": "GDB threads are virtual CPUs, not kernel task IDs; backtrace completeness is uncertain."
    }
    (out / "exp76-track-c-gdb.json").write_text(json.dumps(report, indent=2)+"\n")
    print("EXP76_C_GDB", json.dumps(report, indent=2), flush=True)

if __name__ == "__main__":
    main()
