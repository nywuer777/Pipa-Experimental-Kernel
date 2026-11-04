#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage88 RT Kconfig regression fixtures / NO FLASH
"""Exercise pinned Kconfig RT guards, vendor constraints and effective config."""
from __future__ import annotations

import hashlib
import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(
    str(ROOT / "tools/exp76-stage88-rt-kconfig-guards.py"),
    run_name="stage88_synthetic_fixture",
)
MM_REJECT = (
    "diff --git a/mm/Kconfig b/mm/Kconfig\n"
    "--- a/mm/Kconfig\n"
    "+++ b/mm/Kconfig\n"
    "@@ -377,7 +377,7 @@ config NOMMU_INITIAL_TRIM_EXCESS\n"
    " config TRANSPARENT_HUGEPAGE\n"
    "-\tdepends on HAVE_ARCH_TRANSPARENT_HUGEPAGE\n"
    "+\tdepends on HAVE_ARCH_TRANSPARENT_HUGEPAGE && !PREEMPT_RT_FULL\n"
)
LOCKS_REJECT = (
    "diff --git a/kernel/Kconfig.locks b/kernel/Kconfig.locks\n"
    "--- a/kernel/Kconfig.locks\n"
    "+++ b/kernel/Kconfig.locks\n"
    "@@ -225,11 +225,11 @@ config ARCH_SUPPORTS_ATOMIC_RMW\n"
    " config MUTEX_SPIN_ON_OWNER\n"
    "-\tdepends on SMP && ARCH_SUPPORTS_ATOMIC_RMW\n"
    "+\tdepends on SMP && ARCH_SUPPORTS_ATOMIC_RMW && !PREEMPT_RT_FULL\n"
    " config RWSEM_SPIN_ON_OWNER\n"
    "-       depends on SMP && RWSEM_XCHGADD_ALGORITHM && ARCH_SUPPORTS_ATOMIC_RMW\n"
    "+       depends on SMP && RWSEM_XCHGADD_ALGORITHM && ARCH_SUPPORTS_ATOMIC_RMW && !PREEMPT_RT_FULL\n"
)
MM_SOURCE = (
    "config NOMMU_INITIAL_TRIM_EXCESS\n"
    "\tbool \"nommu\"\n"
    "config TRANSPARENT_HUGEPAGE\n"
    "\tbool \"Transparent Hugepage Support\"\n"
    "\tdepends on HAVE_ARCH_TRANSPARENT_HUGEPAGE\n"
    "\tselect COMPACTION\n"
    "config THP_SWAP\n"
    "\tbool \"THP swap\"\n"
    "\tdepends on TRANSPARENT_HUGEPAGE\n"
)
LOCKS_SOURCE = (
    "config ARCH_SUPPORTS_ATOMIC_RMW\n"
    "\tbool\n"
    "config MUTEX_SPIN_ON_OWNER\n"
    "\tdef_bool y\n"
    "\tdepends on SMP && ARCH_SUPPORTS_ATOMIC_RMW\n"
    "config RWSEM_SPIN_ON_OWNER\n"
    "       def_bool y\n"
    "       depends on SMP && ARCH_SUPPORTS_ATOMIC_RMW\n"
    "config LOCK_SPIN_ON_OWNER\n"
    "\tdef_bool y\n"
    "\tdepends on MUTEX_SPIN_ON_OWNER || RWSEM_SPIN_ON_OWNER\n"
)


