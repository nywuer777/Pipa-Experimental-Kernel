#!/usr/bin/env python3
# Python 3 / tools/exp76-qemu-virtio-clang21.py / Ubuntu 24.04 CI / pinned E404 VirtIO Clang21 reconciliation / NO FLASH
"""Apply an exact, narrowly-scoped VirtIO source fix in the disposable E404 RT tree.

The original uninitialized_var(prev) macro is absent under the selected Clang
build, so its invocation in a declaration becomes an invalid function-like
parameter declarator. Initialize prev after both descriptor-selection branches
have assigned i. This preserves the selected first descriptor on either path.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

RELATIVE = Path("drivers/virtio/virtio_ring.c")
OLD_DECL = "\tunsigned int i, n, avail, descs_used, uninitialized_var(prev), err_idx;\n"
NEW_DECL = "\tunsigned int i, n, avail, descs_used, prev, err_idx;\n"
OLD_INIT = (
    "\t\tdescs_used = total_sg;\n"
    "\t}\n\n"
    "\tif (vq->vq.num_free < descs_used) {\n"
)
NEW_INIT = (
    "\t\tdescs_used = total_sg;\n"
    "\t}\n\n"
    "\t/* i is the initial descriptor for both direct and indirect rings. */\n"
    "\tprev = i;\n\n"
    "\tif (vq->vq.num_free < descs_used) {\n"
)


class BlockedContext(RuntimeError):
    pass


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def transform(text: str, *, apply: bool) -> tuple[str, str]:
    # Guard against false positives in a different function or vendor layout.
    required = ("BUG_ON(total_sg == 0);", "prev = i;", "desc[prev].flags")
    if any(token not in text for token in required):
        raise BlockedContext("BLOCKED_VIRTIO_SEMANTIC_ANCHORS")
    old_n, new_n = text.count(OLD_DECL), text.count(NEW_DECL)
    anchor_n, fixed_n = text.count(OLD_INIT), text.count(NEW_INIT)
    if old_n == 1 and new_n == 0 and anchor_n == 1 and fixed_n == 0:
        if not apply:
            raise BlockedContext("BLOCKED_VIRTIO_PORT_NOT_APPLIED")
        replaced = text.replace(OLD_DECL, NEW_DECL, 1).replace(OLD_INIT, NEW_INIT, 1)
        if replaced.count(NEW_DECL) != 1 or replaced.count(NEW_INIT) != 1:
            raise BlockedContext("BLOCKED_VIRTIO_POSTCONDITION")
        return replaced, "APPLIED"
    if old_n == 0 and new_n == 1 and anchor_n == 0 and fixed_n == 1:
        return text, "ALREADY_APPLIED"
    raise BlockedContext(
        f"BLOCKED_VIRTIO_DIVERGED_CONTEXT old_decl={old_n} new_decl={new_n} "
        f"old_anchor={anchor_n} fixed_anchor={fixed_n}"
    )


def self_test() -> None:
    fixture = (
        "static int virtqueue_add(void)\n{\n" + OLD_DECL +
        "\tBUG_ON(total_sg == 0);\n\tprev = i;\n\tdesc[prev].flags = 0;\n" +
        OLD_INIT + "}\n"
    )
    result, state = transform(fixture, apply=True)
    assert state == "APPLIED"
    assert result != fixture and result.count("\tprev = i;\n") == 2
    assert transform(result, apply=True) == (result, "ALREADY_APPLIED")
    assert transform(result, apply=False) == (result, "ALREADY_APPLIED")
    try:
        transform(fixture, apply=False)
    except BlockedContext as exc:
        assert str(exc) == "BLOCKED_VIRTIO_PORT_NOT_APPLIED"
    else:
        raise AssertionError("verify accepted unfixed tree")
    try:
        transform(fixture.replace(OLD_INIT, "\tbroken_vendor_context;\n"), apply=True)
    except BlockedContext as exc:
        assert str(exc).startswith("BLOCKED_VIRTIO_DIVERGED_CONTEXT")
    else:
        raise AssertionError("ambiguous context was accepted")
    print("EXP76_VIRTIO_CLANG21_PORT_SELFTEST=PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--mode", choices=("apply", "verify"), default="verify")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.tree is None or args.report is None:
        parser.error("--tree and --report required outside --self-test")
    target = args.tree / RELATIVE
    if not target.is_file() or target.is_symlink():
        raise BlockedContext("BLOCKED_VIRTIO_MISSING_REGULAR_FILE")
    raw = target.read_bytes()
    try:
        source = raw.decode("utf-8")
    except UnicodeError as exc:
        raise BlockedContext("BLOCKED_VIRTIO_SOURCE_ENCODING") from exc
    result, state = transform(source, apply=args.mode == "apply")
    after = result.encode("utf-8")
    if state == "APPLIED":
        target.write_bytes(after)
    evidence = {
        "gate": "EXP76_QEMU_VIRTIO_CLANG21_SOURCE_RECONCILIATION",
        "base": "fed88a6024cd4d46c52eda607a95d97d7371ba81",
        "source_path": str(RELATIVE),
        "status": state,
        "source_sha256_before": digest(raw),
        "source_sha256_after": digest(after),
        "changed_lines": ["declare prev without uninitialized_var()", "initialize prev from selected descriptor i"],
        "qemu_image_compiled": False,
        "qemu_functional_verified": False,
        "rt_handoff_ready": False,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BlockedContext as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
