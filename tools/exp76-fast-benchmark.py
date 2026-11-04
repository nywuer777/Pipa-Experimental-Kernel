#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 FAST commit-diff benchmark / NO FLASH
"""Time 20 real FAST executions. Kernel build and ccache are separate."""
import argparse
import datetime
import json
import math
import os
import pathlib
import statistics
import subprocess
import sys
import time

def run(cmd, *, input_text=None, timeout=25, env=None):
    begin=time.perf_counter()
    try:
        p=subprocess.run(cmd,input=input_text,text=True,capture_output=True,timeout=timeout,env=env,check=False)
        rc=p.returncode; log=(p.stdout+p.stderr)[-3000:]
    except subprocess.TimeoutExpired as e:
        rc=124; log=f"timeout ({e.timeout}s)"
    return {"argv":cmd,"returncode":rc,"duration_s":round(time.perf_counter()-begin,6),"log":log}

def git(*args):
    p=subprocess.run(["git",*args],capture_output=True,text=True,check=True)
    return p.stdout

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--runs",type=int,default=20)
    p.add_argument("--base",default="HEAD^")
    p.add_argument("--head",default="HEAD")
    p.add_argument("--checkpatch",default="")
    p.add_argument("--output",type=pathlib.Path,required=True)
    a=p.parse_args()
    if a.runs!=20:
        raise SystemExit("EXP76_FAST requires exactly 20 iterations")
    changed=sorted(set(x for x in git("diff","--name-only","--diff-filter=ACMR",a.base,a.head).splitlines() if x))
    py=[x for x in changed if x.endswith(".py") and pathlib.Path(x).is_file()]
    c=[x for x in changed if x.endswith((".c",".h")) and pathlib.Path(x).is_file()]
    patch=git("diff","--no-ext-diff","--binary",a.base,a.head,"--",*c) if c else ""
    checkpatch_available=bool(a.checkpatch and pathlib.Path(a.checkpatch).is_file())
    runs=[]
    for i in range(a.runs):
        start=time.perf_counter()
        measurements=[]
        measurements.append(run(["git","diff","--check",a.base,a.head]))
        if py:
            measurements.append(run([sys.executable,"-m","py_compile",*py]))
        if patch and checkpatch_available:
            # checkpatch warnings are non-blocking diagnostics, never FAST gate failures.
            measurements.append(run(["perl",a.checkpatch,"--no-tree","--no-signoff","-"],input_text=patch))
        elapsed=round(time.perf_counter()-start,6)
        blocking=[x for x in measurements if x["returncode"]!=0 and
                  x["argv"][0]!="perl"]
        runs.append({
            "ts":datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "duration_s":elapsed,
            "cmd_count":len(measurements),
            "lint_pass":not blocking,
            "measurements":measurements,
            "iteration":i+1
        })
    durations=sorted(x["duration_s"] for x in runs)
    p95=durations[math.ceil(.95*len(durations))-1]
    per_cmd={}
    for item in runs:
        for m in item["measurements"]:
            name=("checkpatch-diagnostic" if m["argv"][0]=="perl"
                  else "py_compile" if "py_compile" in m["argv"]
                  else "git_diff_check")
            per_cmd.setdefault(name,[]).append(m["duration_s"])
    expensive=sorted(({"cmd":k,"total_duration_s":round(sum(v),6),
                        "median_duration_s":round(statistics.median(v),6)}
                      for k,v in per_cmd.items()),
                     key=lambda v:-v["total_duration_s"])[:3]
    state="PASS" if p95<300 and all(r["lint_pass"] for r in runs) else "FAIL"
    report={
        "gate":"EXP76_FAST_20",
        "state":state,
        "source_sha":os.environ.get("GITHUB_SHA"),
        "base":a.base,"head":a.head,
        "fast_runs":runs,
        "fast_median_s":round(statistics.median(durations),6),
        "fast_p95_s":round(p95,6),
        "p95_method":"nearest_rank_sorted_index_ceil(0.95*n)-1",
        "fast_target_60s_pass":p95<60,
        "fast_gate_300s_pass":p95<300,
        "changed_python":py,"changed_c_h":c,
        "checkpatch_diagnostic":"RUN" if patch and checkpatch_available else
                "NOT_APPLICABLE" if not patch else "UNAVAILABLE",
        "checkpatch_nonblocking":True,
        "most_expensive_commands":expensive,
        "ccache_runs":[],
        "ccache_warm_hit_rate_pct":None,
        "ccache_state":"NOT_MEASURED",
        "rt_handoff_ready":False
    }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="fast_runs"},indent=2))
    if state!="PASS":
        raise SystemExit(1)
if __name__=="__main__":
    main()
