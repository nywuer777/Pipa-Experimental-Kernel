#!/usr/bin/env python3
# Python 3 / EXP76 CI / generate eight-gate RT checklist from versioned and immutable evidence / NO FLASH
"""Checklist is derived from verified reports; no QEMU or ccache PASS is inferred."""
import argparse
import json
from pathlib import Path

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def generate(root, source_sha, generated_at):
    sched=read(root/"reports/exp76-scheduler-batch1.json")
    kconfig=read(root/"reports/e404-kconfig-missing-sources.json")
    mutants=read(root/"reports/exp76-fast-mutations.json")
    technical=read(root/"reports/exp76-fast-technical-mutations.json")
    first_boot=read(root/"reports/exp76-round14-qemu-early-panic.json")
    round16=read(root/"reports/exp76-round16-scm-off-build-smoke.json")
    round17=read(root/"reports/exp76-round17-qemu-abc-early-abort.json")
    round18=read(root/"reports/exp76-round18-swork-atomic-caller.json")
    round19=read(root/"reports/exp76-round19-swork-build-boot.json")
    round20=read(root/"reports/exp76-round20-initcall-nohz-irq.json")
    round22=read(root/"reports/exp76-sched-reconciliation.json")
    scope_contract=read(root/"reports/exp76-rt-scope-handoff.json")
    ccache=read(root/"reports/exp76-ccache-three-full-images.json")
    reach=read(root/"reports/clang21-reachable-at-build.json")
    e2=read(root/"reports/exp76-e2-actionable-triage.json")
    assert sched["total"]==41 and sched["port_required"]==16
    assert sched["pending"]==25
    assert kconfig["before_submodule"]["missing_source_paths_count"]==1
    assert kconfig["after_submodule"]["missing_source_paths_count"]==0
    assert mutants["detected_count"]==1 and mutants["total_mutations"]==10
    assert technical["detected"]==10 and technical["total"]==10
    assert technical["production_kbuild_gate_qualified"] is False
    assert first_boot["qemu"]["guest_console_generated"] is True
    assert first_boot["status"]=="KERNEL_ENTERED_PANIC_BEFORE_INIT"
    assert round16["qemu_rt"]["build_step"]=="PASS"
    assert round16["qemu_rt"]["config_diff_critical_count"]==0
    assert round16["qemu_rt"]["smoke_console"]["bytes"]==0
    assert round16["pipa_rt"]["build_step"]=="PASS"
    assert round16["pipa_rt"]["same_config_sha_as_round12"] is True
    assert round17["abc"]["cases"][0]["panic"] is True
    assert round17["abc"]["cases"][2]["panic"] is True
    assert round17["abc"]["cases"][1]["console_bytes"]==0
    assert round17["separate_scmoff_execution_trace"]["far"]=="0x28"
    assert round18["scm_off_trace"]["far"]=="0x28"
    assert round18["symbol_identification"]["direct_caller"].startswith("swork_queue")
    assert round18["cpu_register_proof"]["caller_glob_worker_x9"]=="0x0"
    assert round18["cpu_register_proof"]["atomic_x0"]=="0x28"
    assert round18["vmlinux_scmoff_archived"] is False
    assert round19["reject_audit"]["new_port_verified_hunks"]==0
    assert round19["reject_audit"]["source_contains"][0]=="swork_queue(&timer_update_swork)"
    assert round19["qemu_rt"]["image_build_exit"]==0
    assert round19["ci"]["smoke_exit_code"]==124
    assert round19["guest_stall_diagnostic"]["events"][0]["pc_symbol"]=="cpu_do_idle+0x8"
    assert round19["guest_stall_diagnostic"]["events"][1]["pc_symbol"]=="cpu_do_idle+0x8"
    assert round19["publication"]["vmlinux_and_system_map_published"] is True
    assert round20["tests"]["initcall_nosmp"]["initcall_calling_count"]==0
    assert round20["tests"]["nohz_off"]["guest_running"] is False
    assert round20["tests"]["irq_trace"]["qemu_irq_exception5_count"]==20
    assert round20["rejected_inventory"]["matched_hunks"]==80
    assert round20["rejected_inventory"]["matched_files"]==16
    assert round20["nonrt_control"]["nonrt_image_found"] is False
    assert round22["hunks"][0]["source_status"]=="ALREADY_SATISFIED_SOURCE_NOOP"
    assert round22["hunks"][0]["applied"] is False
    assert round22["new_port_verified"]==0
    assert round22["sysrq_pty"]["guest_stack_pid1_found"] is False
    assert round22["sysrq_qmp_break"]["sysrq_t_dump_found"] is False
    assert scope_contract["rt_handoff_ready"] is False
    assert len(ccache["results"])==3 and ccache["gates"]["warm_same_commit_gt_90pct"]
    assert ccache["gates"]["strict_cold_zero_hits"] is False
    assert reach["files_actually_compiled_pipa_rt"]==1
    assert reach["files_actually_compiled_qemu_rt"]==2
    assert e2["summary"]["semantic_required"]==2 and e2["summary"]["context_drift"]==4
    owner="Rook"
    esc="nywuer777 (mantenedor CI)"
    review="2026-11-06T18:00:00-03:00"
    def item(state,evidence,**other):
        return {"state":state,"evidence_path":evidence,
                "owner":owner,"escalation_owner":esc,
                "deadline_at":None if state=="DONE" else review,
                "updated_at":generated_at,**other}
    classified=sched["port_required"]+sched["port_verified"]+sched["equivalent_verified"]+sched["not_applicable"]
    items={
        "1_series_rt":item("DONE","github-actions/41886188342/exp76-rt-series-provenance-NOFLASH",
                           series_patch_count=351,
                           series_sha256="488b12a98fa58a1e237afee8d22b390977fa00cf809a70accd582473b51dcbca"),
        "2_gap_git":item("DONE","github-actions/41886188342/reports/provenance.json",
                         e404_only_commits=67337,stable_only_commits=8142,
                         merge_base="67aefbfee14b1f29cb4529911aef7322899ecc8b"),
        "3_method":item("DONE","reports/exp76-scheduler-batch1.json",
                         decision="CONSOLIDATED",
                         reason="351 ordered RT patches, 67337 E404-only commits, 209 consolidated reject hunks",
                         reconsider_trigger="at least 63 of 157 BOOT_CRITICAL hunks record >4h real investigation each"),
        "4_hunks":item("PARTIAL","reports/exp76-scheduler-batch1.json",
                        boot_critical_total=157,non_blocking_port_total=52,
                        classified=classified,pending=157-classified,
                        scheduler_pending=sched["pending"],semantically_resolved=0,
                        e2_triage_path="reports/exp76-e2-actionable-triage.json",
                        e2_semantic_required=2,e2_context_drift=4,e2_port_ready=0,
                        swork_reject_hunk="kernel/time/timer.c.rej hunk 1",
                        swork_reject_source_status="RESTORED_PREVIOUSLY_STAGE34",
                        swork_runtime_repair_applied=True,
                        swork_port_verified=False,
                        new_port_verified_count=0,
                        r19_evidence="reports/exp76-round19-swork-build-boot.json",
                        r20_rejected_boot_family_files=round20["rejected_inventory"]["matched_files"],
                        r20_rejected_boot_family_hunks=round20["rejected_inventory"]["matched_hunks"],
                        r20_rejected_counts_are_not_pending_port_count=True,
                        r22_h10=round22["hunks"][0]["hunk_id"],
                        r22_h10_status=round22["hunks"][0]["source_status"],
                        r22_h10_source_change_applied=False,
                        r22_h10_port_verified=False,
                        r22_reconciliation_report="reports/exp76-sched-reconciliation.json"),
        "5_qemu":item("FAIL_PRE_INITCALL_SYSRQ_NO_TASK_DUMP",
                       "github-actions/42250617858/exp76-qemu-rt-functional-NOFLASH",
                       blocker="R22_H10_SOURCE_ALREADY_SATISFIED; MAGIC_SYSRQ_ENABLED; PTY_AND_QMP_BREAK_SENT_NO_TASK_DUMP; GUEST_NEVER_REACHED_INIT",
                       latest_qemu_run_id=round22["hunks"][0]["build_run_id"],
                       r22_h10_status=round22["hunks"][0]["source_status"],
                       r22_magic_sysrq_y=True,
                       r22_sysrq_serial_y=True,
                       r22_sysrq_pty=round22["sysrq_pty"],
                       r22_sysrq_qmp_break=round22["sysrq_qmp_break"],
                       r22_pid1_stack_captured=False,
                       r22_taskdump_unsupported_in_guest_boot_stage=True,
                       test_initcall_debug_nosmp=round20["tests"]["initcall_nosmp"],
                       test_nohz_off=round20["tests"]["nohz_off"],
                       test_qemu_irq=round20["tests"]["irq_trace"],
                       nonrt_control_status=round20["nonrt_control"]["status"],
                       initcall_debug_calling_count=0,
                       cpu0_irq_exception_count=20,
                       irq_last_elr_symbol="arch_cpu_idle+0x10",
                       earliest_last_printk_source=round20["source_phase_evidence"]["empty_cluster_printk"],
                       qemu_image_sha256=round22["hunks"][0]["qemu_image_sha256"],
                       last_guest_console_sha256=round22["hunks"][0]["boot_console_sha256"],
                       last_guest_console_bytes=round22["hunks"][0]["boot_console_bytes"],
                       last_guest_console_lines=round22["hunks"][0]["boot_console_lines"],
                       last_host_qemu_exit_code=round22["hunks"][0]["qemu_host_exit_code"],
                       guest_init_reached=False,
                       guest_running=False,
                       previous_null_swork_evidence_run_id=round18["cpu_register_proof"]["run_id"],
                       previous_null_swork_far=round18["cpu_register_proof"]["fault_far"],
                       r19_swork_source_status="STAGE34_ALREADY_RESTORED_HUNK1",
                       r19_swork_fix_source_commit=round19["source_order_repair"]["implementation_commit"],
                       r19_snapshot_run=round19["guest_stall_diagnostic"]["run_id"],
                       r19_snapshot_artifact=round19["guest_stall_diagnostic"]["artifact_id"],
                       r19_snapshot_pc_symbol="cpu_do_idle+0x8",
                       r19_snapshot_x30_caller="arch_cpu_idle+0xc",
                       r19_snapshot_smp1_and_smp4_same_pc=True,
                       r19_snapshot_limitations=round19["guest_stall_diagnostic"]["hmp_sampling_caveat"],
                       qemu_scm_policy="QEMU_ONLY_QCOM_SCM_N",
                       PIPA_RT_SCM_VALIDATED="NO_HARDWARE",
                       RT_SPIN_SLEEP_V3_GUEST="NOT_EXECUTED",
                       QEMU_RT_SCOPE=scope_contract["qemu_rt_scope"],
                       HANDOFF_TO_KAI_EXPECTS=scope_contract["handoff_to_kai_expects"],
                       latest_evidence_path="reports/exp76-sched-reconciliation.json",
                       kconfig_audit_path="reports/e404-kconfig-missing-sources.json"),
        "6_build_rt":item("PARTIAL_PASS",
                          "github-actions/42250522391/exp76-pipa-rt-unchanged-scm-build-NOFLASH",
                          build_rt_images_generated="PASS",
                          build_aggregate_step="QEMU_SMOKE_TIMEOUT_AFTER_BOTH_RT_IMAGES_COMPILED",
                          pipa_rt_image_sha256=round22["pipa_build"]["image_sha256"],
                          qemu_rt_image_sha256=round22["hunks"][0]["qemu_image_sha256"],
                          pipa_rt_vmlinux_sha256=round22["pipa_build"]["vmlinux_sha256"],
                          qemu_rt_vmlinux_sha256=round22["hunks"][0]["qemu_vmlinux_sha256"],
                          pipa_rt_system_map_sha256=round19["pipa_rt"]["system_map_sha256"],
                          qemu_rt_system_map_sha256=round19["qemu_rt"]["system_map_sha256"],
                          pipa_rt_effective_config_sha256=round19["pipa_rt"]["config_sha256"],
                          qemu_rt_effective_config_sha256=round19["qemu_rt"]["config_sha256"],
                          pipa_rt_qcom_scm="y",qemu_rt_qcom_scm="n",
                          pipa_rt_scm_hardware="NO_HARDWARE",
                          PIPA_RT_SCOPE=scope_contract["pipa_rt_scope"],
                          vmlinux_system_map_published=True,
                          image_source_run=round22["hunks"][0]["build_run_id"],
                          toolchain="ANDROID_CLANG_21_r563880c",
                          abi_diff="NOT_MEASURED",
                          runtime_functional="FAIL_PRE_INITCALL_SYSRQ_NO_TASK_DUMP"),
        "7_fast_ccache":item("PARTIAL","reports/exp76-ccache-three-full-images.json",
                             fast_p95_s=0.226974,
                             fast_benchmark_run=41897623229,
                             fast_classification=mutants["classification"],
                             fast_mutations_detected=mutants["detected_count"],
                             fast_technical_gate="FAIL_AS_TECHNICAL_GATE",
                             fast_technical_candidate="FIXTURE_CI_10_OF_10_PRODUCTION_REAL_KBUILD_UNWIRED",
                             fast_technical_fixture_run_id=technical["authoritative_ci"]["run_id"],
                             fast_technical_fixture_detected=technical["detected"],
                             ccache_full_images="MEASURED_WITH_COLD_ZERO_ASSERTION_FAILURE",
                             ccache_run_id=42020698390,
                             ccache_warm_same_commit_pct=ccache["results"][1]["hit_rate_pct"],
                             ccache_warm_five_line_commit_pct=ccache["results"][2]["hit_rate_pct"],
                             ccache_warm_same_commit_gt90=True,
                             ccache_changed_core_object_invalidation="NOT_VERIFIED"),
        "8_panel":item("DONE","reports/exp76-checklist.json",
                        provenance="Generated by tools/exp76-build-checklist.py",
                        git_versioned=True)
    }
    return {
        "schema_version":2, "generated_at":generated_at,
        "source_sha":source_sha, "scope":"RT_ONLY",
        "items":items,"out_of_scope_vendor_abi":{
            "state":"BLOCKED_OUT_OF_SCOPE",
            "owner":"Kai",
            "evidence_path":"arch/arm64/configs/vendor/pipa_defconfig:726",
            "blocker":"PIPA_MODULE_CONFIG_MISMATCH; stock vendor ABI baseline unavailable"},
        "RT_SCOPE_CONTRACT_PATH":"reports/exp76-rt-scope-handoff.json",
        "RT_FORENSIC_R18_PATH":"reports/exp76-round18-swork-atomic-caller.json",
        "RT_R19_SOURCE_AND_BOOT_REPORT":"reports/exp76-round19-swork-build-boot.json",
        "RT_R20_INITCALL_IRQ_REPORT":"reports/exp76-round20-initcall-nohz-irq.json",
        "RT_R22_H10_RECONCILIATION_REPORT":"reports/exp76-sched-reconciliation.json",
        "rt_handoff_ready":False,
        "reasons_not_ready":["4","5","6","7"],
        "readiness_rule":"RT handoff requires valid measured PASS of all in-scope gates"
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=Path("."))
    p.add_argument("--source-sha",required=True)
    p.add_argument("--generated-at",required=True)
    p.add_argument("--output",type=Path,default=Path("reports/exp76-checklist.json"))
    args=p.parse_args()
    d=generate(args.root,args.source_sha,args.generated_at)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(d,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"items":len(d["items"]),"reasons":d["reasons_not_ready"],
                      "source_sha":d["source_sha"],"rt_handoff_ready":d["rt_handoff_ready"]},indent=2))

if __name__=="__main__":
    main()
