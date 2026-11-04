#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage93 RT RCU ABI + linked exports / NO FLASH
"""Audit E404 unified RCU/RT compatibility against real linked vmlinux.

Do not apply 4.19.325-rt140 RCU tree hunks to the newer E404 RCU:
18 pending tree.c hunks are preserved and remain manually unresolved.
Prove upstream legacy-bh forwarding, RT lockdep inline selection, balanced
preprocessor guards, and linked grace-period/read-side export existence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

STAGE = "EXP76_STAGE93_UNIFIED_RCU_RT_LINK_AND_API_CONTRACT_NONFLASH"
REPORT = "stage93-status.json"
INDEX_STAGE = "EXP76_STAGE82_OUTSTANDING_RT_REJECT_HUNK_INVENTORY_NONFLASH"
STAGE47 = "EXP76_STAGE47_RCU_PREPROCESSOR_AND_WORKQUEUE_RAW_LOCK"
STAGE92 = "EXP76_STAGE92_RT_MIGRATION_ABI_SYMBOL_CROSSCHECK_NONFLASH"
TREE_REJECT = "kernel/rcu/tree.c.rej"
TREE_REJECT_SHA = "2de3a79ea9ac2eb3f2eb6ac6a603614e591ba84600cd5b6c36ce0298471b9cd2"
TREE_REJECT_HUNKS = 18
PATHS = (
    "kernel/rcu/tree.c", "kernel/rcu/tree_plugin.h", "kernel/rcu/update.c",
    "include/linux/rcupdate.h", "include/linux/rcutree.h",
)
EXPORTS = (
    "synchronize_rcu", "rcu_barrier",
    "__rcu_read_lock", "__rcu_read_unlock",
)
FORWARDERS = {
    "synchronize_rcu_bh": "synchronize_rcu",
    "rcu_barrier_bh": "rcu_barrier",
    "call_rcu_bh": "call_rcu",
}
CHECKS = {
    "unified_rcu_segcblist": ("kernel/rcu/tree.c", "rcu_segcblist"),
    "unified_rcu_core": ("kernel/rcu/tree.c", "void rcu_core(void)"),
    "unified_synchronize_rcu": ("kernel/rcu/tree.c", "void synchronize_rcu(void)"),
    "unified_rcu_barrier": ("kernel/rcu/tree.c", "void rcu_barrier(void)"),
    "preempt_rcu_read_lock": ("kernel/rcu/tree_plugin.h", "void __rcu_read_lock(void)"),
    "preempt_rcu_read_unlock": ("kernel/rcu/tree_plugin.h", "void __rcu_read_unlock(void)"),
    "preempt_deferred_qs": ("kernel/rcu/tree_plugin.h", "rcu_preempt_deferred_qs("),
    "preempt_special_unlock": ("kernel/rcu/tree_plugin.h", "rcu_read_unlock_special("),
    "rt_lockdep_wrapper": (
        "include/linux/rcupdate.h",
        "#ifdef CONFIG_PREEMPT_RT_FULL\nstatic inline int rcu_read_lock_bh_held(void)"
    ),
    "rt_lockdep_forward": (
        "include/linux/rcupdate.h", "\treturn rcu_read_lock_held();"
    ),
    "non_rt_lockdep_implementation": (
        "kernel/rcu/update.c", "int rcu_read_lock_bh_held(void)"
    ),
    "non_rt_lockdep_export": (
        "kernel/rcu/update.c", "EXPORT_SYMBOL_GPL(rcu_read_lock_bh_held);"
    ),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_stage(path: Path, stage: str) -> dict:
    if not path.is_file():
        raise ValueError("Stage93 required prior evidence missing: " + str(path))
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("stage") != stage:
        raise ValueError("Stage93 prior evidence stage mismatch: " + stage)
    return obj


def check_preprocessor(text: str, file: str) -> tuple[int, int]:
    stack: list[tuple[int, str, bool]] = []
    count = 0
    for number, line in enumerate(text.splitlines(), 1):
        token = re.match(r"^\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b", line)
        if token is None:
            continue
        kind = token.group(1)
        if kind in ("if", "ifdef", "ifndef"):
            stack.append((number, kind, False))
            count += 1
        elif kind in ("elif", "else"):
            if not stack:
                raise ValueError(f"Stage93 preprocessor orphan {kind}: {file}:{number}")
            start, previous, had_else = stack[-1]
            if had_else:
                raise ValueError(f"Stage93 #elif/#else after #else: {file}:{number}")
            stack[-1] = (start, previous, kind == "else")
        else:
            if not stack:
                raise ValueError(f"Stage93 orphan #endif: {file}:{number}")
            stack.pop()
    if stack:
        raise ValueError(f"Stage93 unclosed preprocessor directive: {file}:{stack[-1][0]}")
    return count, 0


def mapped_symbols(system_map: Path) -> tuple[list[str], list[str]]:
    if not system_map.is_file():
        raise ValueError("Stage93 actual linked System.map missing")
    names: dict[str, set[str]] = {x: set() for x in EXPORTS}
    for row in system_map.read_text(encoding="utf-8", errors="replace").splitlines():
        columns = row.split()
        if len(columns) != 3:
            continue
        address, kind, symbol = columns
        if (symbol in names and kind in ("T", "t", "W", "w")
                and re.fullmatch(r"[0-9a-fA-F]+", address)):
            names[symbol].add(address)
    found = [n for n in EXPORTS if len(names[n]) == 1]
    missing = [n for n in EXPORTS if len(names[n]) != 1]
    return found, missing


def execute(tree: Path, output: Path, inventory: Path,
            stage47_path: Path, stage92_path: Path, report: Path) -> dict:
    if not (tree / ".git").is_dir():
        raise ValueError("Stage93 requires isolated pinned E404 Git tree")
    if (len(list(tree.rglob("*.rej"))) != 64
            or not (tree / "kernel/sched/cpupri.c.rej").is_file()):
        raise ValueError("Stage93 all original 64 RT rejects must remain present")
    reject = tree / TREE_REJECT
    if not reject.is_file() or sha(reject) != TREE_REJECT_SHA:
        raise ValueError("Stage93 18-hunk RCU original rejection SHA256 drift")
    if not inventory.is_file():
        raise ValueError("Stage93 requires immutable Stage82 RT inventory")
    index = json.loads(inventory.read_text(encoding="utf-8"))
    entry = [
        item for item in index.get("entries", [])
        if item.get("source") == "kernel/rcu/tree.c"
    ]
    if not (
        index.get("stage") == INDEX_STAGE
        and index.get("remaining_rejected_files") == 64
        and index.get("source_modified") is False
        and index.get("rejects_deleted") is False
        and len(entry) == 1
        and entry[0].get("reject_sha256") == TREE_REJECT_SHA
        and entry[0].get("hunk_count") == TREE_REJECT_HUNKS
    ):
        raise ValueError("Stage93 Stage82 RCU reject provenance mismatch")
    stage47 = load_stage(stage47_path, STAGE47)
    if not (
        stage47.get("applied") is True
        and stage47.get("rcu_postpatch_preprocessor_balanced") is True
        and stage47.get("remaining_rejected_files") == 64
        and stage47.get("rcu_runtime_verified") is False
    ):
        raise ValueError("Stage93 RCU Stage47 conditional audit not proven")
    stage92 = load_stage(stage92_path, STAGE92)
    if not (
        stage92.get("arm64_stage86_image_link_verified") is True
        and stage92.get("smp_preempt_rt_full_config_verified") is True
        and stage92.get("system_map_symbols_missing") == []
        and stage92.get("verification_scope") == "SOURCE_AND_LINK_ONLY"
        and stage92.get("remaining_rejected_files") == 64
        and stage92.get("device_boot_verified") is False
    ):
        raise ValueError("Stage93 previous actual ARM64 linked baseline invalid")
    config = output / ".config"
    if not config.is_file():
        raise ValueError("Stage93 real kernel .config absent")
    settings = set(config.read_text(encoding="utf-8").splitlines())
    if "CONFIG_PREEMPT_RT_FULL=y" not in settings or "CONFIG_SMP=y" not in settings:
        raise ValueError("Stage93 requires real PREEMPT_RT_FULL SMP .config")
    elf = output / "vmlinux"
    if not elf.is_file() or elf.open("rb").read(4) != b"\x7fELF":
        raise ValueError("Stage93 linked vmlinux ELF missing")
    source = {}
    source_sha = {}
    for path in PATHS:
        p = tree / path
        if not p.is_file():
            raise ValueError("Stage93 E404 RCU source absent: " + path)
        source[path] = p.read_text(encoding="utf-8")
        source_sha[path] = sha(p)
    for label, (path, token) in CHECKS.items():
        if token not in source[path]:
            raise ValueError("Stage93 unified RCU invariant violated: " + label)
    if re.search(r"\b(?:struct\s+rcu_state)\s+(?:rcu_bh_state|rcu_sched_state)\b",
                 source["kernel/rcu/tree.c"]):
        raise ValueError("Stage93 incompatible legacy RCU flavor state reintroduced")
    rcupdate = source["include/linux/rcupdate.h"]
    for alias, target in FORWARDERS.items():
        pattern = (
            r"static\s+inline\s+void\s+" + alias +
            r"\s*\([^)]*\)\s*\{\s*" +
            re.escape(target) + r"\s*\([^;]*\);\s*\}"
        )
        if len(re.findall(pattern, rcupdate)) != 1:
            raise ValueError("Stage93 E404 unified RCU forwarding drift: " + alias)
    update = source["kernel/rcu/update.c"]
    position = update.index("int rcu_read_lock_bh_held(void)")
    if "#ifndef CONFIG_PREEMPT_RT_FULL" not in update[:position]:
        raise ValueError("Stage93 RT lockdep out-of-line implementation unguarded")
    if (rcupdate.count("static inline int rcu_read_lock_bh_held(void)") < 1
            or "return rcu_read_lock_held();" not in rcupdate):
        raise ValueError("Stage93 RT inline lockdep helper changed")
    guarded = {}
    for path in ("kernel/rcu/update.c", "kernel/rcu/tree_plugin.h"):
        n, trailing = check_preprocessor(source[path], path)
        guarded[path] = {"directives_opened": n, "unclosed": trailing}
    found, missing = mapped_symbols(output / "System.map")
    if missing:
        raise ValueError("Stage93 unified RCU exports absent from linked kernel: " +
                         ", ".join(missing))
    if sha(output / "System.map") != stage92.get("system_map_sha256"):
        raise ValueError("Stage93 linked System.map drift versus Stage92 baseline")
    if sha(elf) != stage92.get("vmlinux_elf_sha256"):
        raise ValueError("Stage93 linked vmlinux drift versus Stage92 baseline")
    data = {
        "stage": STAGE,
        "rt_config_verified": True,
        "stage47_rcu_preprocessor_guard_proven": True,
        "stage92_linked_kernel_proven": True,
        "unified_rcu_source_invariants": list(CHECKS),
        "unified_rcu_source_invariant_count": len(CHECKS),
        "unified_rcu_bh_forwarders": FORWARDERS,
        "rcu_preprocessor": guarded,
        "linked_rcu_exports_present": found,
        "linked_rcu_exports_missing": missing,
        "source_sha256": source_sha,
        "system_map_sha256": sha(output / "System.map"),
        "vmlinux_elf_sha256": sha(elf),
        "original_rcu_tree_reject_sha256": TREE_REJECT_SHA,
        "original_rcu_tree_rejected_hunks_pending": TREE_REJECT_HUNKS,
        "original_rejected_files_remaining": 64,
        "verification_scope": "SOURCE_AND_LINK_ONLY",
        "rt_rcu_runtime_semantics_verified": False,
        "rcu_grace_period_runtime_verified": False,
        "device_boot_verified": False,
        "kernel_built": False,
        "flash_ready": False,
    }
    report.mkdir(parents=True, exist_ok=True)
    (report / REPORT).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--inventory", required=True, type=Path)
    p.add_argument("--stage47-report", required=True, type=Path)
    p.add_argument("--stage92-report", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(execute(
        a.tree.resolve(), a.output.resolve(), a.inventory.resolve(),
        a.stage47_report.resolve(), a.stage92_report.resolve(), a.report.resolve()
    ), indent=2))


if __name__ == "__main__":
    main()
