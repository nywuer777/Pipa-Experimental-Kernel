#!/usr/bin/env python3
# Python 3 / Ubuntu24 GitHub Actions / R30 V3 pinned RT Image + module direct-insmod QEMU forensics / NO FLASH
"""Reuse exact V3 Image and module; replace only guest init script to expose insmod progress."""
import argparse
import bisect
import gzip
import hashlib
import json
import re
import shlex
import subprocess
import tempfile
from pathlib import Path

EXPECTED = {
    "image": "e676fd51e21741c0616025ffdd8ed3cd81ea88c4f27dfc63d2c5cc47b689e5c8",
    "vmlinux": "84b9254ba1ebc9da2465f58ae20e94488b79bc30b8e1467274bbd62cb8e8ec84",
    "config": "0dfb1b876487a55938e5fdaba9bcb9473e161e30ddef744a1db2a1d0827a622d",
    "module": "0526972e841a0da8980270a82018bf4ab1d90078f65cba4ce6f1134e34e842d8",
    "initramfs": "71d95c3384c9b20c833aa32b682a68b71483a007cc9b8378032f47fe2624a685",
}
INIT = """#!/bin/sh
export PATH=/bin
mkdir -p /proc /sys /tmp /dev
mount -t proc proc /proc
mount -t sysfs sysfs /sys
echo EXP76_V3_DIAG_GUEST_RUNNING
echo EXP76_V3_DIAG_INSMOD_BEGIN
ls -l /probe/rt.ko
( insmod /probe/rt.ko noop_mode=0; echo "EXP76_V3_DIAG_INSMOD_RC=$?" ) &
child=$!
echo "EXP76_V3_DIAG_INSMOD_PID=$child"
sleep 2
echo EXP76_V3_DIAG_AFTER_2S
cat /proc/modules
dmesg | tail -n 60
if [ -w /proc/sysrq-trigger ]; then
  echo t > /proc/sysrq-trigger
  echo EXP76_V3_DIAG_SYSRQ_T
fi
sleep 3
echo EXP76_V3_DIAG_AFTER_5S
cat /proc/modules
dmesg | tail -n 80
echo EXP76_V3_DIAG_END
poweroff -f
"""
APPEND = (
    "earlycon=pl011,0x09000000 console=ttyAMA0,115200 "
    "loglevel=8 ignore_loglevel printk.time=1 nokaslr "
    "panic=5 initcall_debug=1 init=/init"
)

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()

def run(command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)

