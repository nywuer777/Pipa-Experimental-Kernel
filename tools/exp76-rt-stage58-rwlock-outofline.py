#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage58 RT rwlock out-of-line waiter query / NO FLASH
"""Move the Stage57 RT waiter query out of the header into rwlock-rt.c.

rwlock_rt.h is parsed while spinlock.h is assembling its generic lock API.
Using raw_spin_lock_irqsave() in an inline body there expands to undeclared
_raw_spin_lock_irqsave, failing the arm64 prepare gate before any object.
Keep the exact waiter-protected query but implement it in the already-built
RT rwlock translation unit where raw spinlock APIs are fully declared.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

HEADER = "include/linux/rwlock_rt.h"
SOURCE = "kernel/locking/rwlock-rt.c"
RT_MUTEX = "include/linux/rtmutex.h"
REJECT = "kernel/sched/cpupri.c.rej"

STAGE57_HELPER = (
    "/* Match rwlock_is_contended() from non-RT rwlock.h for RT zsmalloc. */\n"
    "static inline int rwlock_is_contended(rwlock_t *rwlock)\n"
    "{\n"
    "\tstruct rt_mutex *mutex = &rwlock->rtmutex;\n"
    "\tunsigned long flags;\n"
    "\tint pending;\n\n"
    "\traw_spin_lock_irqsave(&mutex->wait_lock, flags);\n"
    "\tpending = !RB_EMPTY_ROOT(&mutex->waiters.rb_root);\n"
    "\traw_spin_unlock_irqrestore(&mutex->wait_lock, flags);\n"
    "\treturn pending;\n"
    "}\n\n"
)
HEADER_DECL = (
    "/* Implemented after spinlock API declarations in rwlock-rt.c. */\n"
    "extern int rwlock_is_contended(rwlock_t *rwlock);\n\n"
)
SOURCE_INCLUDE = "#include <linux/rwlock_types_rt.h>\n"
SOURCE_FUNC = (
    "\n/* Inspect PI waiters under the raw rtmutex lock; preserves Stage57 logic. */\n"
    "int rwlock_is_contended(rwlock_t *rwlock)\n"
    "{\n"
    "\tstruct rt_mutex *mutex = &rwlock->rtmutex;\n"
    "\tunsigned long flags;\n"
    "\tint pending;\n\n"
    "\traw_spin_lock_irqsave(&mutex->wait_lock, flags);\n"
    "\tpending = !RB_EMPTY_ROOT(&mutex->waiters.rb_root);\n"
    "\traw_spin_unlock_irqrestore(&mutex->wait_lock, flags);\n"
    "\treturn pending;\n"
    "}\n"
    "EXPORT_SYMBOL_GPL(rwlock_is_contended);\n"
)


def one(source: str, fragment: str, what: str) -> None:
    count = source.count(fragment)
    if count != 1:
        raise ValueError(f"{what}: expected one pinned fragment, found {count}")


def prepare(tree: Path) -> tuple[dict[str, str], dict]:
    if not (tree / ".git").is_dir():
        raise ValueError("Expected isolated E404 RT git checkout")
    for path in (HEADER, SOURCE, RT_MUTEX, REJECT):
        if not (tree / path).is_file():
            raise ValueError("Missing RT source or rejection: " + path)
    rejects = len(list(tree.rglob("*.rej")))
    if rejects != 64:
        raise ValueError(f"Expected 64 outstanding RT reject files, found {rejects}")
    original = {name: (tree / name).read_text(encoding="utf-8")
                for name in (HEADER, SOURCE, RT_MUTEX)}
    header, source = original[HEADER], original[SOURCE]
    one(header, STAGE57_HELPER, "Original Stage57 inline RT waiter query")
    one(header, "void __read_rt_unlock(struct rt_rw_lock *lock);",
        "Pinned RT rwlock header API")
    one(source, SOURCE_INCLUDE, "Pinned rwlock-rt.c source includes")
    one(source, "void __read_rt_unlock(struct rt_rw_lock *lock)",
        "Existing RT rwlock writer/reader implementation")
    one(source, "#include <linux/export.h>\n",
        "RT locking module export header")
    if "rwlock_is_contended(" in source:
        raise ValueError("Out-of-line RT waiter query already defined")
    if "EXPORT_SYMBOL_GPL(rwlock_is_contended)" in source:
        raise ValueError("RT waiter query symbol already exported")
    mutex = original[RT_MUTEX]
    one(mutex, "raw_spinlock_t\t\twait_lock;",
        "rt_mutex raw wait_lock declaration")
    one(mutex, "struct rb_root_cached   waiters;",
        "rt_mutex PI waiter tree representation")
    changes = {
        HEADER: header.replace(STAGE57_HELPER, HEADER_DECL, 1),
        SOURCE: source.replace(SOURCE_INCLUDE, SOURCE_INCLUDE + SOURCE_FUNC, 1),
    }
    one(changes[HEADER], HEADER_DECL, "RT header extern declaration")
    one(changes[SOURCE], SOURCE_FUNC, "Out-of-line raw-spinlock waiter query")
    if "raw_spin_lock_irqsave(&mutex->wait_lock" in changes[HEADER]:
        raise ValueError("Raw spinlock implementation must not remain in header")
    if changes[SOURCE].count("rwlock_is_contended(") != 1:
        raise ValueError("RT rwlock contention symbol has duplicate definitions")
    return changes, {
        "stage": "EXP76_STAGE58_OUT_OF_LINE_RT_RWLOCK_WAITER_QUERY_NONFLASH",
        "rt_waiter_query_out_of_header": True,
        "raw_spinlock_query_and_unlock_preserved": True,
        "rt_mutex_waiter_tree_access_unchanged": True,
        "rwlock_query_exported_for_modules": True,
        "remaining_rejected_files": rejects,
        "kernel_built": False,
        "runtime_verified": False,
        "flash_ready": False,
        "original_sha256": {name: hashlib.sha256(body.encode()).hexdigest()
                            for name, body in original.items() if name != RT_MUTEX},
        "patched_sha256": {name: hashlib.sha256(body.encode()).hexdigest()
                           for name, body in changes.items()},
    }


def execute(tree: Path, report: Path, mode: str) -> dict:
    if mode not in ("verify", "apply"):
        raise ValueError("Stage58 mode must be verify or apply")
    changes, result = prepare(tree)
    if mode == "apply":
        for name, body in changes.items():
            (tree / name).write_text(body, encoding="utf-8")
        if any((tree / name).read_text(encoding="utf-8") != body
               for name, body in changes.items()):
            raise ValueError("Stage58 post-write verification failed")
    if len(list(tree.rglob("*.rej"))) != 64:
        raise ValueError("Stage58 changed outstanding RT reject files")
    result["applied"] = mode == "apply"
    report.mkdir(parents=True, exist_ok=True)
    (report / "stage58-status.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tree", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--mode", choices=("verify", "apply"), required=True)
    a = p.parse_args()
    print(json.dumps(execute(a.tree.resolve(), a.report.resolve(), a.mode), indent=2))


if __name__ == "__main__":
    main()
