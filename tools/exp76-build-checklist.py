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
                        e2_semantic_required=2,e2_context_drift=4,e2_port_ready=0),
        "5_qemu":item("FAIL_EARLY_SWORK_NULL_WORKER","github-actions/42199563450/exp76-rt-scm-off-instruction-trace-NOFLASH",
                       blocker="EARLY_NOHZ_TIMER_SWORK_QUEUE_LOADS_NULL_GLOBAL_WORKER; DATA_ABORT_FAR_0x28",
                       latest_qemu_run_id=round18["cpu_register_proof"]["run_id"],
                       register_trace_artifact_id=round18["cpu_register_proof"]["artifact_id"],
                       register_trace_x9=round18["cpu_register_proof"]["caller_glob_worker_x9"],
                       register_trace_atomic_x0=round18["cpu_register_proof"]["atomic_x0"],
                       RT_SPIN_SLEEP_V3_GUEST="NOT_EXECUTED_MISSING_RT_KO_AND_GUEST_SCRIPT",
                       abc_control_run_id=round17["source_runs"]["abc_run"],
                       trace_artifact_id=round17["separate_scmoff_execution_trace"]["artifact_id"],
                       trace_fault_far=round17["separate_scmoff_execution_trace"]["far"],
                       trace_fault_elr=round17["separate_scmoff_execution_trace"]["elr"],
                       trace_fault_image_offset=round17["separate_scmoff_execution_trace"]["image_instruction_offset"],
                       trace_fault_instruction=round17["separate_scmoff_execution_trace"]["instruction"],
                       trace_symbol_status="CROSS_BUILD_SWORK_QUEUE_PLUS_0X5C_AND_QEMU_RUNTIME_NULL_WORKER_CONFIRMED; EXACT_SCM_OFF_ELF_NOT_ARCHIVED",
                       trace_caller_identified_by_unique_code_sequence="swork_queue+0x5c",
                       trace_atomic_helper="__ll_sc___cmpxchg_case_acq_4+0x4",
                       trace_candidate_null_worker="glob_worker loaded as zero before lock at +0x28",
                       trace_caller_evidence_path="reports/exp76-round18-swork-atomic-caller.json",
                       next_build_vmlinux_systemmap_required=True,
                       last_guest_console_sha256=round16["qemu_rt"]["smoke_console"]["sha256"],
                       last_guest_console_bytes=0,last_guest_console_lines=0,
                       last_host_qemu_exit_code=0,
                       previous_kernel_entry_run_id=first_boot["run_id"],
                       previous_kernel_panic_sha256=first_boot["evidence_sha256"]["console_raw"],
                       guest_init_reached=False,
                       qemu_scm_policy="QEMU_ONLY_QCOM_SCM_N_EFFECTIVE_CONFIG_VERIFIED",
                       qemu_rt_validates_if_pass=["scheduler","RCU","locking","time","IRQ","mm","arch/arm64","init"],
                       qemu_rt_does_not_validate=["Qualcomm SCM TrustZone","physical PIPA firmware","PIPA hardware boot"],
                       QEMU_RT_SCOPE=scope_contract["qemu_rt_scope"],
                       HANDOFF_TO_KAI_EXPECTS=scope_contract["handoff_to_kai_expects"],
                       pipa_rt_scm_expected="CONFIG_QCOM_SCM=y",
                       pipa_rt_scm_validated="NO_HARDWARE",
                       latest_evidence_path="reports/exp76-round18-swork-atomic-caller.json",
                       kconfig_audit_path="reports/e404-kconfig-missing-sources.json"),
        "6_build_rt":item("PARTIAL_PASS","github-actions/42065541890/exp76-pipa-rt-unchanged-scm-build-NOFLASH",
                          build_rt_images_generated="PASS",
                          build_aggregate_step="QEMU_SMOKE_FAILED_AFTER_IMAGES_GENERATED",
                          pipa_rt_image_sha256=round16["pipa_rt"]["image_sha256"],
                          qemu_rt_image_sha256=round16["qemu_rt"]["image_sha256"],
                          pipa_rt_effective_config_sha256=round16["pipa_rt"]["config_sha256"],
                          qemu_rt_effective_config_sha256=round16["qemu_rt"]["config_sha256"],
                          pipa_rt_qcom_scm="y",qemu_rt_qcom_scm="n",
                          pipa_rt_scm_hardware="NO_HARDWARE",
                          PIPA_RT_SCOPE=scope_contract["pipa_rt_scope"],
                          next_build_artifact_contract=scope_contract["future_build_artifact_contract"],
                          image_source_run=round16["workflow_run_id"],
                          toolchain="ANDROID_CLANG_21_r563880c",
                          abi_diff="NOT_MEASURED",
                          runtime_functional="FAIL_EARLY_SWORK_NULL_WORKER"),
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
