#!/usr/bin/env python3
# Python 3 / Ubuntu24 GitHub Actions / pinned EXP76 R30 V3 QEMU AArch64 load_module GDB return probe / NO FLASH
"""Identify -ENOEXEC return path from original E404 RT V3 module loader without rebuilding."""
import argparse
import hashlib
import json
import re
import shlex
import socket
import subprocess
import time
from pathlib import Path

PIN = {
    "image": "e676fd51e21741c0616025ffdd8ed3cd81ea88c4f27dfc63d2c5cc47b689e5c8",
    "vmlinux": "84b9254ba1ebc9da2465f58ae20e94488b79bc30b8e1467274bbd62cb8e8ec84",
    "diagnostic_initrd": "df3d0ab49af3b34e8cef43cefca41996107a5a11fd66769e0ba5184c872d864d",
}
APPEND = ("earlycon=pl011,0x09000000 console=ttyAMA0,115200 "
          "loglevel=8 ignore_loglevel printk.time=1 nokaslr panic=5 initcall_debug=1 init=/init")
LOAD_MODULE = "0xffffff801010c790"

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--build", type=Path, required=True)
    p.add_argument("--diag", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--port", type=int, default=12379)
    opts = p.parse_args()
    root = opts.build.resolve()
    diag = opts.diag.resolve()
    out = opts.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    image = root / "r23b/output/arch/arm64/boot/Image"
    elf = root / "r23b/output/vmlinux"
    initrd = diag / "diagnostic-initramfs.cpio.gz"
    for k, path in [("image", image), ("vmlinux", elf), ("diagnostic_initrd", initrd)]:
        assert path.is_file() and sha(path) == PIN[k], f"PINNED_{k}_CHANGED"
    console = out / "console-full.txt"
    err = out / "qemu-stderr.txt"
    cmd = [
        "qemu-system-aarch64", "-M", "virt", "-cpu", "cortex-a72",
        "-smp", "4", "-m", "512", "-nodefaults",
        "-serial", "file:" + str(console), "-monitor", "none",
        "-display", "none", "-nic", "none", "-no-reboot",
        "-S", "-gdb", f"tcp:127.0.0.1:{opts.port}",
        "-kernel", str(image), "-initrd", str(initrd), "-append", APPEND
    ]
    (out / "qemu-command.txt").write_text(shlex.join(cmd)+"\n")
    script = out / "load-module.gdb"
    script.write_text(
        "set confirm off\n"
        "set pagination off\n"
        "set architecture aarch64\n"
        f"file {elf}\n"
        f"target remote 127.0.0.1:{opts.port}\n"
        f"hbreak *{LOAD_MODULE}\n"
        "continue\n"
        "printf \"EXP76_GDB_LOAD_MODULE_ENTRY\\n\"\n"
        "info registers x0 x1 x2 x29 x30 pc\n"
        "bt 12\n"
        "finish\n"
        "printf \"EXP76_GDB_LOAD_MODULE_RETURN\\n\"\n"
        "info registers x0 x29 x30 pc\n"
        "bt 12\n"
        "detach\n"
        "quit\n"
    )
    t0 = time.monotonic()
    with err.open("wb") as err_f:
        qemu = subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=err_f)
        gdb_status, gdb_timed = None, False
        try:
            ok = False
            for _ in range(60):
                try:
                    with socket.create_connection(("127.0.0.1", opts.port), timeout=0.2):
                        ok = True
                        break
                except OSError:
                    time.sleep(0.1)
            assert ok, "GDB_REMOTE_LISTENER_MISSING"
            gdb_cmd = ["gdb-multiarch", "-q", "-nx", "-batch", "-x", str(script)]
            (out / "gdb-command.txt").write_text(shlex.join(gdb_cmd)+"\n")
            try:
                gdb = subprocess.run(gdb_cmd, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, timeout=28)
                gdb_out, gdb_status = gdb.stdout, gdb.returncode
            except subprocess.TimeoutExpired as e:
                gdb_out = e.stdout or b""
                gdb_status, gdb_timed = 124, True
            (out / "gdb-raw.txt").write_bytes(gdb_out)
            try:
                qemu.wait(timeout=12)
            except subprocess.TimeoutExpired:
                pass
        finally:
            if qemu.poll() is None:
                qemu.terminate()
                try: qemu.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    qemu.kill()
                    qemu.wait(timeout=4)
    gdb_text = (out / "gdb-raw.txt").read_text(errors="replace")
    text = console.read_text(errors="replace") if console.exists() else ""
    report = {
        "schema_version": 1,
        "source_kernel_run_id": 43257368054,
        "source_direct_insmod_run_id": 43259987170,
        "image_sha256": PIN["image"], "vmlinux_sha256": PIN["vmlinux"],
        "diagnostic_initramfs_sha256": PIN["diagnostic_initrd"],
        "gdb_status": gdb_status, "gdb_timed_out": gdb_timed,
        "gdb_sha256": sha(out / "gdb-raw.txt"),
        "gdb_bytes": (out / "gdb-raw.txt").stat().st_size,
        "entry_breakpoint_hit": "EXP76_GDB_LOAD_MODULE_ENTRY" in gdb_text,
        "return_breakpoint_hit": "EXP76_GDB_LOAD_MODULE_RETURN" in gdb_text,
        "gdb_last_100": gdb_text.splitlines()[-100:],
        "qemu_return_code": qemu.returncode,
        "duration_seconds": round(time.monotonic()-t0, 3),
        "guest_running": "EXP76_V3_DIAG_GUEST_RUNNING" in text,
        "console_sha256": sha(console) if console.exists() else None,
        "console_last_30": text.splitlines()[-30:],
        "build_performed": False, "module_modified": False,
        "kernel_modified": False, "rt_semantics_verified": "NOT_VERIFIED",
        "flash_ready": False
    }
    (out / "module-loader-gdb.json").write_text(json.dumps(report, indent=2)+"\n")
    print("EXP76_R30_MODULE_LOADER_GDB", json.dumps(report, indent=2), flush=True)
    assert (out / "gdb-raw.txt").stat().st_size > 50, "NO_GDB_EVIDENCE"

if __name__ == "__main__":
    main()
