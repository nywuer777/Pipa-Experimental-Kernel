#!/usr/bin/env python3
"""Synthetic fail-closed tests; no Android access and no reboot/flash commands."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/exp27-3-release-gate.py"
spec = importlib.util.spec_from_file_location("exp27_3_gate", MODULE_PATH)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

class TestReleaseGate(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.a = root / "a"
        self.b = root / "b"
        self.a.mkdir()
        self.b.mkdir()
        for base in (self.a, self.b):
            for p in gate.MATCH:
                full = base / p
                full.parent.mkdir(parents=True, exist_ok=True)
                full.write_text("same-source-output\n")
            (base / "exp06-work/out/.config").write_text(
                "\n".join([*gate.REQUIRED_CONFIG, "# CONFIG_MODULES is not set"]) + "\n")
            img = base / gate.BASE_REL / "Image"
            img.parent.mkdir(parents=True, exist_ok=True)
            img.write_bytes(b"\x42" * (4_000_001 if base == self.a else 4_000_002))
        stage = self.b / "exp27-r8152-stage-gate.txt"
        stage.write_text("R8152_TARGET=v1.10.11\n" +
                         gate.EXPECTED["candidate_r8152_blob"] + "\n")
        (self.b / "exp24-rtl8153-link-gate.txt").write_text(
            "EXP24_RTL8153_LINK_PASS\n")
        self.audit = root / "audit.json"
        self.audit.write_text(json.dumps({
            "result": "PASS",
            "baseline_run": gate.EXPECTED["baseline_run"],
            "candidate_run": gate.EXPECTED["candidate_run"],
            "checks": [{"gate": "synthetic", "pass": True}],
        }))
        self.old_b = gate.EXPECTED["baseline_image_sha256"]
        self.new_b = gate.EXPECTED["candidate_image_sha256"]
        gate.EXPECTED["baseline_image_sha256"] = gate.filehash(
            self.a / gate.BASE_REL / "Image")
        gate.EXPECTED["candidate_image_sha256"] = gate.filehash(
            self.b / gate.BASE_REL / "Image")

    def tearDown(self):
        gate.EXPECTED["baseline_image_sha256"] = self.old_b
        gate.EXPECTED["candidate_image_sha256"] = self.new_b
        self.temp.cleanup()

    def test_synthetic_static_pass_never_authorizes_boot(self):
        r = gate.verify(self.a, self.b, self.audit)
        self.assertEqual(r["result"], "STATIC_PASS")
        self.assertFalse(r["flash_ready"])
        self.assertFalse(r["temporary_boot_authorized"])
        self.assertFalse(r["operator_physical_recovery_verified"])

    def test_candidate_corrupted_blocks(self):
        with (self.b / gate.BASE_REL / "Image").open("ab") as handle:
            handle.write(b"corrupted")
        self.assertEqual(gate.verify(self.a, self.b, self.audit)["result"], "BLOCKED")

    def test_missing_touchscreen_diff_blocks(self):
        (self.b / "exp25-touch-code.diff").unlink()
        self.assertEqual(gate.verify(self.a, self.b, self.audit)["result"], "BLOCKED")

    def test_missing_independent_audit_blocks(self):
        self.audit.unlink()
        self.assertEqual(gate.verify(self.a, self.b, self.audit)["result"], "BLOCKED")

    def test_flashable_boot_image_blocks(self):
        (self.b / "boot.img").write_bytes(b"do not allow")
        self.assertEqual(gate.verify(self.a, self.b, self.audit)["result"], "BLOCKED")

    def test_dtbo_img_is_not_incorrectly_classed_as_boot(self):
        p = self.b / gate.BASE_REL / "dtbo.img"
        self.assertTrue(p.exists())
        self.assertEqual(gate.verify(self.a, self.b, self.audit)["result"], "STATIC_PASS")

if __name__ == "__main__":
    unittest.main()
