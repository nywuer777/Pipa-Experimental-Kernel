#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage35 might_sleep regression / NO FLASH
"""Exercise the RT rejected debug/normal macro pair and fail-closed guards."""
from __future__ import annotations

import json
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/exp76-rt-stage35-might-sleep.py"
CODE = runpy.run_path(str(SCRIPT), run_name="stage35_fixture")
DEBUG = CODE["DEBUG_ANCHOR"]
NORMAL = CODE["NORMAL_ANCHOR"]
HEADER = (
    "#ifdef CONFIG_DEBUG_ATOMIC_SLEEP\n"
    "extern void ___might_sleep(const char *file, int line, int preempt_offset);\n"
    + DEBUG
    + "#else\n"
    "  static inline void ___might_sleep(const char *file, int line,\n"
    "                                  int preempt_offset) { }\n"
    + NORMAL
    + "#endif\n"
)
REJECT = (
    "diff a/include/linux/kernel.h b/include/linux/kernel.h (rejected hunks)\n"
    "@@ -260,6 +260,9 @@ extern int _cond_resched(void);\n"
    + CODE["REJECT_DEBUG"] + "\n"
    "@@ -267,6 +270,7 @@ extern int _cond_resched(void);\n"
    + CODE["REJECT_NORMAL"] + "\n"
)


def put(root: Path, rel: str, value: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def seed(root: Path) -> None:
    put(root, "include/linux/kernel.h", HEADER)
    put(root, "include/linux/kernel.h.rej", REJECT)
    put(root, "kernel/locking/rtmutex.c",
        "static void fastlock(void)\n{\n\tmight_sleep_no_state_check();\n}\n")
    put(root, "kernel/sched/cpupri.c.rej", "pending\n")
    for n in range(62):
        put(root, f"pending/{n:02d}.rej", "pending\n")


def invoke(root: Path, mode: str = "apply") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--tree", str(root),
         "--report", str(root / "report"), "--mode", mode],
        capture_output=True, text=True,
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        good = base / "good"
        seed(good)
        verified = invoke(good, "verify")
        assert verified.returncode == 0, verified.stderr
        assert (good / "include/linux/kernel.h").read_text() == HEADER

        accepted = invoke(good)
        assert accepted.returncode == 0, accepted.stderr
        transformed = (good / "include/linux/kernel.h").read_text()
        expected = HEADER.replace(DEBUG, DEBUG + CODE["DEBUG_DEFINE"], 1)
        expected = expected.replace(NORMAL, NORMAL + CODE["NORMAL_DEFINE"], 1)
        assert transformed == expected
        assert transformed.count("# define might_sleep_no_state_check()") == 2
        assert "___might_sleep(__FILE__, __LINE__, 0); might_resched();" in transformed
        assert "do { might_resched(); } while (0)" in transformed
        manifest = json.loads((good / "report/stage35-status.json").read_text())
        assert manifest["remaining_rejected_files"] == 64
        assert manifest["rt_mutex_runtime_semantics_verified"] is False
        assert manifest["kernel_built"] is False and manifest["flash_ready"] is False

        missing_debug = base / "missing-debug-hunk"
        seed(missing_debug)
        put(missing_debug, "include/linux/kernel.h.rej",
            REJECT.replace(CODE["REJECT_DEBUG"], "+# wrong_debug_implementation"))
        assert invoke(missing_debug).returncode != 0
        assert (missing_debug / "include/linux/kernel.h").read_text() == HEADER

        missing_normal = base / "missing-normal-hunk"
        seed(missing_normal)
        put(missing_normal, "include/linux/kernel.h.rej",
            REJECT.replace(CODE["REJECT_NORMAL"], "+# wrong_normal_implementation"))
        assert invoke(missing_normal).returncode != 0

        header_drift = base / "header-drift"
        seed(header_drift)
        put(header_drift, "include/linux/kernel.h",
            HEADER.replace("___might_sleep", "__wrong_might_sleep"))
        assert invoke(header_drift).returncode != 0

        missing_caller = base / "missing-caller"
        seed(missing_caller)
        put(missing_caller, "kernel/locking/rtmutex.c",
            "static void fastlock(void) { might_sleep(); }\n")
        assert invoke(missing_caller).returncode != 0

        duplicate = base / "duplicate"
        seed(duplicate)
        put(duplicate, "include/linux/kernel.h", HEADER + CODE["DEBUG_DEFINE"])
        assert invoke(duplicate).returncode != 0

        rejects_drift = base / "reject-drift"
        seed(rejects_drift)
        (rejects_drift / "pending/00.rej").unlink()
        assert invoke(rejects_drift).returncode != 0
    print("EXP76_STAGE35_MIGHT_SLEEP_REGRESSIONS=8_PASS; FLASH_READY=false")


if __name__ == "__main__":
    main()
