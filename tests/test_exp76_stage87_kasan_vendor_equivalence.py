#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage87 KASAN source audit regressions / NO FLASH
"""Test exact hunk equivalence without deleting rejects or rewriting vendor code."""
from __future__ import annotations

import hashlib
import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(
    str(ROOT / "tools/exp76-stage87-kasan-vendor-equivalence.py"),
    run_name="exp76_stage87_fixture",
)
PAIRS = [
    ("static DEFINE_SPINLOCK(quarantine_lock);",
     "static DEFINE_RAW_SPINLOCK(quarantine_lock);"),
    ("\t\tspin_lock(&quarantine_lock);",
     "\t\traw_spin_lock(&quarantine_lock);"),
    ("\t\tspin_unlock(&quarantine_lock);",
     "\t\traw_spin_unlock(&quarantine_lock);"),
    ("\tspin_lock_irqsave(&quarantine_lock, flags);",
     "\traw_spin_lock_irqsave(&quarantine_lock, flags);"),
    ("\tspin_unlock_irqrestore(&quarantine_lock, flags);",
     "\traw_spin_unlock_irqrestore(&quarantine_lock, flags);"),
    ("\tspin_lock_irqsave(&quarantine_lock, flags);",
     "\traw_spin_lock_irqsave(&quarantine_lock, flags);"),
    ("\t\tspin_unlock_irqrestore(&quarantine_lock, flags);",
     "\t\traw_spin_unlock_irqrestore(&quarantine_lock, flags);"),
    ("\t\tspin_lock_irqsave(&quarantine_lock, flags);",
     "\t\traw_spin_lock_irqsave(&quarantine_lock, flags);"),
    ("\tspin_unlock_irqrestore(&quarantine_lock, flags);",
     "\traw_spin_unlock_irqrestore(&quarantine_lock, flags);"),
]


