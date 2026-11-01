#!/usr/bin/env python3
# Python 3 unittest / GitHub Actions Ubuntu / EXP76 exact-source uname patch tests
"""Fail-closed tests for the E404 newuname UID spoof removal."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "exp76_fix_uname", ROOT / "tools/exp76-fix-uname.py"
)
fix = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fix)

ORIGINAL = (
    "/* source prefix */\n"
    + fix.START
    + "{\n"
    + "\tstruct new_utsname tmp;\n"
    + fix.DECL
    + "\tdown_read(&uts_sem);\n"
    + "\tmemcpy(&tmp, utsname(), sizeof(tmp));\n"
    + "\tif (current_uid().val == 0 &&\n"
    + '\t    !strncmp(current->comm, "bpfloader", 9)) {\n'
    + '\t\t' + fix.NETWORK_RULE + "\n"
    + '\t\tpr_info("fake uname: service");\n'
    + fix.SPOOF
    + "\tup_read(&uts_sem);\n"
    + "\treturn 0;\n"
    + "}\n\n"
    + fix.END
    + "/* original suffix */\n"
)


class TestExp76Uname(unittest.TestCase):
    def test_removes_only_generic_uid_spoof(self):
        patched = fix.transform(ORIGINAL)
        fix.verify(patched)
        self.assertNotIn("5.10.404R", patched)
        self.assertNotIn("cur_uid >=", patched)
        self.assertIn(fix.NETWORK_RULE, patched)
        self.assertIn('pr_info("fake uname: service")', patched)
        self.assertIn("/* original suffix */", patched)

    def test_verify_rejects_unpatched(self):
        with self.assertRaises(ValueError):
            fix.verify(ORIGINAL)

    def test_repeated_apply_fails_closed(self):
        patched = fix.transform(ORIGINAL)
        with self.assertRaises(ValueError):
            fix.transform(patched)

    def test_no_network_override_is_rejected(self):
        changed = ORIGINAL.replace(fix.NETWORK_RULE, "")
        with self.assertRaises(ValueError):
            fix.transform(changed)

    def test_unknown_spoof_format_is_rejected(self):
        changed = ORIGINAL.replace("cur_uid >= 1000", "cur_uid > 1000")
        with self.assertRaises(ValueError):
            fix.transform(changed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
