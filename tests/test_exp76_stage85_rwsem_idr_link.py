#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage85 RT link API regressions / NO FLASH
"""Lock public wrappers to E404 exports and verify proper local-lock pairing."""
from __future__ import annotations

import hashlib
import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(
    str(ROOT / "tools/exp76-rt-stage85-rwsem-idr-link.py"),
    run_name="stage85_fixture",
)


def put(file: Path, content: str) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(content, encoding="utf-8")


def fixture(root: Path) -> tuple[Path, Path]:
    tree = root / "trial"
    (tree / ".git").mkdir(parents=True)
    put(tree / M["MAKE"],
        "obj-y += semaphore.o percpu-rwsem.o\n"
        "ifneq ($(CONFIG_PREEMPT_RT_FULL),y)\n"
        "obj-y += mutex.o rwsem.o\n"
        "endif\n"
        + M["ANCHOR"] + "obj-y += spinlock.o\n"
    )
    rt = "\n".join(
        f"int {name}(struct rw_semaphore *sem) {{ return 0; }}"
        for name in M["LOWLEVEL"]
    )
    hdr = "\n".join(
        f"extern int {name}(struct rw_semaphore *sem);"
        for name in M["LOWLEVEL"]
    )
    put(tree / M["RT_RWSEM"], rt + "\n")
    put(tree / M["RT_HEADER"], hdr + "\n")
    wrappers = []
    for name in M["PUBLIC_FUNCS"]:
        if name == "down_read":
            wrappers.append(
                "void __sched down_read(struct rw_semaphore *sem)\n"
                "{\n\tmight_sleep();\n\t__down_read(sem);\n}\n"
                "EXPORT_SYMBOL(down_read);\n\n"
                "int __sched down_read_interruptible(struct rw_semaphore *sem)\n"
                "{\n\treturn __down_read_interruptible(sem);\n}\n"
                "EXPORT_SYMBOL(down_read_interruptible);\n\n"
            )
        else:
            wrappers.append(
                f"int {'__sched ' if name == 'down_read_killable' else ''}{name}(struct rw_semaphore *sem)\n"
                "{\n\treturn 0;\n}\n"
                f"EXPORT_SYMBOL({name});\n\n"
            )
    vendor = (
        '#include "rwsem.h"\n'
        'static int vendor_rwsem_body;\n'
        + "".join(wrappers) +
        "#ifdef CONFIG_DEBUG_LOCK_ALLOC\n"
        "void down_read_nested(void) {}\n"
        "#endif\n"
    )
    put(tree / M["VENDOR_RWSEM"], vendor)
    put(tree / M["RADIX"], (
        "#include <linux/locallock.h>\n"
        "static DEFINE_LOCAL_IRQ_LOCK(radix_tree_preloads_lock);\n"
        "void radix_tree_preload(void) {\n"
        "\tlocal_lock(radix_tree_preloads_lock);\n"
        "\tlocal_unlock(radix_tree_preloads_lock);\n"
        "}\n"
        "void idr_preload(gfp_t gfp_mask)\n"
        "{\n\tlocal_lock(radix_tree_preloads_lock);\n}\n"
        "EXPORT_SYMBOL(idr_preload);\n"
        "void idr_get_free(void) {}\n"
    ))
    put(tree / M["IDR"], "void idr_preload_end(void);\n")
    for i in range(64):
        put(tree / f"pending/rejected-{i:02d}.rej", "@@ -1 +1 @@\n-old\n+new\n")
    return tree, root / "stage85"


def reject(fn, target: str) -> None:
    try:
        fn()
    except ValueError as exc:
        assert target in str(exc), str(exc)
    else:
        raise AssertionError("Stage85 accepted invalid input: " + target)


