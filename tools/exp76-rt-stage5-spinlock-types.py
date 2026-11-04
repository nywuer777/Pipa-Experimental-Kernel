#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 RT Stage5 spinlock type split with vendor lockdep semantics
"""Source-only relocation of E404 spinlock types into upstream RT split headers.

Preserves vendor RAW LD_WAIT_SPIN vs normal LD_WAIT_CONFIG and the
non-RT spinlock initializer. No CONFIG_PREEMPT_RT, build, or flash.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

HEADER = "include/linux/spinlock_types.h"
RAW = "include/linux/spinlock_types_raw.h"
NORT = "include/linux/spinlock_types_nort.h"
RT = "include/linux/spinlock_types_rt.h"
REJECT_SHA = "a15e8b5faf0abcdce61b99b1409a0359e94cf34eba098b3f22fdc34f03ff0599"
END = "#endif /* __LINUX_SPINLOCK_TYPES_H */\n"

RAW_INIT = (
    "# define RAW_SPIN_DEP_MAP_INIT(lockname)\t\t\\\n"
    "\t.dep_map = {\t\t\t\t\t\\\n"
    "\t\t.name = #lockname,\t\t\t\\\n"
    "\t\t.wait_type_inner = LD_WAIT_SPIN,\t\\\n"
    "\t}\n"
)
NORMAL_INIT = (
    "# define SPIN_DEP_MAP_INIT(lockname)\t\t\t\\\n"
    "\t.dep_map = {\t\t\t\t\t\\\n"
    "\t\t.name = #lockname,\t\t\t\\\n"
    "\t\t.wait_type_inner = LD_WAIT_CONFIG,\t\\\n"
    "\t}\n"
)
NORT_INIT = (
    "#define ___SPIN_LOCK_INITIALIZER(lockname)\t\\\n"
    "\t{\t\t\t\t\t\\\n"
    "\t.raw_lock = __ARCH_SPIN_LOCK_UNLOCKED,\t\\\n"
    "\tSPIN_DEBUG_INIT(lockname)\t\t\\\n"
    "\tSPIN_DEP_MAP_INIT(lockname) }\n\n"
)
TOP = (
    "#include <linux/spinlock_types_raw.h>\n\n"
    "#ifdef CONFIG_DEBUG_LOCK_ALLOC\n"
    + NORMAL_INIT
    + "#else\n"
    "# define SPIN_DEP_MAP_INIT(lockname)\n"
    "#endif\n\n"
    "#ifndef CONFIG_PREEMPT_RT_FULL\n"
    "# include <linux/spinlock_types_nort.h>\n"
    "# include <linux/rwlock_types.h>\n"
    "#else\n"
    "# include <linux/rtmutex.h>\n"
    "# include <linux/spinlock_types_rt.h>\n"
    "# include <linux/rwlock_types_rt.h>\n"
    "#endif\n\n"
)


def changes(tree: Path):
    reject = tree / (HEADER + ".rej")
    if not reject.is_file():
        raise ValueError("Missing pinned spinlock_types.h reject")
    sha = hashlib.sha256(reject.read_bytes()).hexdigest()
    if sha != REJECT_SHA:
        raise ValueError("Unknown spinlock_types.h reject SHA: " + sha)
    paths = (HEADER, RAW, NORT, RT)
    before = {name: (tree/name).read_text(encoding="utf-8") for name in paths}
    old = before[HEADER]
    if old.count("#if defined(CONFIG_SMP)\n") != 1 or old.count(END) != 1:
        raise ValueError("Unknown vendor spinlock_types.h boundaries")
    if old.count("LD_WAIT_SPIN") != 1 or old.count("LD_WAIT_CONFIG") != 1:
        raise ValueError("Vendor lockdep wait type definitions changed")
    if not all(x in old for x in ("RAW_SPIN_DEP_MAP_INIT", "SPIN_DEP_MAP_INIT",
                                  "___SPIN_LOCK_INITIALIZER", "DEFINE_SPINLOCK")):
        raise ValueError("Missing vendor ABI initialization tokens")
    prefix = old[:old.index("#if defined(CONFIG_SMP)\n")]
    if not prefix.startswith("#ifndef __LINUX_SPINLOCK_TYPES_H\n"):
        raise ValueError("Unexpected top header include guard")
    after = {HEADER: prefix + TOP + END}

    raw = before[RAW]
    original = "# define SPIN_DEP_MAP_INIT(lockname)\t.dep_map = { .name = #lockname }\n"
    if raw.count(original) != 1 or raw.count("# define SPIN_DEP_MAP_INIT(lockname)\n") != 1:
        raise ValueError("Unexpected upstream raw depmap macro")
    if raw.count("SPIN_DEP_MAP_INIT(lockname)") != 3:
        raise ValueError("Expected two raw macros plus initializer usage")
    raw = raw.replace(original, RAW_INIT, 1)
    raw = raw.replace("SPIN_DEP_MAP_INIT(lockname)", "RAW_SPIN_DEP_MAP_INIT(lockname)")
    # Replacement above also affects RAW_SPIN_DEP_MAP_INIT just introduced:
    # normalize ONLY the overprefixed spelling to the one true definition.
    raw = raw.replace("RAW_RAW_SPIN_DEP_MAP_INIT(", "RAW_SPIN_DEP_MAP_INIT(")
    if raw.count("RAW_SPIN_DEP_MAP_INIT(lockname)") != 3:
        raise ValueError("Unexpected raw lockdep macro reference count")
    if "wait_type_inner = LD_WAIT_SPIN" not in raw:
        raise ValueError("Lost raw lockdep wait type")
    after[RAW] = raw

    nort = before[NORT]
    old_ref = "__RAW_SPIN_LOCK_INITIALIZER(lockname)"
    if nort.count(old_ref) != 1 or nort.count("#define __SPIN_LOCK_INITIALIZER(lockname)") != 1:
        raise ValueError("Unexpected upstream non-RT initializer")
    nort = nort.replace(old_ref, "___SPIN_LOCK_INITIALIZER(lockname)", 1)
    nort = nort.replace("#define __SPIN_LOCK_INITIALIZER(lockname)",
                        NORT_INIT + "#define __SPIN_LOCK_INITIALIZER(lockname)", 1)
    if nort.count("___SPIN_LOCK_INITIALIZER(lockname)") != 2:
        raise ValueError("NonRT initializer is not defined and referenced exactly once")
    after[NORT] = nort

    rt = before[RT]
    if "SPIN_DEP_MAP_INIT(name)" not in rt or "struct rt_mutex" not in rt:
        raise ValueError("Missing upstream RT type initializer")
    if "SPIN_DEP_MAP_INIT(lockname)" not in after[HEADER]:
        raise ValueError("Normal spin lockdep macro missing from top header")
    after[RT] = rt

    if "LD_WAIT_CONFIG" not in after[HEADER]:
        raise ValueError("Lost normal spin lockdep wait type")
    if "LD_WAIT_SPIN" not in after[RAW]:
        raise ValueError("Lost raw spin lockdep wait type")
    if "___SPIN_LOCK_INITIALIZER" not in after[NORT]:
        raise ValueError("Lost vendor nonRT spinlock initializer")
    return reject, sha, before, after


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tree", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--mode", choices=("verify", "apply"), required=True)
    args = p.parse_args()
    tree = args.tree.resolve()
    reject, sha, before, after = changes(tree)
    modified = [path for path in before if before[path] != after[path]]
    if set(modified) != {HEADER, RAW, NORT}:
        raise ValueError("Unexpected modified headers: " + ",".join(modified))
    if args.mode == "apply":
        for name in modified:
            (tree/name).write_text(after[name], encoding="utf-8")
        reject.unlink()
    result = {
        "stage": "EXP76_RT_STAGE5_SOURCE_ONLY",
        "rejected_hunk_sha256": sha,
        "modified_headers": modified,
        "vendor_raw_lockdep": "LD_WAIT_SPIN",
        "vendor_normal_lockdep": "LD_WAIT_CONFIG",
        "nonrt_initializer_vendor_equivalent_source": True,
        "port_applied": args.mode == "apply",
        "remaining_rejected_files": len(list(tree.rglob("*.rej"))),
        "compile_verified": False,
        "runtime_verified": False,
        "flash_ready": False
    }
    args.report.mkdir(parents=True, exist_ok=True)
    (args.report / "stage5-result.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, indent=2))
    if args.mode == "apply" and result["remaining_rejected_files"] != 76:
        raise SystemExit("FAIL_CLOSED: expected 76 remaining rejected files")


if __name__ == "__main__":
    main()
