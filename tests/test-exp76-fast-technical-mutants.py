#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / disposable EXP76 FAST technical mutation fixtures / NO FLASH
"""Execute ten actual mutations against incremental technical checks, no kernel image."""
import argparse
import datetime
import json
import os
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = runpy.run_path(str(ROOT/"tests/test-exp76-fast-mutants.py"))
BASE = LEGACY["BASE"]
MUTANTS = LEGACY["MUTANTS"]
TOOL = ROOT/"tools/exp76-fast-technical.py"


def cmd(argv, cwd, timeout=40):
    return subprocess.run(argv, cwd=cwd, text=True, capture_output=True,
                          timeout=timeout, check=False)


def git_setup(root, mutant_id, file_path, source):
    for name, content in BASE.items():
        file = root/name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")
    header = root/"include/linux/kernel.h"
    header.parent.mkdir(parents=True, exist_ok=True)
    header.write_text("#ifndef _LINUX_KERNEL_H\n#define _LINUX_KERNEL_H\n#endif\n")
    for argv in [
        ["git", "init", "-q"],
        ["git", "config", "user.name", "exp76-mutation-ci"],
        ["git", "config", "user.email", "exp76-mutation@example.invalid"],
        ["git", "add", "-A"],
        ["git", "commit", "-qm", "baseline"],
    ]:
        p=cmd(argv, root)
        if p.returncode:
            raise RuntimeError("fixture setup failed: "+p.stderr)
    (root/file_path).write_text(source, encoding="utf-8")
    for argv in (["git", "add", "-A"], ["git", "commit", "-qm", mutant_id]):
        p = cmd(argv, root)
        if p.returncode:
            raise RuntimeError("fixture mutation commit failed: "+p.stderr)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args=parser.parse_args()
    measurements=[]
    for ident,path,source,description in MUTANTS:
        with tempfile.TemporaryDirectory(prefix="exp76-fast-technical-") as d:
            tree=Path(d)
            git_setup(tree, ident, path, source)
            report=tree/"technical-result.json"
            p=cmd([sys.executable, str(TOOL), "--tree", str(tree),
                   "--mode", "fixture", "--base", "HEAD^", "--head", "HEAD",
                   "--output", str(report)], ROOT)
            record=json.loads(report.read_text()) if report.is_file() else {}
            matches=[x["test"] for x in record.get("checks",[])
                     if x["exit_code"]!=0]
            detected=p.returncode==1 and record.get("state")=="FAIL"
            measurements.append({"id":ident,"description":description,
                                 "detected":detected,"exit_code":p.returncode,
                                 "failing_checks":matches,
                                 "error_tail":(p.stdout+p.stderr)[-1000:]})
    count=sum(x["detected"] for x in measurements)
    report={"schema_version":1,"stage":"EXP76_FAST_TECHNICAL_FIXTURE_MUTATIONS",
            "source_sha":os.environ.get("GITHUB_SHA"),
            "generated_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "total":10,"detected":count,"mutations":measurements,
            "c_compiler_mode":"HOST_FIXTURE_SYNTAX_ONLY",
            "production_kernel_objects_compiled":0,
            "production_kbuild_gate_qualified":False,
            "rt_handoff_ready":False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
    if count<7:
        raise SystemExit("BLOCKED_FAST_TECHNICAL_FIXTURE_COVERAGE_UNDER_7")
if __name__=="__main__":
    main()
