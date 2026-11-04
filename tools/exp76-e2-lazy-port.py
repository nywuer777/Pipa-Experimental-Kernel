#!/usr/bin/env python3
# Python 3 / E404 4.19 RT partial overlay / exact-context six-hunk lazy-resched reconciliation / NO FLASH
"""Apply only exact, unique fair.c reject contexts if RT lazy-preemption exists."""
import argparse
import hashlib
import json
import re
from pathlib import Path

EXPECTED_REJ_SHA256 = "b8c15cc49c3ce680e176b54065795e0bc058b481ca297cb0dff47733d8ff4c2f"
TARGET_HUNK_ORDINALS = (1, 2, 3, 7, 15, 20)
MARKER = "resched_curr_lazy("

def sha(data):
    return hashlib.sha256(data).hexdigest()

def hunks(rej):
    chunks = re.split(r"(?=^@@ -)", rej, flags=re.MULTILINE)
    result=[]
    for chunk in chunks:
        if not chunk.startswith("@@ -"):
            continue
        lines = chunk.splitlines(keepends=True)
        header=lines[0].strip()
        old=[]; new=[]
        for line in lines[1:]:
            if line.startswith(" "):
                old.append(line[1:]); new.append(line[1:])
            elif line.startswith("-"):
                old.append(line[1:])
            elif line.startswith("+"):
                new.append(line[1:])
            elif line.startswith("\\ No newline"):
                continue
            elif line.startswith(("diff ","--- ","+++ ")):
                break
            else:
                raise ValueError("unexpected rejected hunk row: "+repr(line))
        result.append((header,"".join(old),"".join(new)))
    return result

def attempt(tree,mode):
    path=tree/"kernel/sched/fair.c"
    core=(tree/"kernel/sched/core.c").read_text()
    header=(tree/"kernel/sched/sched.h").read_text()
    fair=path.read_text()
    reject=(tree/"kernel/sched/fair.c.rej").read_bytes()
    actual=sha(reject)
    if actual!=EXPECTED_REJ_SHA256:
        raise ValueError("Stage82 fair.c.reject checksum drift "+actual)
    chunks=hunks(reject.decode())
    if len(chunks)!=20:
        raise ValueError("expected exactly 20 fair.c rejected hunks; got "+str(len(chunks)))
    prereq={
        "core_definition":bool(re.search(r"\b(?:void|static\s+void)\s+resched_curr_lazy\s*\(",core)),
        "sched_h_declaration":bool(re.search(r"\bresched_curr_lazy\s*\(",header)),
        "arm64_lazy_flag":bool(re.search(r"TIF_NEED_RESCHED_LAZY",(tree/"arch/arm64/include/asm/thread_info.h").read_text()))
            if (tree/"arch/arm64/include/asm/thread_info.h").exists() else False,
    }
    ready=all(prereq.values())
    entries=[]
    current=fair
    for ordinal in TARGET_HUNK_ORDINALS:
        hdr,old,new=chunks[ordinal-1]
        if "resched_curr(" not in old or MARKER not in new:
            raise ValueError("expected resched_curr to resched_curr_lazy in hunk "+str(ordinal))
        old_count=current.count(old)
        new_count=current.count(new)
        if not ready:
            state="BLOCKED_CORE_LAZY_PREREQUISITE"
        elif new_count==1:
            state="ALREADY_APPLIED"
        elif old_count==1:
            state="EXACT_CONTEXT_MATCH"
            if mode=="apply":
                current=current.replace(old,new,1)
                state="APPLIED_EXACT_CONTEXT"
        elif old_count>1:
            state="BLOCKED_AMBIGUOUS_CONTEXT"
        else:
            state="BLOCKED_DIVERGED_CONTEXT"
        entries.append({
            "ordinal":ordinal,"hunk_id":EXPECTED_REJ_SHA256+":"+str(ordinal).zfill(2),
            "header":hdr,"old_context_occurrences":old_count,
            "already_applied_context_occurrences":new_count,"state":state
        })
    before_sha=sha(fair.encode())
    after_sha=sha(current.encode())
    if mode=="apply" and current!=fair:
        path.write_text(current)
    return {
        "gate":"EXP76_E2_LAZY_SCHEDULER_RECONCILIATION",
        "mode":mode,"tree":str(tree),"source_sha256_before":before_sha,
        "source_sha256_after":after_sha,
        "reject_sha256":actual,"upstream_lazy_prerequisites":prereq,
        "selected_hunk_count":6,
        "applied_count":sum(x["state"]=="APPLIED_EXACT_CONTEXT" for x in entries),
        "already_applied_count":sum(x["state"]=="ALREADY_APPLIED" for x in entries),
        "blocked_count":sum(x["state"].startswith("BLOCKED") for x in entries),
        "entries":entries,
        "kernel_sched_core_object_built":False,
        "runtime_verified":False,
        "rt_handoff_ready":False
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--tree",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    p.add_argument("--mode",choices=["plan","apply"],default="plan")
    a=p.parse_args()
    report=attempt(a.tree,a.mode)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
    if report["blocked_count"]:
        raise SystemExit(2)

if __name__=="__main__":
    main()
