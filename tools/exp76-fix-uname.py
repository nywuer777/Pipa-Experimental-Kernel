#!/usr/bin/env python3
# Python 3 / GitHub Actions and local source checkout / E404 kernel/sys.c uname fix
"""Remove UID>=1000 uname spoof only; preserve Android network-service exceptions."""
from __future__ import annotations

import argparse
from pathlib import Path

START = "SYSCALL_DEFINE1(newuname, struct new_utsname __user *, name)\n"
END = "#ifdef __ARCH_WANT_SYS_OLD_UNAME\n"
DECL = "\tuid_t cur_uid = current_uid().val;\n"
SPOOF = (
    '\t} else if (cur_uid >= 1000) {\n'
    '        strlcpy(tmp.release, "5.10.404R", sizeof(tmp.release));\n'
    '    }\n'
)
NETWORK_RULE = 'strcpy(tmp.release, "5.10.404");'


def split_source(source: str) -> tuple[str, str, str]:
    if source.count(START) != 1 or source.count(END) < 1:
        raise ValueError("E404 newuname function markers missing or ambiguous")
    start = source.index(START)
    end = source.find(END, start)
    if end < 0:
        raise ValueError("E404 old uname marker missing after newuname")
    return source[:start], source[start:end], source[end:]


def is_patched(function: str) -> bool:
    return (
        DECL not in function
        and SPOOF not in function
        and 'cur_uid >= 1000' not in function
        and '5.10.404R' not in function
        and NETWORK_RULE in function
        and 'current_uid().val == 0' in function
        and 'memcpy(&tmp, utsname(), sizeof(tmp));' in function
    )


def transform(source: str) -> str:
    head, function, tail = split_source(source)
    if function.count(DECL) != 1 or function.count(SPOOF) != 1:
        raise ValueError("Unsupported source: expected UID>=1000 override exactly once")
    if NETWORK_RULE not in function or 'current_uid().val == 0' not in function:
        raise ValueError("Network-service exception missing; refuse modification")
    function = function.replace(DECL, "", 1).replace(SPOOF, "\t}\n", 1)
    if not is_patched(function):
        raise ValueError("Patched function did not meet invariants")
    return head + function + tail


def verify(source: str) -> None:
    _, function, _ = split_source(source)
    if not is_patched(function):
        raise ValueError("UID>=1000 spoof still present or network exceptions changed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kernel", type=Path, required=True, help="Pinned E404 root directory")
    parser.add_argument("--mode", choices=("apply", "verify"), required=True)
    args = parser.parse_args()
    file = args.kernel / "kernel/sys.c"
    if not file.is_file():
        raise SystemExit(f"Missing E404 source: {file}")
    before = file.read_text(encoding="utf-8")
    if args.mode == "apply":
        after = transform(before)
        if after == before:
            raise SystemExit("No source modification occurred")
        file.write_text(after, encoding="utf-8")
    else:
        verify(before)
    print(
        "EXP76_UNAME_UID_SPOOF_REMOVED=PASS; "
        "NETWORK_SERVICE_EXCEPTIONS=PRESERVED; "
        f"MODE={args.mode}; FLASH_READY=false"
    )


if __name__ == "__main__":
    main()
