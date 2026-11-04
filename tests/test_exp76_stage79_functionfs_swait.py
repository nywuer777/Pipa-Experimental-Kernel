#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage79 FunctionFS regressions / NO FLASH
"""Reject source drift, preserve lifecycle and check RT/nonRT wait APIs."""
from __future__ import annotations

import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(
    str(ROOT / "tools/exp76-rt-stage79-functionfs-swait.py"),
    run_name="exp76_stage79_test_helpers",
)


def write(path: Path, source: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def fixture(root: Path) -> Path:
    tree = root / "trial"
    (tree / ".git").mkdir(parents=True)
    write(tree / M["FILE"], (
        "/* E404 FunctionFS teardown regression fixture */\n"
        + M["INCLUDE_ANCHOR"]
        + "#include <linux/uio.h>\n\n"
        + "static void ffs_data_get(struct ffs_data *ffs);\n"
        + M["FUNCTION"]
        + "\tif (unlikely(refcount_dec_and_test(&ffs->ref))) {\n"
        + "\t\tffs_data_clear(ffs);\n"
        + "\t\tffs_release_dev(ffs->private_data);\n"
        + M["OLD"]
        + "\t\tdestroy_workqueue(ffs->io_completion_wq);\n"
        + "\t\tkfree(ffs);\n"
        + "\t}\n}\n\n"
        + "int setup(struct ffs_data *ffs)\n{\n"
        + "\tinit_completion(&ffs->ep0req_completion);\n"
        + "\treturn wait_for_completion_interruptible(&ffs->ep0req_completion);\n"
        + "}\n"
    ))
    write(tree / M["SWAIT"], (
        "struct swait_queue_head { struct list_head task_list; };\n"
        "static inline int swait_active(struct swait_queue_head *wq)\n"
        "{ return !list_empty(&wq->task_list); }\n"
    ))
    write(tree / M["COMPLETION"], (
        "struct completion {\n"
        "    unsigned int done;\n"
        "#ifdef CONFIG_PREEMPT_RT_FULL\n"
        "    struct swait_queue_head wait;\n"
        "#else\n"
        "    wait_queue_head_t wait;\n"
        "#endif\n"
        "};\n"
    ))
    write(tree / M["SENTINEL"], "rejected RT hunk\n")
    for i in range(63):
        write(tree / f"pending/reject-{i:02d}.rej", "rejected RT hunk\n")
    return tree


def reject(fn, expected: str) -> None:
    try:
        fn()
    except ValueError as err:
        assert expected in str(err), str(err)
    else:
        raise AssertionError("Missing Stage79 fail-closed: " + expected)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tree = fixture(root / "good")
        original = (tree / M["FILE"]).read_text()
        verified = M["execute"](tree, root / "verify", "verify")
        assert not verified["applied"]
        assert (tree / M["FILE"]).read_text() == original
        status = M["execute"](tree, root / "apply", "apply")
        patched = (tree / M["FILE"]).read_text()
        expected = original.replace(
            M["INCLUDE_ANCHOR"], M["ADDED_INCLUDE"], 1
        ).replace(M["OLD"], M["NEW"], 1)
        assert patched == expected
        assert status["rt_completion_swait_used"]
        assert status["nonrt_waitqueue_preserved"]
        assert status["normal_waitqueue_checks_preserved"]
        assert status["completion_lifecycle_preserved"]
        assert status["existing_swait_api_verified"]
        assert status["remaining_rejected_files"] == 64
        assert not status["kernel_built"] and not status["flash_ready"]
        assert M["NEW"].count("swait_active(&ffs->ep0req_completion.wait)") == 1
        assert M["NEW"].count("waitqueue_active(&ffs->ep0req_completion.wait)") == 1
        assert M["NEW"].count("waitqueue_active(&ffs->ev.waitq)") == 1
        assert M["NEW"].count("waitqueue_active(&ffs->wait)") == 1
        assert "#ifdef CONFIG_PREEMPT_RT_FULL\n" in M["NEW"]
        assert "#else\n" in M["NEW"] and "#endif\n" in M["NEW"]
        assert json.loads((root / "apply" / M["RESULT"]).read_text()) == status
        reject(lambda: M["prepare"](tree), "completion wait check")

        missing_swait = fixture(root / "missing-swait")
        (missing_swait / M["SWAIT"]).unlink()
        reject(lambda: M["prepare"](missing_swait), "source or outstanding")

        bad_api = fixture(root / "bad-swait-api")
        p = bad_api / M["SWAIT"]
        p.write_text(p.read_text().replace(
            "swait_active(", "swait_renamed("
        ))
        reject(lambda: M["prepare"](bad_api), "swait_active() signature drift")

        no_rt_struct = fixture(root / "completion-not-rt")
        p = no_rt_struct / M["COMPLETION"]
        p.write_text(p.read_text().replace("struct swait_queue_head", "wait_queue_head_t"))
        reject(lambda: M["prepare"](no_rt_struct), "requires RT swait")

        missing_old = fixture(root / "check-drift")
        p = missing_old / M["FILE"]
        p.write_text(p.read_text().replace(
            "waitqueue_active(&ffs->ep0req_completion.wait)",
            "completion_done(&ffs->ep0req_completion)"
        ))
        reject(lambda: M["prepare"](missing_old), "completion wait check")

        no_cleanup = fixture(root / "no-cleanup")
        p = no_cleanup / M["FILE"]
        p.write_text(p.read_text().replace(
            "ffs_data_clear(ffs);", "ffs_data_clear_something_else(ffs);"
        ))
        reject(lambda: M["prepare"](no_cleanup), "cleanup sequence")

        no_finish = fixture(root / "no-free")
        p = no_finish / M["FILE"]
        p.write_text(p.read_text().replace("kfree(ffs);", "kvfree(ffs);"))
        reject(lambda: M["prepare"](no_finish), "final free")

        no_completion_init = fixture(root / "no-completion-init")
        p = no_completion_init / M["FILE"]
        p.write_text(p.read_text().replace(
            "init_completion(&ffs->ep0req_completion);",
            "reinit_completion(&ffs->ep0req_completion);"
        ))
        reject(lambda: M["prepare"](no_completion_init), "initialisation")

        no_wait = fixture(root / "no-completion-waiter")
        p = no_wait / M["FILE"]
        p.write_text(p.read_text().replace(
            "wait_for_completion_interruptible(&ffs->ep0req_completion)",
            "wait_for_completion(&ffs->ep0req_completion)"
        ))
        reject(lambda: M["prepare"](no_wait), "completion waiter")

        no_git = fixture(root / "no-git")
        (no_git / ".git").rmdir()
        reject(lambda: M["prepare"](no_git), "isolated E404")

        rejected = fixture(root / "lost-reject")
        (rejected / "pending/reject-00.rej").unlink()
        reject(lambda: M["prepare"](rejected), "64 outstanding")

        wrong_mode = fixture(root / "wrong-mode")
        reject(lambda: M["execute"](wrong_mode, root / "bad", "flash"),
               "verify/apply only")
    print("EXP76_STAGE79_FUNCTIONFS_SWAIT_REGRESSIONS=12_PASS; KERNEL_BUILT=false; FLASH_READY=false")


if __name__ == "__main__":
    main()
