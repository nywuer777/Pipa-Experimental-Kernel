#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / record exact PREEMPT_RT rejected hunks per subsystem
"""EXP76 audit: collect raw .rej hunks and produce review priorities, without applying fixes."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path

P0 = {
    "kernel/sched/core.c", "kernel/sched/fair.c",
    "kernel/locking/rtmutex.c", "kernel/locking/spinlock.c",
    "kernel/rcu/tree.c", "kernel/softirq.c",
    "kernel/time/hrtimer.c", "include/linux/spinlock_types.h",
    "arch/arm64/include/asm/thread_info.h",
}
P1 = ("kernel/sched/", "kernel/locking/", "kernel/rcu/", "kernel/irq/",
      "kernel/softirq.c", "kernel/futex.c", "kernel/workqueue.c",
      "kernel/time/", "arch/arm64/", "include/linux/", "init/")
AREAS = (
    ("kernel/sched/", "sched"), ("kernel/locking/", "locking"),
    ("kernel/rcu/", "rcu"), ("kernel/irq/", "irq"),
    ("kernel/time/", "time"), ("arch/arm64/", "arm64"),
    ("include/linux/", "headers"), ("drivers/", "drivers"),
    ("kernel/", "other-kernel"), ("mm/", "mm"), ("fs/", "fs"),
    ("arch/", "other-arch"),
)
def priority(p: str) -> str:
    return "P0" if p in P0 else ("P1" if p.startswith(P1) else "P2")

def area(p: str) -> str:
    return next((v for k,v in AREAS if p.startswith(k)), "other")

def scan(trial: Path, pathsfile: Path, output: Path):
    paths = pathsfile.read_text(encoding="utf-8").splitlines()
    if not paths or len(paths) != len(set(paths)):
        raise ValueError("Missing/duplicate reject manifest")
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in sorted(paths):
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or str(path).startswith("."):
            raise ValueError("Unsafe manifest path: " + name)
        rej = trial / (name + ".rej")
        if not rej.is_file():
            raise ValueError("Missing reject file: " + str(rej))
        body = rej.read_bytes()
        hunks = sum(bool(re.match(r"^@@ -\d+", line)) for line in
                    body.decode("utf-8", errors="replace").splitlines())
        if hunks < 1:
            raise ValueError("Reject contains no hunk: " + name)
        rank = priority(name)
        if rank != "P2":
            dest = output / "critical-rejects" / (name + ".rej")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(rej, dest)
        rows.append(dict(file=name, area=area(name), priority=rank,
                         rejected_hunks=hunks, bytes=len(body),
                         sha256=hashlib.sha256(body).hexdigest()))
    rows.sort(key=lambda r: (r["priority"],r["area"],r["file"]))
    with (output / "manifest.csv").open("w", newline="", encoding="utf-8") as fd:
        writer = csv.DictWriter(fd, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (output / "manifest.json").write_text(json.dumps(rows, indent=2)+"\n")
    counts = Counter(r["area"] for r in rows)
    ranks = Counter(r["priority"] for r in rows)
    lines = [
        "# EXP76 exact RT rejected hunks",
        "",
        "Status: report only, no automatic integration or kernel build.",
        "",
        f"Files with rejections: {len(rows)}",
        f"Total rejected hunks: {sum(r['rejected_hunks'] for r in rows)}",
        f"P0: {ranks['P0']} files; P1: {ranks['P1']} files; P2: {ranks['P2']} files.",
        "",
        "## Subsystems",
        "",
        "| Subsystem | Files |", "| --- | ---: |",
    ]
    lines += ["| "+key+" | "+str(value)+" |" for key,value in sorted(counts.items())]
    lines += ["", "## P0 first", "", "| File | Rejected hunks |",
              "| --- | ---: |"]
    lines += ["| "+r["file"]+" | "+str(r["rejected_hunks"])+" |"
              for r in rows if r["priority"] == "P0"]
    lines += ["", "P0/P1 .rej files copied intact to critical-rejects/.",
              "Semantic review required. FLASH_READY=false.", ""]
    (output / "SUMMARY.md").write_text("\n".join(lines))
    return dict(files=len(rows),hunks=sum(r["rejected_hunks"] for r in rows),
                priorities=dict(ranks))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--e404-trial", type=Path, required=True)
    p.add_argument("--e404-paths", type=Path, required=True)
    p.add_argument("--overlay-trial", type=Path, required=True)
    p.add_argument("--overlay-paths", type=Path, required=True)
    a = p.parse_args()
    e = scan(a.e404_trial,a.e404_paths,a.report / "e404-hunks")
    o = scan(a.overlay_trial,a.overlay_paths,a.report / "overlay-hunks")
    if e["files"] != o["files"]:
        raise ValueError("E404 and overlay conflict counts differ")
    print(json.dumps(dict(e404=e,overlay=o),indent=2))
    (a.report / "CONFLICT_REPORT_STATUS.txt").write_text(
        "EXP76_RT_CONFLICT_MANIFEST=PASS\n"
        "EXP76_RT_PATCH_INTEGRATED=false\n"
        "FLASH_READY=false\n"
    )

if __name__ == "__main__":
    main()
