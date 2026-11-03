#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage79 FunctionFS RT swait ABI / NO FLASH
"""Fix RT completion wait-queue inspection in FunctionFS only.

The E404 FunctionFS destructor passes completion.wait to waitqueue_active().
PREEMPT_RT_FULL uses swait_queue_head there; non-RT uses wait_queue_head.
Select the correct active-check API at compile time without changing teardown,
completion lifetime or normal wait queue behavior. The 64 rejects are evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

FILE = "drivers/usb/gadget/function/f_fs.c"
SWAIT = "include/linux/swait.h"
COMPLETION = "include/linux/completion.h"
SENTINEL = "kernel/sched/cpupri.c.rej"
INCLUDE_ANCHOR = "#include <linux/sched/signal.h>\n"
ADDED_INCLUDE = INCLUDE_ANCHOR + "#include <linux/swait.h>\n"
OLD = (
    "\t\tBUG_ON(waitqueue_active(&ffs->ev.waitq) ||\n"
    "\t\t       waitqueue_active(&ffs->ep0req_completion.wait) ||\n"
    "\t\t       waitqueue_active(&ffs->wait));\n"
)
NEW = (
    "\t\t/* The RT completion wait queue is an swait queue. */\n"
    "\t\tBUG_ON(waitqueue_active(&ffs->ev.waitq) ||\n"
    "\t\t       waitqueue_active(&ffs->wait));\n"
    "#ifdef CONFIG_PREEMPT_RT_FULL\n"
    "\t\tBUG_ON(swait_active(&ffs->ep0req_completion.wait));\n"
    "#else\n"
    "\t\tBUG_ON(waitqueue_active(&ffs->ep0req_completion.wait));\n"
    "#endif\n"
)
FUNCTION = "static void ffs_data_put(struct ffs_data *ffs)\n{\n"
RESULT = "stage79-status.json"


def exactly(source: str, needle: str, number: int, description: str) -> None:
    count = source.count(needle)
    if count != number:
        raise ValueError(
            f"{description}: expected {number} matches, found {count}"
        )


def prepare(tree: Path) -> tuple[str, dict]:
    if not (tree / ".git").is_dir():
        raise ValueError("Stage79 requires isolated E404 trial git checkout")
    for relative in (FILE, SWAIT, COMPLETION, SENTINEL):
        if not (tree / relative).is_file():
            raise ValueError("Stage79 source or outstanding RT reject missing: " + relative)
    rejects = len(list(tree.rglob("*.rej")))
    if rejects != 64:
        raise ValueError("Stage79 requires 64 outstanding PREEMPT_RT rejects")

    source = (tree / FILE).read_text(encoding="utf-8")
    exactly(source, FUNCTION, 1, "Pinned ffs_data_put() definition")
    exactly(source, INCLUDE_ANCHOR, 1, "Pinned FunctionFS include anchor")
    exactly(source, OLD, 1, "Pinned FunctionFS completion wait check")
    if "#include <linux/swait.h>" in source or NEW in source:
        raise ValueError("Stage79 FunctionFS source already patched")

    start = source.index(FUNCTION)
    end = source.find("\n}\n", start)
    if end < start:
        raise ValueError("Pinned FunctionFS destructor closing brace missing")
    body = source[start:end]
    exactly(body, OLD, 1, "Completion check inside ffs_data_put")
    exactly(body, "\t\tffs_data_clear(ffs);\n", 1, "FunctionFS cleanup sequence")
    exactly(body, "\t\tkfree(ffs);\n", 1, "FunctionFS final free")
    exactly(source, "\tinit_completion(&ffs->ep0req_completion);\n", 1,
            "FunctionFS completion initialisation")
    exactly(source, "wait_for_completion_interruptible(&ffs->ep0req_completion)", 1,
            "FunctionFS completion waiter")

    swait = (tree / SWAIT).read_text(encoding="utf-8")
    if swait.count(
        "static inline int swait_active(struct swait_queue_head *wq)"
    ) != 1:
        raise ValueError("Pinned RT swait_active() signature drift")
    completion = (tree / COMPLETION).read_text(encoding="utf-8")
    if "struct completion {" not in completion or "wait;" not in completion:
        raise ValueError("Pinned E404 completion wait member drift")
    # PREEMPT_RT modifies the completion wait head from wait to swait. Do
    # not reinterpret its data structure or silently cast between the APIs.
    if "struct swait_queue_head" not in completion:
        raise ValueError("Stage79 requires RT swait completion definition")

    patched = source.replace(INCLUDE_ANCHOR, ADDED_INCLUDE, 1).replace(
        OLD, NEW, 1
    )
    expected = patched.replace(ADDED_INCLUDE, INCLUDE_ANCHOR, 1).replace(
        NEW, OLD, 1
    )
    if expected != source:
        raise ValueError("Stage79 touched FunctionFS code outside guarded wait check")
    return patched, {
        "stage": "EXP76_STAGE79_FUNCTIONFS_RT_COMPLETION_SWAIT_NONFLASH",
        "target": FILE,
        "rt_completion_swait_used": True,
        "nonrt_waitqueue_preserved": True,
        "normal_waitqueue_checks_preserved": True,
        "completion_lifecycle_preserved": True,
        "existing_swait_api_verified": True,
        "remaining_rejected_files": 64,
        "full_kernel_link_performed": False,
        "runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
        "original_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "patched_sha256": hashlib.sha256(patched.encode()).hexdigest(),
    }


def execute(tree: Path, report: Path, mode: str) -> dict:
    if mode not in ("verify", "apply"):
        raise ValueError("Stage79 accepts verify/apply only")
    patched, result = prepare(tree)
    if mode == "apply":
        (tree / FILE).write_text(patched, encoding="utf-8")
        if (tree / FILE).read_text(encoding="utf-8") != patched:
            raise ValueError("Stage79 post-write source integrity failed")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage79 modified RT reject evidence")
    result["applied"] = mode == "apply"
    report.mkdir(parents=True, exist_ok=True)
    (report / RESULT).write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = parser.parse_args()
    print(json.dumps(execute(
        args.tree.resolve(), args.report.resolve(), args.mode,
    ), indent=2))


if __name__ == "__main__":
    main()
