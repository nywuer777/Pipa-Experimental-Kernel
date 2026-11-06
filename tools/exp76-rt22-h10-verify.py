#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 GitHub Actions / E404 RT140 H10 semantic reconciliation gate / NO FLASH
"""Verify the exact upstream H10 removal is already satisfied in E404+RT140."""
import argparse
import hashlib
import json
import re
from pathlib import Path

def sha(blob):
    return hashlib.sha256(blob).hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tree", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    a = p.parse_args()
    source = a.tree / "kernel/sched/core.c"
    reject = a.tree / "kernel/sched/core.c.rej"
    code = source.read_text()
    raw = reject.read_text()
    blocks = re.split(r"(?=^@@ )", raw, flags=re.M)
    hunks = [b for b in blocks if b.startswith("@@ ")]
    if len(hunks) != 21:
        raise RuntimeError("Expected exactly 21 original scheduler rejected hunks")
    h10 = hunks[9]
    required = [
        "-\t/* If a worker is waking up, notify the workqueue: */",
        "-\tif (p->flags & PF_WQ_WORKER)",
        "-\t\twq_worker_waking_up(p, cpu_of(rq));",
    ]
    for line in required:
        if line not in h10:
            raise RuntimeError("H10 rejected deletion does not match pinned RT140: " + line)
    if "ttwu_activate" not in h10.splitlines()[0]:
        raise RuntimeError("H10 wrong target function")
    if not re.search(r"\bttwu_do_activate\s*\(", code):
        raise RuntimeError("E404 activation equivalent not found")
    if re.search(r"\bwq_worker_waking_up\s*\(", code):
        raise RuntimeError("H10 removed notification still present; manual port required")
    result = {
        "test_id": "EXP76_R22_H10_RT140_SOURCE_GATE",
        "hunk_id": "kernel/sched/core.c.rej#10",
        "hunk_header": h10.splitlines()[0],
        "hunk_sha256": sha(h10.encode()),
        "hunk_full_text": h10,
        "unchanged_context_first_three": [x[1:] for x in h10.splitlines()[1:] if x.startswith(" ")][:3],
        "full_hunk_lines": len(h10.splitlines()),
        "target_function_in_e404": "ttwu_do_activate",
        "rejected_file_sha256": sha(reject.read_bytes()),
        "source_sha256": sha(source.read_bytes()),
        "upstream_operation": "REMOVE wq_worker_waking_up from ttwu_activate",
        "e404_equivalent": "ttwu_do_activate",
        "target_notification_present": False,
        "status": "ALREADY_SATISFIED_SOURCE_NOOP",
        "source_change_applied": False,
        "build_verified": False,
        "boot_verified": False,
        "port_verified": False,
        "flash_ready": False,
    }
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