def main() -> None:
    assert len(M["PUBLIC_FUNCS"]) == 9
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        tree, report = fixture(root / "good")
        original_make = (tree / M["MAKE"]).read_bytes()
        original_radix = (tree / M["RADIX"]).read_bytes()
        dry = M["execute"](tree, report, "verify")
        assert dry["applied"] is False
        assert not (tree / M["API"]).exists()
        assert (tree / M["MAKE"]).read_bytes() == original_make
        assert (tree / M["RADIX"]).read_bytes() == original_radix
        actual = M["execute"](tree, report, "apply")
        assert actual["applied"] is True
        assert actual["rt_public_wrapper_count"] == 9
        assert actual["idr_preload_end_uses_local_unlock"]
        assert actual["non_rt_vendor_rwsem_not_linked"]
        assert actual["rejected_files_remaining"] == 64
        make = (tree / M["MAKE"]).read_text()
        api = (tree / M["API"]).read_text()
        radix = (tree / M["RADIX"]).read_text()
        assert make.count("obj-$(CONFIG_PREEMPT_RT_FULL) += rwsem-rt-api.o") == 1
        assert "obj-y += mutex.o rwsem.o" in make
        assert "#ifndef CONFIG_PREEMPT_RT_FULL" in api
        assert "EXPORT_SYMBOL(down_read_interruptible)" not in api
        for item in M["PUBLIC_FUNCS"]:
            assert api.count("EXPORT_SYMBOL(" + item + ")") == 1
        assert radix.count("void idr_preload_end(void)") == 1
        assert "local_unlock(radix_tree_preloads_lock);" in radix
        assert "EXPORT_SYMBOL(idr_preload_end);" in radix
        assert (tree / M["VENDOR_RWSEM"]).read_text().count(
            "EXPORT_SYMBOL(down_read_interruptible)"
        ) == 1
        assert json.loads((report / M["REPORT"]).read_text()) == actual
        assert not actual["kernel_built"] and not actual["flash_ready"]
        reject(lambda: M["prepare"](tree), "already present")

        missing_lowlevel = fixture(root / "lowlevel")
        p = missing_lowlevel[0] / M["RT_RWSEM"]
        put(p, p.read_text().replace("__up_write(", "__up_write_missing("))
        reject(lambda: M["prepare"](missing_lowlevel[0]), "implementation missing")

        missing_header = fixture(root / "header")
        p = missing_header[0] / M["RT_HEADER"]
        put(p, p.read_text().replace("__down_write(", "__down_write_other("))
        reject(lambda: M["prepare"](missing_header[0]), "signature missing")

        drift_vendor = fixture(root / "vendor")
        p = drift_vendor[0] / M["VENDOR_RWSEM"]
        put(p, p.read_text().replace("EXPORT_SYMBOL(up_write);", "EXPORT_SYMBOL(other);"))
        reject(lambda: M["prepare"](drift_vendor[0]), "anchor mismatch")

        non_rt_guard = fixture(root / "kbuild")
        p = non_rt_guard[0] / M["MAKE"]
        put(p, p.read_text().replace(M["ANCHOR"], "obj-y += rwsem.o\n"))
        reject(lambda: M["prepare"](non_rt_guard[0]), "RT Kbuild object list")

        bad_lock = fixture(root / "lock")
        p = bad_lock[0] / M["RADIX"]
        put(p, p.read_text().replace(
            "static DEFINE_LOCAL_IRQ_LOCK(radix_tree_preloads_lock);",
            "static DEFINE_SPINLOCK(radix_tree_preloads_lock);"
        ))
        reject(lambda: M["prepare"](bad_lock[0]), "local_lock ABI missing")

        bad_declaration = fixture(root / "declaration")
        put(bad_declaration[0] / M["IDR"], "static inline void idr_preload_end(void) {}\n")
        reject(lambda: M["prepare"](bad_declaration[0]), "RT idr header declaration")

        missing_reject = fixture(root / "reject-drift")
        (missing_reject[0] / "pending/rejected-00.rej").unlink()
        reject(lambda: M["prepare"](missing_reject[0]), "64 outstanding")

        missing_git = fixture(root / "git")
        (missing_git[0] / ".git").rmdir()
        reject(lambda: M["prepare"](missing_git[0]), "isolated trial Git")

        wrong_mode = fixture(root / "wrong-mode")
        reject(lambda: M["execute"](*wrong_mode, "flash"), "verify or apply")
    print(
        "EXP76_STAGE85_RT_LINK_ABI_REGRESSIONS=10_PASS; "
        "KERNEL_BUILT=false; FLASH_READY=false"
    )


if __name__ == "__main__":
    main()
