#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage58 RT rwlock header ordering regressions / NO FLASH
"""Test bounded lock query move, exported symbol, and fail-closed ABI drift."""
from __future__ import annotations
import json
import runpy
import tempfile
from pathlib import Path

M = runpy.run_path(str(Path(__file__).resolve().parents[1] /
                       "tools/exp76-rt-stage58-rwlock-outofline.py"),
                   run_name="stage58_fixture")
prepare, execute = M["prepare"], M["execute"]


def put(root: Path, name: str, data: str) -> Path:
    file = root / name
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(data, encoding="utf-8")
    return file


def fixture(folder: Path) -> Path:
    tree = folder / "trial"
    (tree / ".git").mkdir(parents=True)
    put(tree, M["HEADER"], "#ifndef __LINUX_RWLOCK_RT_H\n" +
        M["STAGE57_HELPER"] +
        "void __read_rt_unlock(struct rt_rw_lock *lock);\n#endif\n")
    put(tree, M["SOURCE"],
        "#include <linux/sched/debug.h>\n"
        "#include <linux/export.h>\n\n"
        "#include \"rtmutex_common.h\"\n" + M["SOURCE_INCLUDE"] +
        "void __read_rt_unlock(struct rt_rw_lock *lock)\n{\n"
        "\traw_spin_lock_irq(&lock->rtmutex.wait_lock);\n"
        "\traw_spin_unlock_irq(&lock->rtmutex.wait_lock);\n}\n")
    put(tree, M["RT_MUTEX"],
        "struct rt_mutex {\n\traw_spinlock_t\t\twait_lock;\n"
        "\tstruct rb_root_cached   waiters;\n};\n")
    put(tree, M["REJECT"], "unresolved\n")
    for n in range(63):
        put(tree, f"unresolved/r-{n:02d}.rej", "unresolved\n")
    return tree


def reject(fn, expected: str) -> None:
    try:
        fn()
    except ValueError as error:
        assert expected in str(error), str(error)
    else:
        raise AssertionError("Stage58 expected fail-closed error: " + expected)


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        tree = fixture(root / "success")
        original = {name: (tree / name).read_text()
                    for name in (M["HEADER"], M["SOURCE"])}
        verified = execute(tree, root / "verify", "verify")
        assert not verified["applied"]
        assert all((tree / name).read_text() == text
                   for name, text in original.items())
        result = execute(tree, root / "apply", "apply")
        assert result["applied"] and result["remaining_rejected_files"] == 64
        assert not result["kernel_built"] and not result["flash_ready"]
        assert (tree / M["HEADER"]).read_text() == original[M["HEADER"]].replace(
            M["STAGE57_HELPER"], M["HEADER_DECL"], 1)
        assert (tree / M["SOURCE"]).read_text() == original[M["SOURCE"]].replace(
            M["SOURCE_INCLUDE"], M["SOURCE_INCLUDE"] + M["SOURCE_FUNC"], 1)
        assert "raw_spin_lock_irqsave" not in (tree / M["HEADER"]).read_text()
        assert "EXPORT_SYMBOL_GPL(rwlock_is_contended);" in (
            tree / M["SOURCE"]).read_text()
        assert json.loads((root / "apply/stage58-status.json").read_text()) == result
        reject(lambda: prepare(tree), "Original Stage57 inline")

        no_helper = fixture(root / "no-inline")
        p = no_helper / M["HEADER"]
        p.write_text(p.read_text().replace(M["STAGE57_HELPER"], "/* absent */\n"))
        reject(lambda: prepare(no_helper), "Original Stage57 inline")

        double = fixture(root / "double-inline")
        p = double / M["HEADER"]
        p.write_text(p.read_text() + M["STAGE57_HELPER"])
        reject(lambda: prepare(double), "expected one pinned")

        source_drift = fixture(root / "source-drift")
        p = source_drift / M["SOURCE"]
        p.write_text(p.read_text().replace(M["SOURCE_INCLUDE"], "/* missing */\n"))
        reject(lambda: prepare(source_drift), "source includes")

        no_export = fixture(root / "no-export")
        p = no_export / M["SOURCE"]
        p.write_text(p.read_text().replace("#include <linux/export.h>\n", ""))
        reject(lambda: prepare(no_export), "module export header")

        already = fixture(root / "duplicate-symbol")
        p = already / M["SOURCE"]
        p.write_text(p.read_text() + "int rwlock_is_contended(rwlock_t *x) { return 0; }\n")
        reject(lambda: prepare(already), "already defined")

        no_read_unlock = fixture(root / "no-read-unlock")
        p = no_read_unlock / M["SOURCE"]
        p.write_text(p.read_text().replace("void __read_rt_unlock(", "void invalid("))
        reject(lambda: prepare(no_read_unlock), "reader implementation")

        no_wait_lock = fixture(root / "lock-drift")
        p = no_wait_lock / M["RT_MUTEX"]
        p.write_text(p.read_text().replace("raw_spinlock_t", "spinlock_t"))
        reject(lambda: prepare(no_wait_lock), "raw wait_lock")

        no_waiters = fixture(root / "waiter-drift")
        p = no_waiters / M["RT_MUTEX"]
        p.write_text(p.read_text().replace("struct rb_root_cached   waiters;", "int waiters;"))
        reject(lambda: prepare(no_waiters), "PI waiter tree")

        lost_reject = fixture(root / "reject-lost")
        (lost_reject / "unresolved/r-00.rej").unlink()
        reject(lambda: prepare(lost_reject), "64 outstanding")

        missing_git = fixture(root / "missing-git")
        (missing_git / ".git").rmdir()
        reject(lambda: prepare(missing_git), "isolated E404")

        invalid_mode = fixture(root / "invalid-mode")
        reject(lambda: execute(invalid_mode, root / "bad", "flash"),
               "Stage58 mode")
    print("EXP76_STAGE58_RT_RWLOCK_OUTOFLINE_REGRESSIONS=11_PASS; KERNEL_BUILT=false; FLASH_READY=false")


if __name__ == "__main__":
    main()
