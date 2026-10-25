#!/usr/bin/env python3
"""EXP27.6 — consulta PASSIVA de input e IRQ no Xiaomi pipa.

Somente ADB ja autorizado. Nenhum reboot, getevent, root, input tap,
suspensao, fastboot, alteracao USB/PD, escrita em arquivo ou particao.
Nao prova que tela ou mouse funcionam: exige confirmacao fisica separada.
"""
import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

EXP25A_SIGNATURES = ("runner@runnervm8k3b6", "Mon Oct 19 02:32:14 UTC 2026")
EXP27_5_PRIOR_BOOT_DIGEST = "1346989d2e904e1b"
ALLOWED_READS = {
    ("getprop", "ro.product.device"),
    ("getprop", "ro.boot.slot_suffix"),
    ("getprop", "sys.boot_completed"),
    ("cat", "/proc/version"),
    ("cat", "/proc/sys/kernel/random/boot_id"),
    ("cat", "/proc/bus/input/devices"),
    ("cat", "/proc/interrupts"),
}

def require(check, message):
    if not check:
        raise ValueError(message)

def parse_devices(output):
    pairs = []
    for raw in output.splitlines():
        cols = raw.strip().split()
        if len(cols) >= 2 and cols[1] in ("device", "offline", "unauthorized", "recovery", "sideload"):
            pairs.append((cols[0], cols[1]))
    return pairs

def extract_input_summary(raw):
    require("N: Name=" in raw and "H: Handlers=" in raw,
            "arquivo de input ausente/ilegível")
    blocks = re.split(r"\r?\n\s*\r?\n", raw)
    names = []
    handlers = []
    for block in blocks:
        n = re.search(r'^N:\s*Name="([^"\r\n]{1,160})"', block, re.M)
        h = re.search(r"^H:\s*Handlers=([^\r\n]+)", block, re.M)
        if n:
            names.append(n.group(1).lower())
        if h:
            handlers.append(h.group(1).lower().split())
    # These are heuristics for enumeration, NOT evidence of functional touch.
    candidate_touch = any(re.search(r"nvt|nt36|novatek|touchscreen|touch panel|fts_ts|synaptics", n)
                          for n in names)
    mouse_handler = any(re.fullmatch(r"mouse[0-9]+", item)
                        for group in handlers for item in group)
    return {
        "input_devices_listed": len(names),
        "nvt_or_touch_label_present": candidate_touch,
        "mouse_handler_present": mouse_handler,
        "touch_functional": "NOT_TESTED",
        "mouse_functional": "NOT_TESTED",
    }

def parse_nvt_irq(raw):
    entries = []
    for line in raw.splitlines():
        if "NVT-ts" not in line and not re.search(r"\bnovatek\b", line, re.I):
            continue
        match = re.match(r"^\s*(\d+):\s+((?:\d+\s+)+)", line)
        if not match:
            continue
        entries.append((int(match.group(1)), sum(int(n) for n in match.group(2).split())))
    if not entries:
        return {"nvt_irq_visible": False, "nvt_irq_total": "NOT_FOUND"}
    # More than one line is ambiguous for this device.
    require(len(entries) == 1, "múltiplas IRQ NVT; evidência ambígua")
    return {"nvt_irq_visible": True, "nvt_irq_total": entries[0][1]}

def run_readonly(adb_path, serial):
    require(adb_path.is_file(), "adb.exe não encontrado")
    p = subprocess.run([str(adb_path), "devices", "-l"],
                       capture_output=True, encoding="utf-8", errors="replace",
                       text=True, timeout=12)
    require(p.returncode == 0, "falha em adb devices -l")
    all_devices = parse_devices(p.stdout)
    active = [s for s, status in all_devices if status == "device"]
    # Prevent any shell call if the host starts seeing both USB and Wi-Fi.
    require(len(active) == 1, "transportes ADB múltiplos/ausentes; nenhuma consulta ao Android")
    require(active[0] == serial, "serial ADB mudou; nenhuma consulta ao Android")
    require(re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", serial) is not None,
            "serial inválido")
    def read(*args):
        require(tuple(args) in ALLOWED_READS, "comando não está na whitelist de leitura")
        c = [str(adb_path), "-s", serial, "shell", *args]
        res = subprocess.run(c, capture_output=True, encoding="utf-8",
                             errors="replace", text=True, timeout=12)
        require(res.returncode == 0, "leitura ADB falhou: " + " ".join(args))
        require("Permission denied" not in res.stdout and "No such file" not in res.stdout,
                "campo obrigatório inacessível: " + " ".join(args))
        return res.stdout.strip()
    product = read("getprop", "ro.product.device")
    require(product == "pipa", "dispositivo não é Xiaomi pipa")
    slot = read("getprop", "ro.boot.slot_suffix")
    boot_ok = read("getprop", "sys.boot_completed")
    require(slot == "_b" and boot_ok == "1", "slot ou Android boot inesperado")
    version = read("cat", "/proc/version")
    require(all(marker in version for marker in EXP25A_SIGNATURES),
            "kernel diferente da EXP25A; coleta interrompida")
    first_boot_id = read("cat", "/proc/sys/kernel/random/boot_id")
    require(re.fullmatch(r"[0-9a-fA-F-]{36}", first_boot_id) is not None,
            "boot_id inválido")
    input_text = read("cat", "/proc/bus/input/devices")
    irq_text = read("cat", "/proc/interrupts")
    second_boot_id = read("cat", "/proc/sys/kernel/random/boot_id")
    require(first_boot_id == second_boot_id, "boot_id mudou durante coleta; INVALIDAR")
    boot_digest = hashlib.sha256(first_boot_id.encode()).hexdigest()[:16]
    inp = extract_input_summary(input_text)
    irq = parse_nvt_irq(irq_text)
    return {
        "result": "READONLY_COLLECTION_PASS",
        "product": product,
        "slot": slot,
        "kernel": "EXP25A_RECOGNIZED",
        "boot_completed": boot_ok,
        "boot_id_short_digest": boot_digest,
        "same_boot_as_exp27_5": "YES" if boot_digest == EXP27_5_PRIOR_BOOT_DIGEST else "NO_OR_DIFFERENT_BOOT",
        **inp,
        **irq,
        "usb_pd_stable": "NOT_TESTED",
        "physical_recovery": "PENDING",
        "temporary_boot_authorized": False,
        "flash_ready": False,
    }

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--adb", type=Path, default=Path("C:/platform-tools/adb.exe"))
    p.add_argument("--serial", default="6665d3e6")
    args = p.parse_args(argv)
    try:
        result = run_readonly(args.adb, args.serial)
        for name, value in result.items():
            if name not in {"flash_ready", "temporary_boot_authorized"}:
                print("EXP27_6_" + name.upper() + "=" + str(value).upper() if isinstance(value, bool)
                      else "EXP27_6_" + name.upper() + "=" + str(value))
        print("TEMP_BOOT_AUTHORIZED=false; FLASH_READY=false")
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print("EXP27_6_GATE=BLOCKED: " + str(exc), file=sys.stderr)
        print("TEMP_BOOT_AUTHORIZED=false; FLASH_READY=false", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
