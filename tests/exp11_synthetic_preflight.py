#!/usr/bin/env python3
"""EXP11 synthetic boot/vbmeta layout tests, no real device data."""
import io
import struct
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import exp11_offline_boot_preflight as audit

def arm_kernel(size=256):
    a=bytearray(size)
    a[56:60]=b"ARMd"
    return bytes(a)

def fdt(n=64):
    return b"\xd0\x0d\xfe\xed" + struct.pack(">I", n) + bytes(n-8)

def synthetic_boot():
    head=bytearray(4096)
    head[:8]=b"ANDROID!"
    struct.pack_into("<IIII", head, 8, 256, 128, 0, 1580)
    struct.pack_into("<I", head, 40, 3)
    generic=b"\x1f\x8b"+bytes(126)
    return bytes(head) + arm_kernel() + bytes(4096-256) + generic

def synthetic_vendor():
    head=bytearray(4096)
    head[:8]=b"VNDRBOOT"
    struct.pack_into("<II", head, 8, 3, 4096)
    struct.pack_into("<I", head, 24, 128)
    struct.pack_into("<II", head, 2096, 2112, 64)
    return bytes(head)+b"\x1f\x8b"+bytes(126)+bytes(4096-128)+fdt()

def synthetic_dtbo():
    head=struct.pack(">8I",0xD7B7AB1E,128,32,32,1,32,4096,0)
    entry=struct.pack(">8I",64,64,0,0,0,0,0,0)
    return head+entry+fdt()

def synthetic_vbmeta():
    head=bytearray(256)
    head[:4]=b"AVB0"
    struct.pack_into(">II", head, 4, 1, 0)
    struct.pack_into(">I", head, 120, 3)
    return bytes(head)

class TestBootSafety(unittest.TestCase):
    def test_valid_boot_v3(self):
        d=audit.boot_v3(io.BytesIO(synthetic_boot()))
        self.assertEqual(d["kernel_offset"], 4096)
        self.assertEqual(d["generic_ramdisk_offset"], 8192)
        self.assertEqual(d["kernel_size"], 256)
        self.assertEqual(d["original_kernel_sha256"], audit.sha_stream(io.BytesIO(arm_kernel())))
    def test_bad_header_version(self):
        x=bytearray(synthetic_boot())
        struct.pack_into("<I", x, 40, 4)
        with self.assertRaises(ValueError):
            audit.boot_v3(io.BytesIO(x))
    def test_bad_kernel_arm_magic(self):
        x=bytearray(synthetic_boot())
        x[4096+56]=0
        with self.assertRaises(ValueError):
            audit.boot_v3(io.BytesIO(x))
    def test_bad_ramdisk_bounds(self):
        x=bytearray(synthetic_boot())
        struct.pack_into("<I", x, 12, 500000)
        with self.assertRaises(ValueError):
            audit.boot_v3(io.BytesIO(x))
    def test_vendor_boot_v3(self):
        d=audit.vendor_boot_v3(io.BytesIO(synthetic_vendor()))
        self.assertEqual(d["dtb_offset"],8192)
        self.assertEqual(d["dtb_size"],64)
    def test_vendor_bad_fdt_size(self):
        x=bytearray(synthetic_vendor())
        struct.pack_into(">I",x,8192+4,128)
        with self.assertRaises(ValueError):
            audit.vendor_boot_v3(io.BytesIO(x))
    def test_dtbo_table(self):
        d=audit.dtbo_table(io.BytesIO(synthetic_dtbo()))
        self.assertEqual(d["count"],1)
        self.assertEqual(d["table_size"],128)
    def test_dtbo_bad_entry_offset(self):
        x=bytearray(synthetic_dtbo())
        struct.pack_into(">I",x,32+4,2048)
        with self.assertRaises(ValueError):
            audit.dtbo_table(io.BytesIO(x))
    def test_vbmeta_structural_only(self):
        d=audit.vbmeta_header(io.BytesIO(synthetic_vbmeta()))
        self.assertEqual(d["flags"],3)
        self.assertFalse(d["signature_chain_cryptographically_verified"])
    def test_vbmeta_bad_magic(self):
        x=bytearray(synthetic_vbmeta())
        x[0]=0
        with self.assertRaises(ValueError):
            audit.vbmeta_header(io.BytesIO(x))

if __name__=="__main__":
    unittest.main()
