#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / E404 RT reconstructed tree / Clang21 legacy-macro inventory / NO FLASH
"""Inventory every uninitialized_var use and publish bounded Clang21 evidence."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

USE = re.compile(r"\buninitialized_var\s*\(")
DEFINE = re.compile(r"^\s*#\s*define\s+uninitialized_var\b", re.M)
BASE = "fed88a6024cd4d46c52eda607a95d97d7371ba81"


def git_history(tree, rel):
    p = subprocess.run(
        ["git", "-C", str(tree), "log", "--oneline", "-5", "--", rel],
        capture_output=True, text=True, check=False)
    return {"exit_code": p.returncode, "lines": p.stdout.splitlines(),
            "stderr": p.stderr[:300]}


def scan(tree):
    uses = []
    definitions = []
    checked = 0
    for file in sorted(tree.rglob("*")):
        if not file.is_file() or file.is_symlink() or file.suffix not in (".c", ".h"):
            continue
        if ".git" in file.parts:
            continue
        checked += 1
        raw = file.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        rel = file.relative_to(tree).as_posix()
        lines = text.splitlines()
        for number, line in enumerate(lines, 1):
            if USE.search(line):
                uses.append({"file": rel, "line": number,
                             "occurrences": len(USE.findall(line)),
                             "excerpt": line.strip()[:240]})
            if rel.startswith("include/") and DEFINE.search(line):
                definitions.append({"file": rel, "line": number,
                                    "excerpt": line.strip()[:240]})
    return checked, uses, definitions


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tree", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    a = p.parse_args()
    checked, uses, definitions = scan(a.tree)
    virtio = [u for u in uses if u["file"] == "drivers/virtio/virtio_ring.c"]
    before = subprocess.run(
        ["git", "-C", str(a.tree), "diff", "--", "drivers/virtio/virtio_ring.c"],
        capture_output=True, text=True, check=False)
    if before.returncode != 0:
        raise RuntimeError("Cannot check whether RT trial modified VirtIO")
    details = {
        "schema_version": 1,
        "stage": "EXP76_CLANG21_419_LEGACY_MACRO_INVENTORY",
        "source_base": BASE,
        "scope": "EXACT_RECONSTRUCTED_E404_RT_TREE",
        "tree_path": str(a.tree),
        "checked_c_h_files": checked,
        "uninitialized_var_use_lines": len(uses),
        "uninitialized_var_call_sites": sum(u["occurrences"] for u in uses),
        "uninitialized_var_files": sorted({u["file"] for u in uses}),
        "calls": uses,
        "header_macro_definition_count": len(definitions),
        "definitions": definitions,
        "virtio_use_lines": len(virtio),
        "virtio_modified_by_rt_overlay": bool(before.stdout),
        "virtio_overlay_diff_sha256": hashlib.sha256(
            before.stdout.encode()).hexdigest(),
        "recent_header_history": {
            rel: git_history(a.tree, rel) for rel in (
                "include/linux/compiler_attributes.h",
                "include/linux/compiler_types.h",
                "include/linux/compiler.h",
                "include/linux/compiler-gcc.h",
                "include/linux/compiler-clang.h")
        },
        "observed_compatibility_errors": [{
            "run_id": 41902392736,
            "file": "drivers/virtio/virtio_ring.c",
            "line": 271, "symbol": "uninitialized_var(prev)",
            "category": "legacy_macro_undefined",
            "root_cause": (
                "legacy_macro_has_no_definition_in_include"
                if not definitions else "macro_defined_elsewhere_check_include_graph"),
            "fix_branch": "exp76-qemu-virtio-clang21",
            "fix_commit": "b11aac4a94fde7b9d2b12a4e16302306cc1384dd",
            "fix_applied_to_original_source": False,
            "qemu_rt_image_compiled_run": 41930944374,
            "qemu_virtio_runtime_verified": False,
        }],
        "other_clang21_incompatibilities": "UNCLASSIFIED_UNTIL_OBSERVED",
        "qemu_functional_verified": False,
        "rt_handoff_ready": False,
    }
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(details, indent=2) + "\n")
    print("UNINITIALIZED_VAR_USE_LINES=", details["uninitialized_var_use_lines"])
    print("UNINITIALIZED_VAR_CALL_SITES=", details["uninitialized_var_call_sites"])
    print("UNINITIALIZED_VAR_FILES=", len(details["uninitialized_var_files"]))
    print("UNINITIALIZED_VAR_DEFINITIONS=", len(definitions))
    print("VIRTIO_RT_DIFF_PRESENT=", details["virtio_modified_by_rt_overlay"])


if __name__ == "__main__":
    main()
