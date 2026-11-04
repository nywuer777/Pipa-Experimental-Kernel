#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu 24.04 / EXP76 Stage92 linked migration contract regressions / NO FLASH
"""Synthetic source and real System.map fixtures for fail-closed RT migration gate."""
from __future__ import annotations

import json
import runpy
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = runpy.run_path(
    str(ROOT / "tools/exp76-stage92-migration-link-contract.py"),
    run_name="stage92_regression_helpers",
)


def put(path: Path, contents: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(contents, bytes):
        path.write_bytes(contents)
    else:
        path.write_text(contents, encoding="utf-8")


def fixture(root: Path) -> tuple[Path, ...]:
    tree = root / "trial"
    out = root / "output"
    (tree / ".git").mkdir(parents=True)
    for i in range(63):
        put(tree / f"original-conflicts/{i:02d}.c.rej", "pinned RT reject\n")
    put(tree / "kernel/sched/cpupri.c.rej", "pinned scheduler reject\n")
    token_lines = {path: [] for path in M["SOURCES"]}
    for _label, (path, token) in M["CHECKS"].items():
        token_lines[path].append(token)
    token_lines["kernel/sched/core.c"].extend(
        ("void migrate_disable(void) {}", "void migrate_enable(void) {}",
         "int cpu_nr_pinned(int cpu) { return cpu; }")
    )
    token_lines["kernel/cpu.c"].extend(
        ("if (cpu_nr_pinned(cpu)) return;", "if (cpu_nr_pinned(cpu)) return;")
    )
    for path, lines in token_lines.items():
        put(tree / path, "\n".join(lines) + "\n")
    put(out / ".config", "CONFIG_SMP=y\nCONFIG_PREEMPT_RT_FULL=y\n")
    put(out / "vmlinux", b"\x7fELF" + bytes(8192))
    put(out / "System.map", "".join(
        f"ffff80000000{i:04x} T {name}\n"
        for i, name in enumerate(M["SYMBOLS"])
    ))
    stage41 = root / "stage41.json"
    put(stage41, json.dumps({
        "stage": M["STAGE41"],
        **{key: True for key in (
            "applied", "original_rt_migration_hunk_ported",
            "nested_migrate_disable_enable_present",
            "runqueue_nr_pinned_counted",
            "cpu_nr_pinned_reads_accounted_runqueue",
            "saved_vendor_affinity_mask_and_setaffinity_deferral",
            "upstream_async_stopper_safety_checks_preserved",
            "cpu_hotplug_caller_unchanged",
        )},
        "remaining_rejected_files": 64,
        "migration_runtime_semantics_verified": False,
        "flash_ready": False,
    }))
    stage86 = root / "stage86.json"
    put(stage86, json.dumps({
        "stage": M["STAGE86"], "attempted": True, "exit_code": 0,
        "raw_arm64_header_valid": True,
        "all_previous_unresolved_symbols_restored": True,
        "remaining_rejected_files": 64,
        "packaged_boot_image_generated": False,
        "flash_performed": False, "flash_ready": False,
    }))
    return tree, out, stage41, stage86, root / "report"


def run(args: tuple[Path, ...]) -> dict:
    return M["execute"](*args)


def reject(fn, expected: str) -> None:
    try:
        fn()
    except ValueError as exc:
        assert expected in str(exc), (expected, str(exc))
    else:
        raise AssertionError("Stage92 accepted invalid source/link: " + expected)


def change_json(path: Path, key: str, value) -> None:
    obj = json.loads(path.read_text())
    obj[key] = value
    put(path, json.dumps(obj))


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        good = fixture(root / "good")
        status = run(good)
        assert status["stage"] == M["STAGE"]
        assert status["smp_preempt_rt_full_config_verified"] is True
        assert status["arm64_stage86_image_link_verified"] is True
        assert status["source_stage41_applied"] is True
        assert status["verification_scope"] == "SOURCE_AND_LINK_ONLY"
        assert status["cross_file_source_contract_count"] == len(M["CHECKS"]) == 14
        assert status["system_map_symbols_present"] == list(M["SYMBOLS"])
        assert status["system_map_symbols_missing"] == []
        assert status["vendor_embedded_cpus_allowed_preserved"]
        assert status["cpu_hotplug_callers_verified"] == 2
        assert status["original_rejects_retained"]
        assert status["remaining_rejected_files"] == 64
        assert not status["migration_runtime_semantics_verified"]
        assert not status["cpu_hotplug_runtime_verified"]
        assert not status["rcu_runtime_verified"]
        assert not status["device_boot_verified"]
        assert not status["kernel_built"] and not status["flash_ready"]
        assert json.loads((good[4] / M["REPORT"]).read_text()) == status

        no_symbol = fixture(root / "no-symbol")
        mp = no_symbol[1] / "System.map"
        put(mp, mp.read_text().replace(" T cpu_nr_pinned", " T no_cpu_nr_pinned"))
        reject(lambda: run(no_symbol), "absent from actual linked System.map")

        wrong_code = fixture(root / "wrong-code")
        p = wrong_code[0] / "kernel/sched/core.c"
        put(p, p.read_text().replace(
            "cpumask_copy(&p->migrate_disable_saved_mask, new_mask);", "/* unsafe */"))
        reject(lambda: run(wrong_code), "deferred_affinity_requested_mask")

        missing_counter = fixture(root / "counter")
        p = missing_counter[0] / "kernel/sched/sched.h"
        put(p, p.read_text().replace("\tint\t\t\tnr_pinned;", "int missing;"))
        reject(lambda: run(missing_counter), "runqueue_nr_pinned_field")

        missing_stopper = fixture(root / "stopper")
        p = missing_stopper[0] / "kernel/sched/core.c"
        put(p, p.read_text().replace(
            "stop_one_cpu_nowait(task_cpu(p), migration_cpu_stop,", "no_stop"))
        reject(lambda: run(missing_stopper), "asynchronous_cpu_stopper")

        changed_hotplug = fixture(root / "hotplug")
        put(changed_hotplug[0] / "kernel/cpu.c", "if (cpu_nr_pinned(cpu)) return;\n")
        reject(lambda: run(changed_hotplug), "CPU hotplug pinning check")

        missing_field = fixture(root / "field")
        put(missing_field[0] / "include/linux/sched.h",
            "cpumask_t cpus_ptr;\n" + (
                missing_field[0] / "include/linux/sched.h"
            ).read_text())
        reject(lambda: run(missing_field), "unsupported E404 cpus_ptr")

        no_rt = fixture(root / "no-rt")
        put(no_rt[1] / ".config", "CONFIG_SMP=y\nCONFIG_PREEMPT=y\n")
        reject(lambda: run(no_rt), "CONFIG_PREEMPT_RT_FULL=y")

        no_smp = fixture(root / "no-smp")
        put(no_smp[1] / ".config", "CONFIG_PREEMPT_RT_FULL=y\n")
        reject(lambda: run(no_smp), "CONFIG_SMP=y")

        invalid_stage41 = fixture(root / "stage41")
        change_json(invalid_stage41[2], "runqueue_nr_pinned_counted", False)
        reject(lambda: run(invalid_stage41), "incomplete Stage41")

        invalid_stage86 = fixture(root / "stage86")
        change_json(invalid_stage86[3], "raw_arm64_header_valid", False)
        reject(lambda: run(invalid_stage86), "arm64 Image/link evidence invalid")

        invalid_elf = fixture(root / "elf")
        put(invalid_elf[1] / "vmlinux", b"BAD!" + bytes(8192))
        reject(lambda: run(invalid_elf), "vmlinux ELF missing")

        missing_map = fixture(root / "map")
        (missing_map[1] / "System.map").unlink()
        reject(lambda: run(missing_map), "System.map missing")

        missing_rej = fixture(root / "reject-count")
        (missing_rej[0] / "original-conflicts/00.c.rej").unlink()
        reject(lambda: run(missing_rej), "64 original")

    print(
        "EXP76_STAGE92_RT_MIGRATION_LINK_CONTRACT_REGRESSIONS=14_PASS; "
        "PINNING_SYMBOLS=3; SOURCE_CHECKS=14; "
        "RUNTIME_VERIFIED=false; FLASH_READY=false"
    )


if __name__ == "__main__":
    main()
