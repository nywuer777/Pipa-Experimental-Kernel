#!/usr/bin/env python3
"""EXP27.4 synthetic Boot V3 repack tests. No real boot backups or device access."""
import gzip
import importlib.util
import io
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools/exp27-4-build-offline.py"
spec = importlib.util.spec_from_file_location("exp27_4", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def kernel(size, marker):
    b = bytearray(marker * size)
    b[56:60] = b"ARM\x64"
    return bytes(b)

def synthetic():
    old = kernel(1100, b"\x01")
    new = kernel(3500, b"\x02")
    rd = gzip.compress(b"realistic enough minimal generic ramdisk")
    hdr = bytearray(m.PAGE)
    hdr[:8] = b"ANDROID!"
    struct.pack_into("<4I", hdr, 8, len(old), len(rd), 0x12345678, m.BOOT_HEADER_SIZE)
    struct.pack_into("<I", hdr, 40, 3)
    hdr[44:55] = b"hello world"
    stock = bytes(hdr) + old + bytes(m.align(len(old)) - len(old)) + \
        rd + bytes(m.align(len(rd)) - len(rd))
    return stock, old, new, rd

class TestBootV3(unittest.TestCase):
    def test_repack_and_precise_invariants(self):
        stock, old, new, rd = synthetic()
        cand, report = m.build(
            stock, new,
            expected_stock_sha=m.sha(stock),
            expected_old_kernel_sha=m.sha(old),
            expected_ramdisk_sha=m.sha(rd),
            expected_new_sha=m.sha(new),
            pinned=False,
        )
        self.assertEqual(report["result"], "OFFLINE_CANDIDATE_CREATED_UNTESTED")
        self.assertFalse(report["temporary_boot_authorized"])
        self.assertFalse(report["flash_ready"])
        self.assertEqual(cand[:8], b"ANDROID!")
        self.assertEqual(cand[:8] + cand[12:m.PAGE],
                         stock[:8] + stock[12:m.PAGE])
        self.assertEqual(struct.unpack_from("<I", cand, 8)[0], len(new))
        self.assertEqual(cand[m.PAGE:m.PAGE+len(new)], new)
        rd_off = m.PAGE + m.align(len(new))
        self.assertEqual(cand[rd_off:rd_off+len(rd)], rd)
        self.assertEqual(len(cand), m.PAGE + m.align(len(new)) + m.align(len(rd)))

    def test_reject_modified_control(self):
        stock, old, new, rd = synthetic()
        with self.assertRaises(ValueError):
            m.build(stock[:-1] + b"\x01", new,
                    expected_stock_sha=m.sha(stock),
                    expected_old_kernel_sha=m.sha(old),
                    expected_ramdisk_sha=m.sha(rd),
                    expected_new_sha=m.sha(new), pinned=False)

    def test_reject_wrong_replacement_kernel(self):
        stock, old, new, rd = synthetic()
        with self.assertRaises(ValueError):
            m.build(stock, new + b"x",
                    expected_stock_sha=m.sha(stock),
                    expected_old_kernel_sha=m.sha(old),
                    expected_ramdisk_sha=m.sha(rd),
                    expected_new_sha=m.sha(new), pinned=False)

    def test_reject_bad_header_version(self):
        stock, old, new, rd = synthetic()
        bad = bytearray(stock)
        struct.pack_into("<I", bad, 40, 4)
        with self.assertRaisesRegex(ValueError, "version/size"):
            m.verify_stock(bytes(bad), expected_hash=m.sha(bad),
                           expected_kernel_hash=m.sha(old),
                           expected_ramdisk_hash=m.sha(rd),
                           require_pinned_layout=False)

    def test_reject_nonzero_padding(self):
        stock, old, new, rd = synthetic()
        bad = bytearray(stock)
        bad[m.PAGE + len(old)] = 7
        with self.assertRaisesRegex(ValueError, "padding"):
            m.verify_stock(bytes(bad), expected_hash=m.sha(bad),
                           expected_kernel_hash=m.sha(old),
                           expected_ramdisk_hash=m.sha(rd),
                           require_pinned_layout=False)

    def test_zip_gate_fails_missing_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "a.zip"
            with zipfile.ZipFile(target, "w") as z:
                z.writestr(m.KERNEL_ZIP_PATH, b"example")
            with self.assertRaisesRegex(ValueError, "missing/duplicate"):
                m.read_exp27_zip(target)

    def test_zip_gate_rejects_duplicate_member(self):
        import warnings
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "dup.zip"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(target, "w") as z:
                    for n in (m.KERNEL_ZIP_PATH, m.SOURCE_ZIP_PATH,
                              m.LINK_ZIP_PATH, m.TOUCH_ZIP_PATH):
                        z.writestr(n, b"data")
                    z.writestr(m.KERNEL_ZIP_PATH, b"duplicate")
            with self.assertRaisesRegex(ValueError, "missing/duplicate"):
                m.read_exp27_zip(target)

if __name__ == "__main__":
    unittest.main()
