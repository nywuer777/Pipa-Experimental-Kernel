#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / E404 RT overlay + Clang21 nonRT QEMU control / NO FLASH
"""Guard RT-only rcu_bh_qs() behind CONFIG_PREEMPT_RT_FULL in __do_softirq."""
import argparse
import hashlib
import json
import re
from pathlib import Path

REL = Path("kernel/softirq.c")
TOKEN = "rcu_bh_qs();"
PIN = "fed88a6024cd4d46c52eda607a95d97d7371ba81"
PAT = re.compile(r"(?m)^(?P<indent>[ \t]*)rcu_bh_qs\(\);[ \t]*$")
FUNCTION = "asmlinkage __visible void __softirq_entry __do_softirq(void)"
FALLBACK = "rcu_softirq_qs();"

def sha(data):
    return hashlib.sha256(data).hexdigest()

def apply(text):
    if FUNCTION not in text:
        raise ValueError("BLOCKED_SOFTIRQ_FUNCTION_MISSING")
    start = text.index(FUNCTION)
    end = text.find("asmlinkage __visible void do_softirq", start)
    if end < start:
        raise ValueError("BLOCKED_SOFTIRQ_FUNCTION_BOUNDARY")
    body = text[start:end]
    matches = list(PAT.finditer(text))
    if len(matches) != 1:
        raise ValueError("BLOCKED_SOFTIRQ_QS_CALL_COUNT="+str(len(matches)))
    match = matches[0]
    if not start < match.start() < end:
        raise ValueError("BLOCKED_SOFTIRQ_QS_OUTSIDE_DO_SOFTIRQ")
    indent = match.group("indent")
    old = match.group()
    replacement = (
        "#ifdef CONFIG_PREEMPT_RT_FULL\n"
        + indent + TOKEN + "\n"
        + "#else\n"
        + indent + "if (__this_cpu_read(ksoftirqd) == current)\n"
        + indent + "\t" + FALLBACK + "\n"
        + "#endif"
    )
    if replacement in text:
        return text, "ALREADY_APPLIED"
    if "#ifdef CONFIG_PREEMPT_RT_FULL\n"+old in text:
        raise ValueError("BLOCKED_SOFTIRQ_EXISTING_CONFIG_GUARD")
    if old not in text:
        raise ValueError("BLOCKED_SOFTIRQ_CONTEXT_MISSING")
    result = text[:match.start()] + replacement + text[match.end():]
    if result.count(TOKEN) != text.count(TOKEN) or result.count(FALLBACK) < 1:
        raise ValueError("BLOCKED_SOFTIRQ_POSTCONDITION")
    return result, "APPLIED"

def self_test():
    old = (
        FUNCTION + "\n{\n\tif (pending)\n\t\trcu_bh_qs();\n}\n\n"
        "asmlinkage __visible void do_softirq(void)\n{\n}\n"
    )
    new,state=apply(old)
    assert state == "APPLIED"
    assert apply(new) == (new, "ALREADY_APPLIED")
    assert "if (__this_cpu_read(ksoftirqd) == current)" in new
    try:
        apply(old.replace(TOKEN, "rcu_softirq_qs();"))
    except ValueError as e:
        assert "CALL_COUNT=0" in str(e)
    else:
        raise AssertionError("accepted missing RCU call")
    print("EXP76_SOFTIRQ_NONRT_SELFTEST=PASS")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--tree",type=Path)
    p.add_argument("--report",type=Path)
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if args.self_test:
        self_test()
        return
    if args.tree is None or args.report is None:
        p.error("--tree and --report required")
    path=args.tree/REL
    if not path.is_file() or path.is_symlink():
        raise ValueError("BLOCKED_SOFTIRQ_SOURCE_NOT_REGULAR")
    raw=path.read_bytes()
    source=raw.decode("utf-8")
    new,status=apply(source)
    if status == "APPLIED":
        path.write_text(new,encoding="utf-8")
    report={
        "stage":"EXP76_QEMU_NONRT_RCU_SOFTIRQ_COMPAT",
        "status":status,"path":str(REL),"source_base":PIN,
        "source_sha256_before":sha(raw),
        "source_sha256_after":sha(new.encode("utf-8")),
        "rt_branch_keeps_rcu_bh_qs":True,
        "nonrt_branch_uses_vendor_rcu_softirq_qs":True,
        "qemu_nonrt_image_verified":False,
        "qemu_rt_guest_verified":False,
        "rt_handoff_ready":False
    }
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))

if __name__=="__main__":
    main()