def put(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def synthetic_reject() -> str:
    lines = ["diff --git a/mm/kasan/quarantine.c b/mm/kasan/quarantine.c",
             "--- a/mm/kasan/quarantine.c",
             "+++ b/mm/kasan/quarantine.c"]
    pos = 0
    for i, heading in enumerate(M["HEADERS"]):
        lines.append(heading + " quarantine()")
        group = PAIRS[pos:pos + (4 if i == 5 else 1)]
        pos += len(group)
        for before, after in group:
            lines.append("-" + before)
            lines.append("+" + after)
    assert pos == 9
    return "\n".join(lines) + "\n"


def fixture(root: Path) -> tuple[Path, Path, Path]:
    tree = root / "trial"
    (tree / ".git").mkdir(parents=True)
    for i in range(63):
        put(tree / f"pending/conflict_{i:02d}.c.rej", "@@ -1 +1 @@\n-old\n+new\n")
    put(tree / M["REJECT"], synthetic_reject())
    put(tree / M["SOURCE"], (
        "// vendor E404 raw spinlock implementation\n"
        + "\n".join(line for _, line in PAIRS)
        + "\n"
    ))
    sha = hashlib.sha256((tree / M["REJECT"]).read_bytes()).hexdigest()
    inventory = root / "stage82.json"
    put(inventory, json.dumps({
        "stage": M["STAGE82"], "remaining_rejected_files": 64,
        "source_modified": False, "rejects_deleted": False,
        "entries": [{"source": M["SOURCE"],
                     "reject_sha256": sha, "hunk_count": 6}],
    }))
    return tree, inventory, root / "report"


def reject(fn, message: str) -> None:
    try:
        fn()
    except ValueError as e:
        assert message in str(e), str(e)
    else:
        raise AssertionError("Stage87 unexpectedly allowed " + message)


def sha_sync(tree: Path, manifest: Path) -> None:
    hash_ = hashlib.sha256((tree / M["REJECT"]).read_bytes()).hexdigest()
    M["execute"].__globals__["REJECT_SHA"] = hash_
    data = json.loads(manifest.read_text())
    data["entries"][0]["reject_sha256"] = hash_
    put(manifest, json.dumps(data))


def main() -> None:
    assert M["REJECT_SHA"] == (
        "0fdc912c253d78ffb8b032276f07721fc81d71854a8c60bb82375c74adec506e"
    )
    for before, after in PAIRS:
        assert M["to_raw_spinlock"](before) == after
    headings, removed, added = M["parse_changes"](synthetic_reject())
    assert len(headings) == 6 and len(removed) == len(added) == 9
    old_sha = M["execute"].__globals__["REJECT_SHA"]
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = fixture(root / "good")
            sha_sync(*good[:2])
            before = (good[0] / M["SOURCE"]).read_bytes()
            rejects = (good[0] / M["REJECT"]).read_bytes()
            report = M["execute"](*good)
            assert report["vendor_equivalent_files"] == 1
            assert report["vendor_equivalent_hunks"] == 6
            assert report["reviewed_added_lines"] == 9
            assert report["reviewed_removed_lines"] == 9
            assert report["all_added_raw_spinlock_lines_present"]
            assert report["all_obsolete_spinlock_lines_absent"]
            assert report["source_changed"] is False
            assert report["rejects_deleted"] is False
            assert report["rejected_files_remaining"] == 64
            assert report["all_rt_semantics_verified"] is False
            assert not report["kernel_built"] and not report["flash_ready"]
            assert (good[0] / M["SOURCE"]).read_bytes() == before
            assert (good[0] / M["REJECT"]).read_bytes() == rejects
            assert json.loads((good[2] / M["REPORT"]).read_text()) == report

            missing_git = fixture(root / "git")
            sha_sync(*missing_git[:2])
            (missing_git[0] / ".git").rmdir()
            reject(lambda: M["execute"](*missing_git), "isolated pinned")

            missing_file = fixture(root / "missing-file")
            sha_sync(*missing_file[:2])
            (missing_file[0] / M["REJECT"]).unlink()
            reject(lambda: M["execute"](*missing_file), "source and RT reject")

            changed_sha = fixture(root / "wrong-sha")
            sha_sync(*changed_sha[:2])
            p = changed_sha[0] / M["REJECT"]
            put(p, p.read_text() + "# modified\n")
            reject(lambda: M["execute"](*changed_sha), "SHA256 mismatch")

            missing_inventory = fixture(root / "missing-inventory")
            sha_sync(*missing_inventory[:2])
            missing_inventory[1].unlink()
            reject(lambda: M["execute"](*missing_inventory), "immutable source inventory")

            wrong_hunks = fixture(root / "wrong-hunks")
            p = wrong_hunks[0] / M["REJECT"]
            put(p, p.read_text().replace(
                M["HEADERS"][3], "@@ -231,7 +231,7 @@", 1))
            sha_sync(*wrong_hunks[:2])
            reject(lambda: M["execute"](*wrong_hunks), "six-hunk structure drift")

            changed_primitive = fixture(root / "different-api")
            p = changed_primitive[0] / M["REJECT"]
            put(p, p.read_text().replace(
                "+\t\traw_spin_lock(&quarantine_lock);",
                "+\t\tmutex_lock(&quarantine_lock);", 1))
            sha_sync(*changed_primitive[:2])
            reject(lambda: M["execute"](*changed_primitive),
                   "non-raw-spinlock edits")

            missing_raw = fixture(root / "missing-raw")
            sha_sync(*missing_raw[:2])
            p = missing_raw[0] / M["SOURCE"]
            put(p, p.read_text().replace(
                "\t\traw_spin_lock(&quarantine_lock);", "", 1))
            reject(lambda: M["execute"](*missing_raw), "vendor KASAN not equivalent")

            legacy_spin = fixture(root / "legacy-spin")
            sha_sync(*legacy_spin[:2])
            p = legacy_spin[0] / M["SOURCE"]
            put(p, p.read_text() + "\tspin_lock_irqsave(&quarantine_lock, flags);\n")
            reject(lambda: M["execute"](*legacy_spin), "vendor KASAN not equivalent")

            fewer_rejects = fixture(root / "reject-count")
            sha_sync(*fewer_rejects[:2])
            (fewer_rejects[0] / "pending/conflict_01.c.rej").unlink()
            reject(lambda: M["execute"](*fewer_rejects), "exactly 64")

            bad_manifest = fixture(root / "manifest")
            sha_sync(*bad_manifest[:2])
            data = json.loads(bad_manifest[1].read_text())
            data["entries"][0]["hunk_count"] = 5
            put(bad_manifest[1], json.dumps(data))
            reject(lambda: M["execute"](*bad_manifest), "provenance drift")

    finally:
        M["execute"].__globals__["REJECT_SHA"] = old_sha
    print(
        "EXP76_STAGE87_KASAN_RAW_SPINLOCK_REGRESSIONS=11_PASS; "
        "VENDOR_EQUIVALENT_HUNKS=6; REJECTS_RETAINED=64; FLASH_READY=false"
    )


if __name__ == "__main__":
    main()
