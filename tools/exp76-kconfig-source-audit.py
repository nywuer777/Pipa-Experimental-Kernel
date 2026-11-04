#!/usr/bin/env python3
# Python 3 / Linux 4.19 E404 tree / audit literal Kconfig sources and broken links / NO FLASH
"""Audit Kconfig source includes, separating missing, optional and dynamic references."""
import argparse
import glob
import json
import os
import re
import subprocess
import time
from pathlib import Path

SOURCE = re.compile(r'^\s*(source|rsource|osource|orsource)\s+(?:"([^"]+)"|([^\s#]+))')
VARIABLE = re.compile(r'\$(?:\{(SRCARCH|ARCH|srctree)\}|(SRCARCH|ARCH|srctree)\b)')
IGNORE = {".git", "out", "build", "exp76-qemu", "exp76-rt-report"}

def kconfigs(tree):
    for directory, dirs, files in os.walk(tree, followlinks=False):
        dirs[:] = [d for d in dirs if d not in IGNORE and not d.startswith("out-")]
        for name in files:
            if name == "Kconfig" or name.startswith("Kconfig."):
                yield Path(directory, name)

def inspect(tree, arch):
    start = time.monotonic()
    files = sorted(kconfigs(tree))
    missing, dynamic, optional = [], [], []
    refs = matched = 0
    for source_file in files:
        rel = source_file.relative_to(tree).as_posix()
        try:
            lines = source_file.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as ex:
            dynamic.append({"from": rel, "line": None, "raw": "", "reason": "UNREADABLE_FILE", "error": str(ex)})
            continue
        for lineno, line in enumerate(lines, 1):
            m = SOURCE.match(line)
            if not m:
                continue
            refs += 1
            kind, quoted, bare = m.groups()
            spec = quoted if quoted is not None else bare
            spec = VARIABLE.sub(lambda m: {
                "SRCARCH": arch, "ARCH": arch, "srctree": str(tree)
            }[m.group(1) or m.group(2)], spec)
            if "$" in spec:
                dynamic.append({"from": rel, "line": lineno, "raw": spec, "reason": "DYNAMIC_VARIABLE"})
                continue
            base = source_file.parent if kind in ("rsource", "orsource") else tree
            path = Path(spec)
            candidate = path if path.is_absolute() else base / path
            matches = [Path(p) for p in glob.glob(str(candidate), recursive=True) if Path(p).is_file()]
            if matches:
                matched += 1
                continue
            detail = {
                "from": rel, "line": lineno, "directive": kind,
                "source": spec,
                "resolved_target": str(candidate.relative_to(tree)) if candidate.is_relative_to(tree) else str(candidate),
                "broken_symlink": candidate.is_symlink() and not candidate.exists(),
                "source_directory_broken_symlink": any(
                    ancestor.is_symlink() and not ancestor.exists()
                    for ancestor in candidate.parents if ancestor != tree
                )
            }
            if kind in ("osource", "orsource"):
                optional.append(detail)
            else:
                missing.append(detail)
    missing_paths = sorted(set(x["resolved_target"] for x in missing))
    gitmodules = tree / ".gitmodules"
    subs = gitmodules.read_text(encoding="utf-8") if gitmodules.exists() else ""
    status = None
    if (tree / ".git").exists():
        try:
            p = subprocess.run(["git","-C",str(tree),"submodule","status"],
                               capture_output=True,text=True,timeout=5)
            status = {"exit_code":p.returncode,"output":p.stdout[-6000:],"stderr":p.stderr[-1000:]}
        except Exception as ex:
            status={"error":str(ex)}
    return {
        "schema_version":1, "stage":"EXP76_E404_KCONFIG_SOURCE_DEPENDENCIES",
        "tree":str(tree), "arch":arch, "elapsed_s":round(time.monotonic()-start,5),
        "kconfig_files_scanned":len(files), "source_directives":refs, "source_resolved_directives":matched,
        "missing_source_occurrences_count":len(missing),
        "missing_source_paths_count":len(missing_paths),
        "missing_source_paths":missing_paths, "missing_sources":missing,
        "optional_missing_count":len(optional), "optional_missing":optional,
        "unresolved_dynamic_count":len(dynamic), "unresolved_dynamic":dynamic,
        "gitmodules":subs, "submodule_status":status,
        "status":"FAIL_MISSING_SOURCES" if missing else ("INCOMPLETE_DYNAMIC" if dynamic else "PASS"),
        "rt_handoff_ready":False
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--tree",type=Path,required=True)
    p.add_argument("--arch",default="arm64")
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--fail-on-missing",action="store_true")
    args=p.parse_args()
    tree=args.tree.resolve(strict=True)
    result=inspect(tree,args.arch)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in ("missing_sources","optional_missing","unresolved_dynamic","gitmodules","submodule_status")},indent=2))
    if args.fail_on_missing and result["missing_source_paths_count"]:
        raise SystemExit(1)

if __name__=="__main__":
    main()
