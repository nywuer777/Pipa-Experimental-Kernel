#!/usr/bin/env python3
"""EXP27.5 — auditar arquivos de boot e opcionalmente consultar Android em leitura.

SEM flash/boot/reboot/ADB connect/root/rebind. Sem escrita no tablet.
Por padrão NAO executa ADB nem escreve relatórios/arquivos locais.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

PAGE = 4096
STOCK_SHA = "202aaaf67fe5c0a963965c4e29f67866b509916e0bdff15dde38ef55b3d321e7"
STOCK_BYTES = 32206848
STOCK_KERNEL_SHA = "a72fff8f285419f6f45c7e3d1c43fb1fe5958878b5ce53ab9291148ad9b7acdd"
STOCK_RAMDISK_SHA = "d2a62b4ca809b28ddd0ae25388af051c874fbacfecb6b965243b7d6b81465ee9"
CANDIDATE_SHA = "df9eb41441770035849e95a6e54ccc110357d5c171a06758cc2df60a192a01d7"
CANDIDATE_BYTES = 32411648
NEW_IMAGE_SHA = "a14b536b471c97db877482afe97bcbeb97daa74ebc48a3a344d90ead57d56967"
DRIVER_SOURCE_BLOB = "92b51c4c46f57b660f3053804ba74f6df9e71c76"
IMAGE_IN_ZIP = "exp06-work/out/arch/arm64/boot/Image"
PROVENANCE = ("exp27-r8152-stage-gate.txt",
              "exp24-rtl8153-link-gate.txt",
              "exp25-touch-final-gate.log")

def digest(b):
    return hashlib.sha256(b).hexdigest()

def need(condition, message):
    if not condition:
        raise ValueError(message)

def round4k(n):
    return (n + PAGE - 1) // PAGE * PAGE

def parse_boot(data):
    import struct
    need(len(data) >= PAGE and data[:8] == b"ANDROID!", "boot magic inválido")
    ksize, rsize, osword, hsize = struct.unpack_from("<4I", data, 8)
    version = struct.unpack_from("<I", data, 40)[0]
    need(version == 3 and hsize == 1580, "Boot V3/1580 não confirmado")
    need(ksize > 4096 and rsize > 8, "kernel/ramdisk com tamanho inválido")
    end = PAGE + round4k(ksize) + round4k(rsize)
    need(end == len(data), "tamanho compacto Boot V3 inesperado")
    kstart, rstart = PAGE, PAGE + round4k(ksize)
    kernel = data[kstart:kstart + ksize]
    ramdisk = data[rstart:rstart + rsize]
    need(kernel[56:60] == b"ARM\x64", "assinatura ARM64 inválida")
    need(ramdisk[:2] == b"\x1f\x8b", "ramdisk não é gzip")
    need(not any(data[1580:PAGE]), "padding do cabeçalho não canônico")
    need(not any(data[kstart+ksize:rstart]), "padding do kernel não canônico")
    need(not any(data[rstart+rsize:end]), "padding do ramdisk não canônico")
    return {"header": data[:PAGE], "kernel": kernel, "ramdisk": ramdisk,
            "osword": osword, "kernel_size": ksize, "ramdisk_size": rsize}

def read_ci(zip_path):
    need(zip_path.is_file(), "ZIP do Actions EXP27.1 não encontrado")
    need(zip_path.stat().st_size <= 160*1024*1024, "ZIP CI muito grande")
    with zipfile.ZipFile(zip_path) as z:
        names = (IMAGE_IN_ZIP, *PROVENANCE)
        result = {}
        for name in names:
            entries = [i for i in z.infolist() if i.filename == name and not i.is_dir()]
            need(len(entries) == 1, "ZIP ausente/duplicado: " + name)
            need(entries[0].file_size <= 70*1024*1024, "arquivo ZIP maior que o limite: "+name)
            result[name] = z.read(entries[0])
    img = result[IMAGE_IN_ZIP]
    need(digest(img) == NEW_IMAGE_SHA, "kernel CI não corresponde ao SHA-256 EXP27.1")
    need(img[56:60] == b"ARM\x64" and b"v1.10.11" in img,
         "Image CI não contém identificação ARM64/r8152")
    need(b"R8152_TARGET=v1.10.11" in result[PROVENANCE[0]] and
         DRIVER_SOURCE_BLOB.encode() in result[PROVENANCE[0]],
         "origem do driver não confere")
    need(b"EXP24_RTL8153_LINK_PASS" in result[PROVENANCE[1]],
         "gate RTL8153 não consta no ZIP")
    need(b"EXP25A_NVT_IRQ_GATE=PASS" in result[PROVENANCE[2]],
         "gate Novatek não consta no ZIP")
    return img

def check_offline(stock_path, candidate_path, json_path, zip_path):
    for label, path in (("controle stock",stock_path), ("candidato EXP27.4",candidate_path),
                        ("JSON EXP27.4",json_path)):
        need(path.is_file(), label + " não encontrado: " + str(path))
    stock = stock_path.read_bytes()
    candidate = candidate_path.read_bytes()
    need(len(stock) == STOCK_BYTES and digest(stock) == STOCK_SHA,
         "tamanho/hash do stock inválido")
    need(len(candidate) == CANDIDATE_BYTES and digest(candidate) == CANDIDATE_SHA,
         "tamanho/hash do candidato inválido")
    old, new = parse_boot(stock), parse_boot(candidate)
    need(digest(old["kernel"]) == STOCK_KERNEL_SHA, "kernel original modificado")
    need(digest(old["ramdisk"]) == STOCK_RAMDISK_SHA, "ramdisk original modificado")
    need(old["header"][:8] + old["header"][12:] ==
         new["header"][:8] + new["header"][12:],
         "header não preservado fora do campo kernel_size")
    need(old["ramdisk"] == new["ramdisk"],
         "ramdisk difere do controle original")
    need(old["osword"] == new["osword"], "campo os_version difere")
    need(new["kernel"] == read_ci(zip_path), "kernel do candidato difere da Image CI")
    need(digest(new["kernel"]) == NEW_IMAGE_SHA, "hash do kernel interno inválido")
    try:
        report = json.loads(json_path.read_text(encoding="utf-8-sig"))
    except (UnicodeError, ValueError) as err:
        raise ValueError("JSON da EXP27.4 inválido") from err
    expected = {
        "result": "OFFLINE_CANDIDATE_CREATED_UNTESTED",
        "candidate_sha256": CANDIDATE_SHA,
        "candidate_bytes": CANDIDATE_BYTES,
        "source_exp27_image_sha256": NEW_IMAGE_SHA,
        "ramdisk_identical": True,
        "cmdline_identical": True,
        "os_version_word_identical": True,
        "header_other_bytes_identical": True,
        "device_partitions_modified": False,
        "boot_tested": False,
        "temporary_boot_authorized": False,
        "flash_ready": False,
    }
    for field, value in expected.items():
        need(type(report.get(field)) is type(value) and report[field] == value,
             "relatório inconsistente: " + field)
    return {
        "result": "PASS",
        "candidate_sha256": CANDIDATE_SHA,
        "candidate_bytes": len(candidate),
        "kernel_sha256": NEW_IMAGE_SHA,
        "independent_header_ramdisk_kernel_check": "PASS",
        "source_ci_checked": True,
        "android_observed": False,
        "physical_recovery_verified": False,
        "temporary_boot_authorized": False,
        "flash_ready": False,
    }

def parse_adb_devices(output):
    devices = []
    for ln in output.splitlines():
        ln = ln.strip()
        if not ln or ln.lower().startswith("list of devices") or ln.startswith("*"):
            continue
        cols = ln.split()
        if len(cols) >= 2:
            devices.append((cols[0], cols[1], cols[2:]))
    return devices

def adb_readonly(adb_exe, serial):
    need(adb_exe.is_file(), "adb.exe não encontrado; coleta opcional cancelada")
    proc = subprocess.run([str(adb_exe), "devices", "-l"], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=12)
    need(proc.returncode == 0, "não foi possível enumerar ADB")
    entries = [x for x in parse_adb_devices(proc.stdout) if x[1] == "device"]
    if serial:
        need(re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", serial) is not None,
             "identificador de transporte inválido")
        entries = [x for x in entries if x[0] == serial]
    need(len(entries) == 1,
         "ADB ambíguo/ausente: deve haver 1 transporte autorizado; "
         "nenhum comando enviado ao dispositivo")
    target = entries[0][0]
    def read(*args):
        call = [str(adb_exe), "-s", target, "shell", *args]
        x = subprocess.run(call, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=12)
        need(x.returncode == 0, "consulta ADB falhou; não continuar")
        return x.stdout.strip()

    # Somente chamadas de consulta: sem su, reboot, connect, escrita sysfs ou drivers.
    ident = read("getprop", "ro.product.device")
    need(ident == "pipa", "dispositivo não é pipa; abortado")
    slot = read("getprop", "ro.boot.slot_suffix")
    completed = read("getprop", "sys.boot_completed")
    version = read("cat", "/proc/version")
    boot_id = read("cat", "/proc/sys/kernel/random/boot_id")
    need(re.fullmatch(r"[0-9a-fA-F-]{36}", boot_id) is not None,
         "boot_id ausente/inválido")
    runtime = "NOT_EXP27"
    if "runner@" in version and "Mon Oct 19 02:32:14 UTC 2026" in version:
        runtime = "EXP25A_RECOGNIZED"
    elif "build-user@build-host" in version:
        runtime = "PERSISTENT_E404_RECOGNIZED"
    # Não inspeciona raw serial, boot_id ou cmdline no output.
    need(slot in ("_b", "b") and completed == "1",
         "slot inesperado ou Android ainda não inicializado")
    return {
        "adb_transport": "USB" if not any(("._adb-tls" in target, target.startswith("adb-"),
                                           ":" in target)) else "WIFI_OR_NETWORK",
        "product": ident,
        "slot": slot,
        "boot_completed": completed,
        "kernel_identity": runtime,
        "boot_id_short_digest": digest(boot_id.encode())[:16],
        "touchscreen_functional": "NOT_TESTED",
        "usb_pd_stable": "NOT_TESTED",
        "recovery_verified": False,
        "temporary_boot_authorized": False,
        "flash_ready": False,
    }

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    d = Path("C:/platform-tools")
    p.add_argument("--stock", type=Path, default=d/"pipa_preflight/boot_b-stock-compact-control.img")
    p.add_argument("--candidate", type=Path, default=d/"EXP27.4-boot-prep/EXP27.4-RTL8153-NOT-FOR-FLASH.candidate.bin")
    p.add_argument("--audit-json", type=Path, default=d/"EXP27.4-boot-prep/EXP27.4-offline-audit.json")
    p.add_argument("--ci-zip", type=Path, default=Path.home()/"Downloads/pipa-exp27-r8152-v11011-clang21-3.zip")
    p.add_argument("--observe-android", action="store_true", help="ADB leitura explícita; por padrão SEM ADB")
    p.add_argument("--adb", type=Path, default=d/"adb.exe")
    p.add_argument("--serial", type=str, default=None,
                   help="Somente se houver mais de um transporte autorizado no PC")
    a = p.parse_args(argv)
    try:
        need(not a.serial or a.observe_android, "--serial requer --observe-android")
        r = check_offline(a.stock, a.candidate, a.audit_json, a.ci_zip)
        print("EXP27.5_OFFLINE_INDEPENDENT_CHECK=PASS")
        print("BOOT_V3_HEADERS_AND_RAMDISK=PASS")
        print("CANDIDATE_IMAGE_CI_BYTE_MATCH=PASS")
        print("EXP27.4_CANDIDATE_SHA256=" + r["candidate_sha256"])
        if a.observe_android:
            state = adb_readonly(a.adb, a.serial)
            print("EXP27.5_ANDROID_READONLY=PASS")
            for k, v in state.items():
                if k not in ("recovery_verified","temporary_boot_authorized","flash_ready"):
                    print(k.upper() + "=" + str(v))
        else:
            print("EXP27.5_ANDROID_READONLY=NOT_REQUESTED")
        print("PHYSICAL_RECOVERY=PENDING")
        print("TEMP_BOOT_AUTHORIZED=false; FLASH_READY=false")
        return 0
    except (OSError, ValueError, zipfile.BadZipFile,
            subprocess.TimeoutExpired) as exc:
        print("EXP27.5_GATE=BLOCKED: " + str(exc), file=sys.stderr)
        print("TEMP_BOOT_AUTHORIZED=false; FLASH_READY=false", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
