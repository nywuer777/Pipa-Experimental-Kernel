#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / QEMU_RT_PIPA_DIFF fail-closed Kconfig gate / NO FLASH
"""Compare final generated PIPA and QEMU RT configs with an audited critical list."""
import argparse
import hashlib
import json
import re
from pathlib import Path

KEY = re.compile(r"^CONFIG_[A-Z0-9_]+$")
YES = re.compile(r"^(CONFIG_[A-Z0-9_]+)=(.*)$")
NO = re.compile(r"^# (CONFIG_[A-Z0-9_]+) is not set$")

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_config(path: Path) -> dict:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = YES.fullmatch(line)
        if match:
            name, value = match.groups()
        else:
            match = NO.fullmatch(line)
            if not match:
                continue
            name, value = match.group(1), "n"
        if name in values:
            raise ValueError("duplicated Kconfig key " + name)
        values[name] = value
    if len(values) < 200:
        raise ValueError("not a complete generated .config: " + str(path))
    return values

def execute(pipa_path: Path, qemu_path: Path, critical_path: Path,
            report: Path) -> dict:
    pipa, qemu = read_config(pipa_path), read_config(qemu_path)
    names = [
        line.strip() for line in critical_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not names or len(names) != len(set(names)) or any(not KEY.fullmatch(x) for x in names):
        raise ValueError("invalid or duplicated critical CONFIG_ entries")
    if pipa.get("CONFIG_PREEMPT_RT_FULL") != "y" or qemu.get("CONFIG_PREEMPT_RT_FULL") != "y":
        raise ValueError("both RT configs must have CONFIG_PREEMPT_RT_FULL=y")
    critical = set(names)
    diffs = [
        {"key": key, "pipa": pipa.get(key, "<absent>"),
         "qemu": qemu.get(key, "<absent>"), "critical": key in critical}
        for key in sorted(pipa.keys() | qemu.keys())
        if pipa.get(key, "<absent>") != qemu.get(key, "<absent>")
    ]
    blocked = [x for x in diffs if x["critical"]]
    result = {
        "stage": "EXP76_QEMU_RT_PIPA_EFFECTIVE_KCONFIG_DIFF",
        "state": "FAIL" if blocked else "PASS",
        "pipa_config_sha256": digest(pipa_path),
        "qemu_config_sha256": digest(qemu_path),
        "critical_list_sha256": digest(critical_path),
        "critical_symbols": names,
        "critical_differences": blocked,
        "noncritical_differences": [x for x in diffs if not x["critical"]],
        "rt_handoff_ready": False,
        "flash_ready": False,
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if blocked:
        raise ValueError("QEMU_RT_PIPA_DIFF critical delta: " +
                         ", ".join(x["key"] for x in blocked))
    return result

def main() -> None:
    cli = argparse.ArgumentParser()
    cli.add_argument("--pipa", type=Path, required=True)
    cli.add_argument("--qemu", type=Path, required=True)
    cli.add_argument("--critical", type=Path, required=True)
    cli.add_argument("--report", type=Path, required=True)
    args = cli.parse_args()
    print(json.dumps(execute(args.pipa, args.qemu, args.critical, args.report), indent=2))

if __name__ == "__main__":
    main()
