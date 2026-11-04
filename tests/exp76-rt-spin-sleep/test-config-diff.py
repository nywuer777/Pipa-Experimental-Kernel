#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / QEMU vs PIPA config diff synthetic regressions / NO FLASH
import importlib.util
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "tests/exp76-rt-spin-sleep/check-config-diff.py"
spec = importlib.util.spec_from_file_location("exp76_cfg_diff", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def sample(path, overrides):
    lines = [f"CONFIG_FILLER_{i}=y" for i in range(220)]
    lines += ["CONFIG_PREEMPT_RT_FULL=y", "CONFIG_RCU_BOOST=y", "# CONFIG_MODULES is not set"]
    lines = [x for x in lines if not any(x.startswith(k+"=") or x.startswith("# "+k+" is not set") for k in overrides)]
    lines += [f"{k}={v}" if v != "n" else f"# {k} is not set" for k, v in overrides.items()]
    path.write_text("\n".join(lines)+"\n")

with tempfile.TemporaryDirectory() as d:
    root = Path(d); a = root/"pipa"; b = root/"qemu"; report = root/"report.json"
    critical = ROOT/"tests/exp76-rt-spin-sleep/rt-critical-configs.txt"
    sample(a,{})
    sample(b,{"CONFIG_MODULES":"y"})
    obj=mod.execute(a,b,critical,report)
    assert obj["state"]=="PASS"
    assert [x["key"] for x in obj["noncritical_differences"]]==["CONFIG_MODULES"]
    sample(b,{"CONFIG_MODULES":"y","CONFIG_RCU_BOOST":"n"})
    try:
        mod.execute(a,b,critical,report)
    except ValueError as error:
        assert "CONFIG_RCU_BOOST" in str(error)
    else:
        raise AssertionError("critical drift was accepted")
    assert '"state": "FAIL"' in report.read_text()
print("EXP76_QEMU_RT_PIPA_DIFF_TEST=PASS; CRITICAL_DRIFT_REJECTED; NO_FLASH")
