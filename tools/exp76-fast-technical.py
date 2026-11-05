#!/usr/bin/env python3
# Python 3 / Ubuntu 24.04 GitHub Actions / EXP76 fast technical gate for RT source deltas / NO FLASH
"""Incremental technical checks; kernel mode REQUIRES a prepared ARM64 output tree.

The fixture mode is only for mutation-test calibration; a fixture PASS does not
qualify the E404 kernel, and the kernel mode must be wired to production CI.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

CONFIG = re.compile(r"^\s*(?:menu)?config\s+([A-Z][A-Z0-9_]*)\b", re.M)
SOURCE = re.compile(r'^\s*(?:source|rsource|osource)\s+"([^"]+)"\s*$', re.M)
OPTION = re.compile(r"^CONFIG_([A-Z0-9_]+)=(.*)$")


def execute(argv, cwd, timeout=120):
    start = time.monotonic()
    try:
        p = subprocess.run(argv, cwd=cwd, text=True, input="" if argv[-1] == "-" else None,
                           capture_output=True, timeout=timeout, check=False)
        return {"argv": argv, "exit_code": p.returncode,
                "duration_s": round(time.monotonic()-start, 3),
                "output_tail": (p.stdout + p.stderr)[-1800:]}
    except subprocess.TimeoutExpired:
        return {"argv": argv, "exit_code": 124,
                "duration_s": round(time.monotonic()-start, 3),
                "output_tail": "BLOCKED_TIMEOUT"}
    except FileNotFoundError as e:
        return {"argv": argv, "exit_code": 127,
                "duration_s": round(time.monotonic()-start, 3),
                "output_tail": str(e)}


def changed(tree, base, head):
    proc = subprocess.run(["git", "diff", "--name-only", "--diff-filter=ACMR",
                           base, head], cwd=tree, text=True, capture_output=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr)
    return sorted(set(proc.stdout.splitlines()))


def added_lines(tree, base, head, paths):
    if not paths:
        return []
    proc = subprocess.run(["git", "diff", "-U0", base, head, "--", *paths],
                          cwd=tree, text=True, capture_output=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr)
    return [row[1:] for row in proc.stdout.splitlines()
            if row.startswith("+") and not row.startswith("+++ ")]


def inspect_config(tree, paths):
    # Conservative presence check, not Kconfig's complete dependency solver.
    definitions = set()
    for p in tree.rglob("*Kconfig*"):
        if not p.is_file() or ".git" in p.parts or "tests" in p.parts:
            continue
        if p.name != "Kconfig" and not p.name.startswith("Kconfig."):
            continue
        definitions.update(CONFIG.findall(p.read_text(errors="replace")))
    errors = []
    for name in paths:
        p = tree/name
        if not p.is_file():
            continue
        for i, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
            m = OPTION.fullmatch(line)
            if m and m.group(1) not in definitions:
                errors.append(f"{name}:{i}: CONFIG_{m.group(1)} has no config declaration")
    return errors


def inspect_sources(tree, paths):
    errors = []
    for name in paths:
        p = tree/name
        if not p.is_file():
            continue
        for m in SOURCE.finditer(p.read_text(errors="replace")):
            dest = m.group(1)
            if "$" in dest:
                continue  # Dynamic references need real Kconfig evaluation.
            rel = dest if not name.startswith("Kconfig") else dest
            if not (tree/rel).is_file():
                errors.append(f"{name}: Kconfig source missing: {dest}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree", required=True, type=Path)
    parser.add_argument("--mode", choices=("fixture", "kernel"), required=True)
    parser.add_argument("--base", default="HEAD^")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--build-out", type=Path)
    parser.add_argument("--cc", default="ccache clang")
    parser.add_argument("--max-c-files", type=int, default=3)
    args = parser.parse_args()
    tree = args.tree.resolve()
    if not (tree/".git").exists():
        raise SystemExit("BLOCKED_NOT_GIT_TREE")
    files = changed(tree, args.base, args.head)
    c = [f for f in files if f.endswith(".c") and (tree/f).is_file()]
    h = [f for f in files if f.endswith(".h") and (tree/f).is_file()]
    py = [f for f in files if f.endswith(".py") and (tree/f).is_file()]
    kcfg = [f for f in files if Path(f).name.startswith("Kconfig")]
    configs = [f for f in files if "defconfig" in Path(f).name]
    mk = [f for f in files if Path(f).name in ("Makefile", "Kbuild")]
    checks = []
    def add(name, cmd):
        r = execute(cmd, tree)
        checks.append({"test": name, **r})
        return r["exit_code"] == 0

    add("git_diff_check", ["git", "diff", "--check", args.base, args.head])
    if py:
        add("py_compile", [sys.executable, "-m", "py_compile", *py])
    if c:
        mixed = [s for s in added_lines(tree, args.base, args.head, c)
                 if " \t" in s or "\t " in s]
        checks.append({"test": "mixed_whitespace_in_changed_C", "exit_code": 1 if mixed else 0,
                       "output_tail": "\n".join(mixed[:6]), "duration_s": 0})
    if kcfg:
        errors = inspect_sources(tree, kcfg)
        checks.append({"test": "kconfig_literal_sources",
                       "exit_code": 1 if errors else 0,
                       "output_tail": "\n".join(errors[:8]), "duration_s": 0})
    if configs:
        errors = inspect_config(tree, configs)
        checks.append({"test": "defconfig_symbol_existence",
                       "exit_code": 1 if errors else 0,
                       "output_tail": "\n".join(errors[:8]), "duration_s": 0})
    if args.mode == "fixture":
        cc = shutil.which("clang") or shutil.which("gcc")
        if not cc:
            checks.append({"test": "fixture_cc", "exit_code": 127,
                           "output_tail": "no C compiler", "duration_s": 0})
        else:
            for f in c:
                add("compile_C:"+f, [cc, "-std=gnu11", "-Werror=implicit-function-declaration",
                                     "-Werror=return-type", "-fsyntax-only",
                                     "-I", str(tree/"include"), f])
            for f in h:
                add("preprocess_header:"+f, [cc, "-x", "c", "-fsyntax-only",
                                            "-include", f, "-"])
        if mk:
            add("make_recipe_parse", ["make", "--no-print-directory", "-n", "-f", "Makefile", "all"])
    else:
        out = args.build_out.resolve() if args.build_out else None
        if not out or not (out/".config").is_file():
            checks.append({"test": "KBUILD_PREPARED_CONFIG", "exit_code": 125,
                           "output_tail": "prepared --build-out/.config required", "duration_s": 0})
        if len(c) > args.max_c_files or h:
            checks.append({"test": "KBUILD_INCREMENTAL_SCOPE", "exit_code": 125,
                           "output_tail": f"{len(c)} C and {len(h)} headers; maximum {args.max_c_files} C; header dependent objects must be selected explicitly", "duration_s": 0})
        if out and (out/".config").is_file() and len(c) <= args.max_c_files and not h:
            for f in c:
                target = f[:-2]+".o"
                add("real_kbuild_object:"+target,
                    ["make", "-C", str(tree), "O="+str(out), "ARCH=arm64",
                     "CC="+args.cc, "LD=ld.lld", "HOSTCC=gcc",
                     "CROSS_COMPILE=aarch64-linux-gnu-",
                     "CLANG_TRIPLE=aarch64-linux-gnu-", "-j4", target])
        if mk and out:
            add("real_kbuild_makefile_parse",
                ["make", "-C", str(tree), "O="+str(out), "ARCH=arm64", "-n", "prepare"])
    state = "PASS" if checks and all(x["exit_code"] == 0 for x in checks) else "FAIL"
    report = {"stage": "EXP76_FAST_TECHNICAL_INCREMENTAL", "mode": args.mode,
              "state": state, "changed_files": files, "checks": checks,
              "kernel_objects_compiled": sum(x["test"].startswith("real_kbuild_object")
                                            and x["exit_code"] == 0 for x in checks),
              "full_kernel_build_completed": False,
              "mutation_coverage_verified": False,
              "rt_handoff_ready": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({"state": state,"checks":len(checks),"kernel_objects_compiled":report["kernel_objects_compiled"]}))
    raise SystemExit(0 if state=="PASS" else 1)

if __name__ == "__main__":
    main()
