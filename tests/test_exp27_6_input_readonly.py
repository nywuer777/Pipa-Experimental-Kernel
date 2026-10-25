#!/usr/bin/env python3
"""EXP27.6 passive Android input diagnostics: synthetic tests, no Android attached."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

P = Path(__file__).resolve().parents[1] / "tools/exp27-6-input-readonly.py"
spec = importlib.util.spec_from_file_location("exp276", P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

ADB_DEVICES = ("List of devices attached\n"
               "6665d3e6 device product:pipa model:23043RP34G device:pipa transport_id:1\n")
INPUT = ('I: Bus=0018 Vendor=0000 Product=0000 Version=0000\n'
         'N: Name="NVT-ts"\n'
         'H: Handlers=event8 \n'
         'B: EV=b\n\n'
         'I: Bus=0003 Vendor=046d Product=c077 Version=0111\n'
         'N: Name="USB Optical Mouse"\n'
         'H: Handlers=mouse0 event9\n'
         'B: EV=17\n')
IRQ = ('           CPU0       CPU1       CPU2\n'
       '521:        250          0          0          0 GICv3 240 Level NVT-ts\n')
VERSION = ("Linux version 4.19.404R (runner@runnervm8k3b6) "
           "#1 SMP PREEMPT Mon Oct 19 02:32:14 UTC 2026\n")
BOOTID = "c9c5a5af-c470-4e39-9adf-9f8f8c57e809\n"

def response(text, code=0):
    return mock.Mock(stdout=text, returncode=code)

class TestPassiveInput(unittest.TestCase):
    def test_input_detects_two_handlers_not_function(self):
        result=m.extract_input_summary(INPUT)
        self.assertEqual(result["input_devices_listed"],2)
        self.assertTrue(result["nvt_or_touch_label_present"])
        self.assertTrue(result["mouse_handler_present"])
        self.assertEqual(result["touch_functional"],"NOT_TESTED")
        self.assertEqual(result["mouse_functional"],"NOT_TESTED")

    def test_input_without_mouse_reports_false(self):
        result=m.extract_input_summary(INPUT.split("\n\n")[0])
        self.assertFalse(result["mouse_handler_present"])

    def test_input_without_device_header_fails_closed(self):
        with self.assertRaises(ValueError):
            m.extract_input_summary("Permission denied")

    def test_irq_snapshot(self):
        self.assertEqual(m.parse_nvt_irq(IRQ),
                         {"nvt_irq_visible":True,"nvt_irq_total":250})

    def test_no_irq_does_not_claim_failure_of_touch(self):
        self.assertEqual(m.parse_nvt_irq("CPU0\n4: 2 GICv3 usb"),
                         {"nvt_irq_visible":False,"nvt_irq_total":"NOT_FOUND"})

    def test_multiple_nvt_lines_rejected(self):
        with self.assertRaisesRegex(ValueError,"múltiplas IRQ"):
            m.parse_nvt_irq(IRQ + "522: 1 0 GICv3 other NVT-ts\n")

    def sequence(self, *,bootid_second=BOOTID, version=VERSION):
        return [
            response(ADB_DEVICES),
            response("pipa\n"),
            response("_b\n"),
            response("1\n"),
            response(version),
            response(BOOTID),
            response(INPUT),
            response(IRQ),
            response(bootid_second),
        ]

    def execute(self, seq):
        with tempfile.TemporaryDirectory() as td:
            exe=Path(td)/"adb.exe"
            exe.touch()
            with mock.patch.object(m.subprocess,"run",side_effect=seq) as run:
                try:
                    result=m.run_readonly(exe,"6665d3e6")
                    return result,run.call_args_list
                except Exception:
                    self.calls=run.call_args_list
                    raise

    def test_full_readonly_sequence(self):
        result,calls=self.execute(self.sequence())
        self.assertEqual(result["product"],"pipa")
        self.assertEqual(result["kernel"],"EXP25A_RECOGNIZED")
        self.assertEqual(result["boot_completed"],"1")
        self.assertFalse(result["flash_ready"])
        self.assertFalse(result["temporary_boot_authorized"])
        self.assertEqual(result["touch_functional"],"NOT_TESTED")
        self.assertEqual(len(calls),9)
        for call in calls[1:]:
            argv=call.args[0]
            self.assertEqual(argv[1:4],["-s","6665d3e6","shell"])
            self.assertIn(tuple(argv[4:]),m.ALLOWED_READS)

    def test_usb_and_wifi_duplicate_rejected_without_shell(self):
        multi=ADB_DEVICES+"adb-abc._adb-tls-connect._tcp device product:pipa\n"
        with tempfile.TemporaryDirectory() as td:
            exe=Path(td)/"adb.exe"
            exe.touch()
            with mock.patch.object(m.subprocess,"run",return_value=response(multi)) as run:
                with self.assertRaisesRegex(ValueError,"múltiplos"):
                    m.run_readonly(exe,"6665d3e6")
                self.assertEqual(run.call_count,1)

    def test_wrong_pipa_rejected(self):
        seq=self.sequence()
        seq[1]=response("different_device\n")
        with self.assertRaisesRegex(ValueError,"não é Xiaomi pipa"):
            self.execute(seq)
        self.assertEqual(len(self.calls),2)

    def test_changed_boot_id_rejected(self):
        with self.assertRaisesRegex(ValueError,"boot_id mudou"):
            self.execute(self.sequence(bootid_second="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee\n"))
        self.assertEqual(len(self.calls),9)

    def test_wrong_kernel_rejected_without_input_read(self):
        with self.assertRaisesRegex(ValueError,"kernel diferente"):
            self.execute(self.sequence(version="Linux version 4.19.404R (other@system)\n"))
        self.assertEqual(len(self.calls),5)

    def test_no_read_write_commands_whitelisted(self):
        for verb in ("reboot", "input", "su", "getevent", "setprop", "rm", "mount"):
            self.assertFalse(any(verb in c for c in m.ALLOWED_READS))
        self.assertEqual(len(m.ALLOWED_READS),7)

if __name__=="__main__":
    unittest.main()
