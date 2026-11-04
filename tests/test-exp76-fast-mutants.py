#!/usr/bin/env python3
# Python 3 / Ubuntu GitHub Actions / 10 disposable FAST mutation fixtures with actual diff commands / NO FLASH
"""Measure mutations against the exact EXP76_FAST_20 contract; no production code mutated."""
import argparse
import datetime
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAST = ROOT / "tools/exp76-fast-benchmark.py"
BASE = {
    "kernel/fast_mutation.c": "#include <linux/kernel.h>\nint fast_mutation(void) { return 1; }\n",
    "kernel/fast_mutation.h": "#ifndef FAST_MUTATION_H\n#define FAST_MUTATION_H\n#define FAST_VALUE 1\n#endif\n",
    "tools/mutation.py": "def number():\n    return 1\n",
    "Makefile": "all:\n\t@echo valid\n",
    "Kconfig": 'source "kernel/Kconfig"\n',
    "kernel/Kconfig": 'config FAST_KCONFIG\n    bool "fast"\n',
    "defconfig": "CONFIG_FAST_KCONFIG=y\n",
}
MUTANTS = [
    ("M1", "kernel/fast_mutation.c", "#include <linux/arquivo_inexistente.h>\nint fast_mutation(void) { return 1; }\n", "missing C include"),
    ("M2", "kernel/fast_mutation.c", "#include <linux/kernel.h>\nint fast_mutation(void) { return funcao_inexistente(); }\n", "unresolved C call"),
    ("M3", "defconfig", "CONFIG_FAST_KCONFIG=y\nCONFIG_NONEXISTENT_OPTION=y\n", "undefined Kconfig option"),
    ("M4", "kernel/fast_mutation.c", "#include <linux/kernel.h>\nint fast_mutation(void) { \t return 1; }\n", "trailing/mixed whitespace"),
    ("M5", "tools/mutation.py", "def number():\nreturn 1\n", "Python invalid indentation"),
    ("M6", "Makefile", "all:\n@echo broken\n", "Makefile recipe tab missing"),
    ("M7", "kernel/fast_mutation.h", "#ifndef FAST_MUTATION_H\n#define FAST_MUTATION_H\n#define FAST_VALUE 1\n", "unclosed #ifdef"),
    ("M8", "kernel/fast_mutation.c", "#include <linux/kernel.h>\nint fast_mutation(void) { return var_nao_declarada; }\n", "undefined C variable"),
    ("M9", "kernel/fast_mutation.c", "#include <linux/kernel.h>\nint fast_mutation(void) { return 1; }\nint fast_mutation(void) { return 2; }\n", "duplicate C symbol"),
    ("M10", "Kconfig", 'source "kernel/Kconfig"\nsource "drivers/kernelsu/Kconfig"\n', "missing Kconfig include"),
]

def cmd(argv, cwd, timeout=25):
    return subprocess.run(argv, cwd=cwd, text=True, capture_output=True,
                          timeout=timeout, check=False)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--checkpatch",default="")
    a=p.parse_args()
    measurements=[]
    for mutant_id, relative, content, expected in MUTANTS:
        with tempfile.TemporaryDirectory(prefix="exp76-fast-mutant-") as d:
            root=Path(d)
            for name, baseline in BASE.items():
                path=root/name
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(baseline,encoding="utf-8")
            for argv in (
                ["git","init","-q"],
                ["git","config","user.name","exp76-fixture"],
                ["git","config","user.email","exp76-fixture@example.invalid"],
                ["git","add","-A"],
                ["git","commit","-qm","baseline"],
            ):
                r=cmd(argv,root)
                if r.returncode:
                    raise RuntimeError("git setup failed: "+r.stderr)
            (root/relative).write_text(content,encoding="utf-8")
            for argv in (["git","add","-A"], ["git","commit","-qm",mutant_id]):
                r=cmd(argv,root)
                if r.returncode:
                    raise RuntimeError("failed to commit mutation: "+r.stderr)
            output=root/"mutation-result.json"
            r=cmd([sys.executable,str(FAST),"--runs","20",
                   "--base","HEAD^","--head","HEAD","--output",str(output),
                   "--checkpatch",str(Path(a.checkpatch).resolve()) if a.checkpatch else ""],
                  root,timeout=85)
            report=json.loads(output.read_text()) if output.exists() else None
            if report is None or len(report.get("fast_runs",[]))!=20:
                raise RuntimeError(f"{mutant_id} FAST did not finish: {r.stderr}")
            fail_measurements=sum(1 for x in report["fast_runs"] if not x["lint_pass"])
            measurements.append({
                "mutation_id":mutant_id, "description":expected, "changed_file":relative,
                "fast_detected":r.returncode==1,
                "fast_exit_code":r.returncode,
                "blocking_fail_count":fail_measurements,
                "checkpatch_diagnostic":report["checkpatch_diagnostic"],
                "fast_median_s":report["fast_median_s"],
                "fast_p95_s":report["fast_p95_s"],
            })
    detected=sum(x["fast_detected"] for x in measurements)
    classification=("TECHNICAL_COVERAGE" if detected>=8 else
                    "STYLE_SYNTAX_GATE_ONLY" if detected<5 else
                    "PARTIAL_TECHNICAL_COVERAGE")
    report={
        "schema_version":1, "test_id":"EXP76_FAST_TEN_MUTATIONS",
        "generated_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_sha":os.environ.get("GITHUB_SHA"),
        "mutations":measurements, "detected":detected,
        "total":len(MUTANTS), "detection_rate_pct":detected*10,
        "classification":classification,
        "kernel_compilation_performed":False,"rt_handoff_ready":False
    }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":
    main()
