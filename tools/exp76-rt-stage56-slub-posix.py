#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 GitHub Actions / EXP76 Stage56 SLUB IRQ and POSIX NONRT warning ABI / NO FLASH
"""Complete exact RT SLUB IRQ symmetry and restore a missing upstream RT WARN macro.

The partial 4.19.325-rt140 SLUB hunk changes the IRQ exit to enableirqs
without porting its definition and entry predicate into E404. The POSIX
CPU-timer RT path uses WARN_ON_ONCE_NONRT, whose macro definition is absent
from E404 asm-generic/bug.h. Port both original RT contracts, fail closed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

SLUB = "mm/slub.c"
BUG = "include/asm-generic/bug.h"
REJECT = "kernel/sched/cpupri.c.rej"
SLUB_OLD = (
    "\tbool shuffle;\n\n"
    "\tflags &= gfp_allowed_mask;\n\n"
    "\tif (gfpflags_allow_blocking(flags))\n"
    "\t\tlocal_irq_enable();\n\n"
    "\tflags |= s->allocflags;\n"
)
SLUB_NEW = (
    "\tbool shuffle;\n"
    "\tbool enableirqs = false;\n\n"
    "\tflags &= gfp_allowed_mask;\n\n"
    "\tif (gfpflags_allow_blocking(flags))\n"
    "\t\tenableirqs = true;\n"
    "#ifdef CONFIG_PREEMPT_RT_FULL\n"
    "\tif (system_state > SYSTEM_BOOTING)\n"
    "\t\tenableirqs = true;\n"
    "#endif\n"
    "\tif (enableirqs)\n"
    "\t\tlocal_irq_enable();\n\n"
    "\tflags |= s->allocflags;\n"
)
SLUB_EXIT = (
    "out:\n"
    "\tif (enableirqs)\n"
    "\t\tlocal_irq_disable();\n"
    "\tif (!page)\n"
    "\t\treturn NULL;\n"
)
WARN_ANCHOR = "#endif /* __ASSEMBLY__ */\n\n#endif\n"
WARN_BLOCK = (
    "/* PREEMPT_RT may run POSIX CPU timer processing in thread context. */\n"
    "#ifdef CONFIG_PREEMPT_RT_BASE\n"
    "# define WARN_ON_ONCE_NONRT(condition) do { } while (0)\n"
    "#else\n"
    "# define WARN_ON_ONCE_NONRT(condition) WARN_ON_ONCE(condition)\n"
    "#endif\n\n"
)
TIMER = "kernel/time/posix-cpu-timers.c"


def one(src: str, fragment: str, label: str) -> None:
    n = src.count(fragment)
    if n != 1:
        raise ValueError(f"{label}: expected exactly one pinned fragment, got {n}")


def prepare(tree: Path) -> tuple[dict[str, str], dict]:
    if not (tree / ".git").is_dir():
        raise ValueError("Stage56 requires isolated E404 git checkout")
    for name in (SLUB, BUG, TIMER, REJECT):
        if not (tree / name).is_file():
            raise ValueError("Stage56 required RT source/reject missing: " + name)
    rejects = len(list(tree.rglob("*.rej")))
    if rejects != 64:
        raise ValueError(f"Expected 64 unresolved RT rejects, found {rejects}")
    slub = (tree / SLUB).read_text(encoding="utf-8")
    bug = (tree / BUG).read_text(encoding="utf-8")
    timer = (tree / TIMER).read_text(encoding="utf-8")
    one(slub, "static struct page *allocate_slab(struct kmem_cache *s, gfp_t flags, int node)\n",
        "E404 SLUB allocate_slab")
    one(slub, SLUB_OLD, "Partial RT SLUB IRQ entry")
    one(slub, SLUB_EXIT, "Applied RT SLUB IRQ exit")
    if "bool enableirqs" in slub:
        raise ValueError("SLUB enableirqs already declared")
    one(bug, WARN_ANCHOR, "E404 asm-generic warning macro insertion")
    if "WARN_ON_ONCE_NONRT" in bug:
        raise ValueError("WARN_ON_ONCE_NONRT already defined")
    one(bug, "# define WARN_ON_SMP(x)", "Warning macro presence")
    if not ("#ifdef CONFIG_PREEMPT_RT_BASE" in timer and
            "WARN_ON_ONCE_NONRT(!irqs_disabled());" in timer):
        raise ValueError("E404 RT threaded POSIX timer warning consumer missing")
    fixed = {
        SLUB: slub.replace(SLUB_OLD, SLUB_NEW, 1),
        BUG: bug.replace(WARN_ANCHOR, WARN_BLOCK + WARN_ANCHOR, 1),
    }
    one(fixed[SLUB], SLUB_EXIT, "Preserved RT SLUB IRQ exit")
    one(fixed[SLUB], SLUB_NEW, "Complete RT SLUB IRQ entry")
    one(fixed[BUG], WARN_BLOCK, "RT and nonRT warning semantics")
    return fixed, {
        "stage": "EXP76_STAGE56_SLUB_IRQ_POSIX_NONRT_WARN_NONFLASH",
        "slub_irq_entry_exit_predicate_matched": True,
        "slub_rt_boot_state_gate_preserved": True,
        "posix_rt_nonrt_warning_macro_defined": True,
        "posix_cpu_timer_warning_consumer_verified": True,
        "remaining_rejected_files": rejects,
        "runtime_verified": False,
        "kernel_built": False,
        "flash_ready": False,
        "source_sha256": {name: hashlib.sha256((tree / name).read_bytes()).hexdigest()
                          for name in (SLUB, BUG, TIMER)},
        "patched_sha256": {name: hashlib.sha256(s.encode()).hexdigest()
                           for name, s in fixed.items()},
    }


def execute(tree: Path, report: Path, mode: str) -> dict:
    if mode not in ("apply", "verify"):
        raise ValueError("Stage56 mode must be apply or verify")
    edits, info = prepare(tree)
    if mode == "apply":
        for name, body in edits.items():
            (tree / name).write_text(body, encoding="utf-8")
        if any((tree / name).read_text(encoding="utf-8") != body
               for name, body in edits.items()):
            raise ValueError("Stage56 written source failed integrity check")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage56 changed unresolved RT reject count")
    info["applied"] = mode == "apply"
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage56-status.json").write_text(
        json.dumps(info, indent=2) + "\n", encoding="utf-8"
    )
    return info


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = p.parse_args()
    print(json.dumps(execute(args.tree.resolve(), args.report.resolve(), args.mode), indent=2))


if __name__ == "__main__":
    main()