def put(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")


def fixture(root: Path) -> tuple[Path, Path, Path, Path]:
    tree = root / "trial"
    (tree / ".git").mkdir(parents=True, exist_ok=True)
    put(tree / "mm/Kconfig", MM_SOURCE)
    put(tree / "kernel/Kconfig.locks", LOCKS_SOURCE)
    put(tree / "mm/Kconfig.rej", MM_REJECT)
    put(tree / "kernel/Kconfig.locks.rej", LOCKS_REJECT)
    for i in range(62):
        put(tree / f"pending/conflict-{i:02d}.c.rej", "@@ -1 +1 @@\n-old\n+new\n")
    put(tree / M["AUDIT_SENTINEL"], "@@ -1 +1 @@\n-old\n+new\n")
    # Retain total 64, including scheduler sentinel. Use 61 misc conflicts.
    (tree / "pending/conflict-61.c.rej").unlink()
    entries = []
    for relative in M["FILES"]:
        entries.append({
            "source": relative,
            "reject_sha256": hashlib.sha256(
                (tree / (relative + ".rej")).read_bytes()
            ).hexdigest(),
            "hunk_count": 1,
        })
    inventory = root / "stage82.json"
    put(inventory, json.dumps({
        "stage": M["INDEX_STAGE"],
        "remaining_rejected_files": 64,
        "source_modified": False,
        "rejects_deleted": False,
        "entries": entries,
    }))
    config = root / ".config"
    put(config, (
        "CONFIG_PREEMPT_RT_FULL=y\n"
        "# CONFIG_TRANSPARENT_HUGEPAGE is not set\n"
        "# CONFIG_MUTEX_SPIN_ON_OWNER is not set\n"
        "# CONFIG_RWSEM_SPIN_ON_OWNER is not set\n"
    ))
    return tree, inventory, root / "report", config


def pin_synthetic_rejects() -> dict:
    original = {}
    for relative, contents in (
        ("mm/Kconfig", MM_REJECT), ("kernel/Kconfig.locks", LOCKS_REJECT)
    ):
        original[relative] = M["FILES"][relative]["sha"]
        M["FILES"][relative]["sha"] = hashlib.sha256(contents.encode()).hexdigest()
    return original


def restore_rejects(original: dict) -> None:
    for relative, sha in original.items():
        M["FILES"][relative]["sha"] = sha


def reject(fn, snippet: str) -> None:
    try:
        fn()
    except ValueError as error:
        assert snippet in str(error), (snippet, str(error))
    else:
        raise AssertionError("Stage88 accepted invalid fixture: " + snippet)


def call(fixture_args, mode: str):
    tree, inventory, report, config = fixture_args
    return M["execute"](
        tree, inventory, report, mode,
        config if mode == "verify-config" else None,
    )


def main() -> None:
    original = pin_synthetic_rejects()
    try:
        assert len(M["CONFIGS"]) == 3
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = fixture(root / "good")
            before = {
                p: (good[0] / p).read_bytes() for p in M["FILES"]
            }
            dry = call(good, "verify")
            assert dry["applied"] is False
            assert all((good[0] / p).read_bytes() == before[p] for p in before)
            live = call(good, "apply")
            assert live["applied"] is True
            assert live["upstream_rejected_hunks_reviewed"] == 2
            assert live["upstream_rejected_lines_reviewed"] == 3
            assert live["remaining_rejected_files"] == 64
            assert live["vendor_rwsem_prerequisites_preserved"] is True
            assert live["effective_config_verified"] is False
            for name in M["CONFIGS"]:
                path = "mm/Kconfig" if name == "TRANSPARENT_HUGEPAGE" else "kernel/Kconfig.locks"
                source = (good[0] / path).read_text()
                marker = "config " + name + "\n"
                block = source.split(marker)[1].split("config ")[0]
                assert "!PREEMPT_RT_FULL" in block
            locks = (good[0] / "kernel/Kconfig.locks").read_text()
            assert (
                "       depends on SMP && ARCH_SUPPORTS_ATOMIC_RMW && !PREEMPT_RT_FULL"
                in locks
            )
            assert "RWSEM_XCHGADD_ALGORITHM && ARCH_SUPPORTS_ATOMIC_RMW && !PREEMPT_RT_FULL" not in locks
            assert (good[0] / "mm/Kconfig").read_text().count("!PREEMPT_RT_FULL") == 1
            assert len(list(good[0].rglob("*.rej"))) == 64
            verified = call(good, "verify-config")
            assert verified["effective_config_verified"] is True
            assert verified["effective_config_disabled"] == list(M["CONFIGS"])
            assert json.loads((good[2] / M["REPORT"]).read_text()) == verified
            assert not verified["kernel_built"] and not verified["flash_ready"]
            reject(lambda: call(good, "apply"), "vendor dependency mismatch")

            missing_git = fixture(root / "git")
            (missing_git[0] / ".git").rmdir()
            reject(lambda: call(missing_git, "apply"), "isolated RT checkout")

            changed_reject = fixture(root / "reject-sha")
            path = changed_reject[0] / "mm/Kconfig.rej"
            put(path, path.read_text() + "# drift\n")
            reject(lambda: call(changed_reject, "apply"), "rejected SHA mismatch")

            changed_source = fixture(root / "vendor-dependency")
            path = changed_source[0] / "kernel/Kconfig.locks"
            put(path, path.read_text().replace(
                "       depends on SMP && ARCH_SUPPORTS_ATOMIC_RMW\n",
                "       depends on RWSEM_XCHGADD_ALGORITHM\n",
            ))
            reject(lambda: call(changed_source, "apply"), "vendor dependency mismatch")

            wrong_manifest = fixture(root / "inventory")
            data = json.loads(wrong_manifest[1].read_text())
            data["entries"][0]["hunk_count"] = 9
            put(wrong_manifest[1], json.dumps(data))
            reject(lambda: call(wrong_manifest, "apply"), "inventory mismatch")

            missing_reject = fixture(root / "lost-rej")
            (missing_reject[0] / "pending/conflict-00.c.rej").unlink()
            reject(lambda: call(missing_reject, "apply"), "64 original")

            non_rt = fixture(root / "no-rt-config")
            call(non_rt, "apply")
            put(non_rt[3], "CONFIG_PREEMPT=y\n")
            reject(lambda: call(non_rt, "verify-config"), "lacks PREEMPT_RT_FULL=y")

            thp_enabled = fixture(root / "enabled-thp")
            call(thp_enabled, "apply")
            put(thp_enabled[3], "CONFIG_PREEMPT_RT_FULL=y\nCONFIG_TRANSPARENT_HUGEPAGE=y\n")
            reject(lambda: call(thp_enabled, "verify-config"), "remain enabled")

            source_modified = fixture(root / "source-modified")
            call(source_modified, "apply")
            put(source_modified[0] / "mm/Kconfig",
                (source_modified[0] / "mm/Kconfig").read_text() + "# changed\n")
            reject(lambda: call(source_modified, "verify-config"), "source hash mismatch")

            no_report = fixture(root / "missing-report")
            reject(lambda: call(no_report, "verify-config"), "applied report")

            malicious_mode = fixture(root / "mode")
            reject(lambda: call(malicious_mode, "flash"), "verify, apply or verify-config")
    finally:
        restore_rejects(original)
    print(
        "EXP76_STAGE88_RT_KCONFIG_GUARDS_REGRESSIONS=11_PASS; "
        "GUARDS=3; REJECTS_RETAINED=64; FLASH_READY=false"
    )


if __name__ == "__main__":
    main()