def symbolize(raw, smap):
    syms = []
    for line in smap.read_text(errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 3:
            try: syms.append((int(parts[0], 16), parts[2]))
            except ValueError: pass
    syms.sort()
    keys = [x[0] for x in syms]
    hits = {}
    for m in re.finditer(r"0xffffff[0-9a-fA-F]{10,12}", raw):
        addr = int(m.group(0), 16)
        i = bisect.bisect_right(keys, addr) - 1
        if i >= 0 and addr - syms[i][0] < 0x2000:
            ident = f"{syms[i][1]}+0x{addr - syms[i][0]:x}"
            hits[ident] = hits.get(ident, 0) + 1
    return [{"symbol": s, "occurrences": n} for s, n in sorted(hits.items(), key=lambda x: -x[1])[:60]]

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    base = a.input.resolve()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    inputs = {
        "image": base / "r23b/output/arch/arm64/boot/Image",
        "vmlinux": base / "r23b/output/vmlinux",
        "config": base / "r23b/reports/effective.config",
        "module": base / "tests/exp76-rt-spin-sleep/exp76_rt_spin_sleep.ko",
        "initramfs": base / "r30/reports/v3/v3-initramfs.cpio.gz",
    }
    for key, path in inputs.items():
        assert path.is_file(), "MISSING_" + key
        actual = sha(path)
        assert actual == EXPECTED[key], f"{key}_HASH_CHANGED {actual}"
    assert "CONFIG_PREEMPT_RT_FULL=y" in inputs["config"].read_text()
    initrd = out / "diagnostic-initramfs.cpio.gz"
    with tempfile.TemporaryDirectory(prefix="exp76-v3-") as t:
        root = Path(t)
        with inputs["initramfs"].open("rb") as fd:
            unzip = subprocess.Popen(["gzip", "-dc"], stdin=fd, stdout=subprocess.PIPE)
            assert unzip.stdout
            run(["cpio", "-id", "--no-absolute-filenames", "--quiet"], stdin=unzip.stdout,
                cwd=root, timeout=30)
            unzip.stdout.close()
            assert unzip.wait(timeout=5) == 0
        assert (root / "probe/rt.ko").is_file()
        assert sha(root / "probe/rt.ko") == EXPECTED["module"]
        (root / "init").write_text(INIT)
        (root / "init").chmod(0o755)
        for app in ("ls", "cat", "dmesg", "insmod", "sleep", "mount",
                    "mkdir", "tail", "poweroff", "echo", "ps"):
            link = root / "bin" / app
            if not link.exists() and not link.is_symlink():
                link.symlink_to("busybox")
        finder = subprocess.Popen(["find", ".", "-print0"], cwd=root, stdout=subprocess.PIPE)
        assert finder.stdout
        packed = subprocess.Popen(["cpio", "--null", "-o", "--format=newc", "--quiet"],
                                  stdin=finder.stdout, cwd=root, stdout=subprocess.PIPE)
        finder.stdout.close()
        with initrd.open("wb") as f:
            assert packed.stdout
            comp = subprocess.Popen(["gzip", "-9"], stdin=packed.stdout, stdout=f)
            packed.stdout.close()
            assert comp.wait(timeout=30) == 0
        assert packed.wait(timeout=30) == 0 and finder.wait(timeout=5) == 0
    console = out / "console-full.txt"
    cmd = ["qemu-system-aarch64", "-M", "virt", "-cpu", "cortex-a72",
           "-smp", "4", "-m", "512", "-nodefaults", "-serial", "stdio",
           "-monitor", "none", "-display", "none", "-nic", "none",
           "-no-reboot", "-kernel", str(inputs["image"]), "-initrd",
           str(initrd), "-append", APPEND]
    (out / "qemu-command.txt").write_text(shlex.join(cmd) + "\n")
    with console.open("wb") as f:
        try:
            q = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, timeout=30)
            ret, timed = q.returncode, False
        except subprocess.TimeoutExpired:
            ret, timed = 124, True
    raw = console.read_text(errors="replace")
    timestamps = [float(x) * 1000 for x in re.findall(r"(?m)^\[\s*(\d+\.\d+)\]", raw)]
    report = {
        "schema_version": 1, "source_run_id": 43257368054,
        "source_artifact_id": 13961873316, "inputs_sha256": EXPECTED,
        "diagnostic_initramfs_sha256": sha(initrd),
        "console_sha256": sha(console), "console_bytes": console.stat().st_size,
        "console_lines": len(raw.splitlines()), "kernel_reached_ms": round(max(timestamps), 3) if timestamps else None,
        "qemu_exit_code": ret, "timed_out": timed,
        "guest_running": "EXP76_V3_DIAG_GUEST_RUNNING" in raw,
        "insmod_rc_marker": re.findall(r"EXP76_V3_DIAG_INSMOD_RC=(\d+)", raw),
        "module_messages": [line for line in raw.splitlines() if
                            "EXP76_RT_SPIN_SLEEP" in line or "EXP76_V3_DIAG" in line][:90],
        "symbolized_console_addresses": symbolize(raw, base / "r23b/output/System.map"),
        "build_performed": False, "kernel_modified": False,
        "module_modified": False, "rt_semantics_verified": "NOT_VERIFIED_DIAGNOSTIC",
        "flash_ready": False
    }
    (out / "pinned-v3-insmod-diagnostic.json").write_text(json.dumps(report, indent=2) + "\n")
    (out / "sha256sum.txt").write_text(
        f"{sha(initrd)}  {initrd.name}\n{sha(console)}  {console.name}\n"
    )
    print("EXP76_V3_PINNED_DIAG", json.dumps(report, indent=2), flush=True)
    assert report["guest_running"], "PRESERVED_IMAGE_DID_NOT_START_GUEST"

if __name__ == "__main__":
    main()
