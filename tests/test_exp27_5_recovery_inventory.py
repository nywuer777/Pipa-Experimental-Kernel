#!/usr/bin/env python3
"""Fixture tests for EXP27.5. Do not require a tablet or any private boot file."""
import gzip
import importlib.util
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1]/"tools/exp27-5-recovery-inventory.py"
spec = importlib.util.spec_from_file_location("exp275", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def mk_kernel(size, fill):
    data = bytearray([fill]*size)
    data[56:60] = b"ARM\x64"
    return bytes(data)

def mk_boot(kernel, rd):
    h = bytearray(m.PAGE)
    h[:8] = b"ANDROID!"
    struct.pack_into("<4I", h, 8, len(kernel), len(rd), 12345, 1580)
    struct.pack_into("<I", h, 40, 3)
    h[44:61] = b"exp27 test kernel"
    return (bytes(h) + kernel + bytes(m.round4k(len(kernel))-len(kernel))
            + rd + bytes(m.round4k(len(rd))-len(rd)))

class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.old = mk_kernel(7000, 0x31)
        new = bytearray(mk_kernel(10000, 0x44))
        new[200:208] = b"v1.10.11"
        self.new = bytes(new)
        self.ramdisk = gzip.compress(b"synthetic, not private boot content")
        self.stock = mk_boot(self.old, self.ramdisk)
        self.candidate = mk_boot(self.new, self.ramdisk)
        self.stock_path = self.root/"stock.bin"
        self.candidate_path = self.root/"candidate.bin"
        self.json_path = self.root/"candidate.json"
        self.zip_path = self.root/"exp27.zip"
        self.stock_path.write_bytes(self.stock)
        self.candidate_path.write_bytes(self.candidate)
        self.expected = {
            "result":"OFFLINE_CANDIDATE_CREATED_UNTESTED",
            "candidate_sha256":m.digest(self.candidate),
            "candidate_bytes":len(self.candidate),
            "source_exp27_image_sha256":m.digest(self.new),
            "ramdisk_identical":True,
            "cmdline_identical":True,
            "os_version_word_identical":True,
            "header_other_bytes_identical":True,
            "device_partitions_modified":False,
            "boot_tested":False,
            "temporary_boot_authorized":False,
            "flash_ready":False,
        }
        self.json_path.write_text(json.dumps(self.expected))
        with zipfile.ZipFile(self.zip_path, "w") as z:
            z.writestr(m.IMAGE_IN_ZIP, self.new)
            z.writestr(m.PROVENANCE[0], "R8152_TARGET=v1.10.11\n"+m.DRIVER_SOURCE_BLOB)
            z.writestr(m.PROVENANCE[1], "EXP24_RTL8153_LINK_PASS")
            z.writestr(m.PROVENANCE[2], "EXP25A_NVT_IRQ_GATE=PASS")
        patches = [
            mock.patch.object(m,"STOCK_BYTES",len(self.stock)),
            mock.patch.object(m,"STOCK_SHA",m.digest(self.stock)),
            mock.patch.object(m,"STOCK_KERNEL_SHA",m.digest(self.old)),
            mock.patch.object(m,"STOCK_RAMDISK_SHA",m.digest(self.ramdisk)),
            mock.patch.object(m,"CANDIDATE_BYTES",len(self.candidate)),
            mock.patch.object(m,"CANDIDATE_SHA",m.digest(self.candidate)),
            mock.patch.object(m,"NEW_IMAGE_SHA",m.digest(self.new)),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def check(self):
        return m.check_offline(self.stock_path,self.candidate_path,
                               self.json_path,self.zip_path)

    def test_complete_synthetic_identity(self):
        result = self.check()
        self.assertEqual(result["result"],"PASS")
        self.assertEqual(result["independent_header_ramdisk_kernel_check"],"PASS")
        self.assertFalse(result["temporary_boot_authorized"])
        self.assertFalse(result["flash_ready"])

    def test_kernel_byte_alteration_blocks(self):
        modified = bytearray(self.candidate)
        modified[m.PAGE + 250] ^= 1
        self.candidate_path.write_bytes(modified)
        with self.assertRaisesRegex(ValueError,"candidato inválido"):
            self.check()

    def test_ramdisk_replacement_blocks_even_if_hash_recomputed(self):
        bad = bytearray(self.candidate)
        off = m.PAGE + m.round4k(len(self.new))
        bad[off + 3] ^= 1
        self.candidate_path.write_bytes(bad)
        with mock.patch.object(m,"CANDIDATE_SHA",m.digest(bad)):
            with self.assertRaisesRegex(ValueError,"ramdisk"):
                self.check()

    def test_header_alteration_blocks_even_if_candidate_hash_recomputed(self):
        bad = bytearray(self.candidate)
        bad[68] ^= 1
        self.candidate_path.write_bytes(bad)
        with mock.patch.object(m,"CANDIDATE_SHA",m.digest(bad)):
            with self.assertRaisesRegex(ValueError,"header"):
                self.check()

    def test_report_claiming_flash_ready_blocks(self):
        report = self.expected.copy()
        report["flash_ready"] = True
        self.json_path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError,"flash_ready"):
            self.check()

    def test_report_string_fake_false_blocks(self):
        report = self.expected.copy()
        report["flash_ready"] = "False"
        self.json_path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError,"flash_ready"):
            self.check()

    def test_zip_missing_provenance_blocks(self):
        with zipfile.ZipFile(self.zip_path, "w") as z:
            z.writestr(m.IMAGE_IN_ZIP, self.new)
        with self.assertRaisesRegex(ValueError,"ZIP ausente/duplicado"):
            self.check()

    def test_duplicate_zip_entry_blocks(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.zip_path, "w") as z:
                for name in (m.IMAGE_IN_ZIP, *m.PROVENANCE):
                    z.writestr(name,self.new)
                z.writestr(m.IMAGE_IN_ZIP,self.new)
        with self.assertRaisesRegex(ValueError,"duplicado"):
            self.check()

    def test_adb_parser_one_and_two_devices(self):
        one = "List of devices attached\nusbABC device product:pipa model:23043RP34G device:pipa\n"
        self.assertEqual(len(m.parse_adb_devices(one)),1)
        two = one+"adb-abc._adb-tls-connect._tcp device product:pipa\n"
        self.assertEqual(len(m.parse_adb_devices(two)),2)

    def test_adb_multiple_transports_are_rejected_without_device_shell(self):
        adb = self.root/"adb.exe"
        adb.touch()
        stdout = ("List of devices attached\nusbABC device product:pipa\n"
                  "adb-abc._adb-tls-connect._tcp device product:pipa\n")
        fake = mock.Mock(returncode=0,stdout=stdout)
        with mock.patch.object(m.subprocess,"run",return_value=fake) as run:
            with self.assertRaisesRegex(ValueError,"ambíguo"):
                m.adb_readonly(adb,None)
            self.assertEqual(run.call_count,1)
            self.assertEqual(run.call_args.args[0][1:3],["devices","-l"])

    def test_adb_invalid_serial_rejected_without_device_shell(self):
        adb = self.root/"adb.exe"
        adb.touch()
        fake = mock.Mock(returncode=0,stdout="List of devices attached\nusbABC device product:pipa\n")
        with mock.patch.object(m.subprocess,"run",return_value=fake) as run:
            with self.assertRaisesRegex(ValueError,"identificador"):
                m.adb_readonly(adb,"usbABC; reboot")
            self.assertEqual(run.call_count,1)

    def test_adb_readonly_whitelist(self):
        adb = self.root/"adb.exe"
        adb.touch()
        samples = iter([
            mock.Mock(returncode=0,stdout="List of devices attached\nusbABC device product:pipa\n"),
            mock.Mock(returncode=0,stdout="pipa\n"),
            mock.Mock(returncode=0,stdout="_b\n"),
            mock.Mock(returncode=0,stdout="1\n"),
            mock.Mock(returncode=0,stdout="Linux version 4.19.404R (runner@test) #1 SMP PREEMPT Mon Oct 19 02:32:14 UTC 2026\n"),
            mock.Mock(returncode=0,stdout="c9c5a5af-c470-4e39-9adf-9f8f8c57e809\n"),
        ])
        with mock.patch.object(m.subprocess,"run",side_effect=list(samples)) as run:
            data = m.adb_readonly(adb,None)
            self.assertEqual(data["product"],"pipa")
            self.assertEqual(data["kernel_identity"],"EXP25A_RECOGNIZED")
            self.assertFalse(data["flash_ready"])
            self.assertEqual(run.call_count,6)
            names = [arg.args[0] for arg in run.call_args_list]
            self.assertTrue(all("reboot" not in " ".join(n) and
                                "fastboot" not in " ".join(n) and
                                "push" not in " ".join(n)
                                for n in names))

if __name__ == "__main__":
    unittest.main()
