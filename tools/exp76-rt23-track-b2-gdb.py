#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / E404 RT140 B2 QEMU GDB + raw translated-block trace / NO FLASH
"""Forensic capture for the exact B2 Image from Actions run 42629841386."""
import argparse
import bisect
import gzip
import hashlib
import importlib.util
import json
import re
import shlex
import subprocess
import time
from pathlib import Path

IMAGE_SHA = "aeffed3f051eb3f1166763fb9fdfb3a6e8c521fe90a000c9ff48019897a64c2b"
ELF_SHA = "e59f413d3b31c1e47298647303a3c1c23ba94178325c2626c233c44dd25acb0a"
CONFIG_SHA = "19294205006587189cbf79043ab81f83a0d2bfa4b4860a595f66a5df2398eac5"
RAM_SHA = "b9c25fcc2934473c45458b68b2f65f682e55cc3648e803ba64ca410fe6f70e5e"
APPEND = ("earlycon=pl011,0x09000000 console=ttyAMA0,115200 loglevel=8 "
          "ignore_loglevel printk.time=1 nokaslr panic=5 initcall_debug=1 init=/init")
OBSERVE = (
    "rcu_init", "smp_prepare_cpus", "workqueue_init",
    "kthread_create_on_node", "__kthread_create_on_node", "kthreadd",
    "kernel_init_freeable", "wait_for_completion_killable",
    "wait_for_common", "try_to_wake_up", "wake_up_new_task",
    "__schedule", "do_idle", "cpu_do_idle"
)

def load_helpers():
    module_path = Path(__file__).with_name("exp76-rt23-track-c-gdb.py")
    spec = importlib.util.spec_from_file_location("exp76_c_gdb_helpers", module_path)
    assert spec and spec.loader and module_path.is_file()
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()

def scan_and_compress(trace, dest, addresses, symbols):
    # One pass; never materialize a large QEMU trace in memory.
    pattern = re.compile(rb"Trace\s+\d+:\s+0x[0-9a-fA-F]+\s+\[([0-9a-fA-F]+/)?([0-9a-fA-F]+)")
    totals = {"tb_count": 0, "hits": {k: 0 for k in OBSERVE}, "last_tb": None}
    h = hashlib.sha256()
    with trace.open("rb") as src, gzip.open(dest, "wb", compresslevel=6) as gz:
        for line in src:
            h.update(line)
            gz.write(line)
            m = pattern.search(line)
            if not m:
                continue
            pc = int(m.group(2), 16)
            totals["tb_count"] += 1
            i = bisect.bisect_right(addresses, pc) - 1
            if i < 0:
                continue
            key = symbols[i][1]
            totals["last_tb"] = {"pc": hex(pc), "symbol": key, "offset": hex(pc-addresses[i])}
            if key in totals["hits"]:
                totals["hits"][key] += 1
    totals["raw_sha256"] = h.hexdigest()
    totals["raw_bytes"] = trace.stat().st_size
    totals["gz_sha256"] = digest(dest)
    totals["gz_bytes"] = dest.stat().st_size
    trace.unlink()
    return totals

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--initramfs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--port", type=int, default=12369)
    parser.add_argument("--interval", type=float, default=6.0)
    args = parser.parse_args()
    helper = load_helpers()
    root = args.artifact_root.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    image = root / "r23b/output/arch/arm64/boot/Image"
    elf = root / "r23b/output/vmlinux"
    smap = root / "r23b/output/System.map"
    config = root / "r23b/reports/effective.config"
    ram = args.initramfs.resolve()
    for name, path, expected in (
        ("Image", image, IMAGE_SHA), ("vmlinux", elf, ELF_SHA),
        ("config", config, CONFIG_SHA), ("initramfs", ram, RAM_SHA)
    ):
        got = digest(path)
        assert got == expected, f"{name} SHA mismatch: {got} != {expected}"
    cfg = config.read_text()
    assert "CONFIG_PREEMPT_RT_FULL=y" in cfg
    assert "# CONFIG_ENERGY_MODEL is not set" in cfg
    assert "# CONFIG_FTRACE is not set" in cfg
    all_sym = []
    for line in smap.read_text().splitlines():
        parts = line.split()
        if len(parts) >= 3:
            try:
                all_sym.append((int(parts[0], 16), parts[2]))
            except ValueError:
                pass
    all_sym.sort()
    addresses = [a for a, _ in all_sym]
    resolve = helper.lookup_symbols(smap)
    console = out / "console-full.txt"
    trace = out / "qemu-tb-exec-int.log"
    cmd = [
        "qemu-system-aarch64", "-M", "virt", "-cpu", "cortex-a72",
        "-smp", "4", "-m", "512", "-nodefaults",
        "-serial", "file:" + str(console), "-monitor", "none",
        "-display", "none", "-nic", "none", "-no-reboot",
        "-gdb", "tcp:127.0.0.1:" + str(args.port),
        "-d", "exec,int,guest_errors", "-D", str(trace),
        "-kernel", str(image), "-initrd", str(ram), "-append", APPEND
    ]
    (out / "qemu-command.txt").write_text(shlex.join(cmd)+"\n")
    start = time.monotonic()
    snapshots = []
    listener_ok = False
    qemu_unexpected_exit = False
    with (out / "qemu-stderr.txt").open("wb") as stderr:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=stderr)
        try:
            listener_ok = helper.tcp_ready(args.port)
            if listener_ok:
                for n in (1, 2):
                    time.sleep(args.interval)
                    if proc.poll() is not None:
                        qemu_unexpected_exit = True
                        break
                    snapshots.append(helper.gdb_capture(elf, args.port, out, n, resolve))
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=4)
    trace_result = (scan_and_compress(trace, out / "qemu-tb-exec-int.log.gz",
                                     addresses, all_sym)
                    if trace.exists() else None)
    raw = console.read_bytes() if console.exists() else b""
    lines = raw.decode("utf-8", "replace").splitlines()
    timestamps = [float(m.group(1)) for ln in lines
                  if (m := re.match(r"^\[\s*(\d+\.\d+)\]", ln))]
    report = {
        "schema_version": 1, "track": "B2-GDB", "source_run_id": 42629841386,
        "source_artifact_id": 13680896439, "image_sha256": digest(image),
        "vmlinux_sha256": digest(elf), "system_map_sha256": digest(smap),
        "config_sha256": digest(config), "initramfs_sha256": digest(ram),
        "qemu_guest_smp": 4, "qemu_return_code_after_harness_stop": proc.returncode,
        "stopped_by_harness": not qemu_unexpected_exit, "gdb_listener_available": listener_ok,
        "duration_seconds": round(time.monotonic()-start, 3),
        "console_sha256": hashlib.sha256(raw).hexdigest(), "console_bytes": len(raw),
        "console_lines": len(lines), "console_last_20": lines[-20:],
        "reached_ms": round(max(timestamps)*1000, 3) if timestamps else None,
        "guest_running": b"EXP76_QEMU_RT_SMOKE=GUEST_RUNNING" in raw,
        "gdb_snapshots": snapshots, "qemu_tb_trace": trace_result,
        "build_performed": False, "flash_ready": False,
        "caveat": "GDB threads represent vCPUs, not kernel tasks. Last TB/idle PC is not proof of root cause."
    }
    (out / "exp76-track-b2-gdb.json").write_text(json.dumps(report, indent=2)+"\n")
    print("EXP76_B2_GDB", json.dumps(report, indent=2), flush=True)

if __name__ == "__main__":
    main()
