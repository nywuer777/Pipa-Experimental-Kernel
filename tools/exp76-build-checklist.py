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
    ccache=read(root/"reports/exp76-ccache-three-full-images.json")
    reach=read(root/"reports/clang21-reachable-at-build.json")
    e2=read(root/"reports/exp76-e2-actionable-triage.json")
    assert sched["total"]==41 and sched["port_required"]==16
    assert sched["pending"]==25
    assert kconfig["before_submodule"]["missing_source_paths_count"]==1
    assert kconfig["after_submodule"]["missing_source_paths_count"]==0
    assert mutants["detected_count"]==1 and mutants["total_mutations"]==10
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
        "5_qemu":item("NOT_READY","github-actions/42021714463/exp76-qemu-rt-functional-NOFLASH",
                       blocker="BUILD_ASSERTION_COLD_CACHE_HITS_PREVENTED_GUEST; modules, initramfs and boots skipped",
                       latest_qemu_run_id=42021714463,
                       kconfig_audit_path="reports/e404-kconfig-missing-sources.json"),
        "6_build_rt":item("PARTIAL_PASS","github-actions/41930944374/exp76-qemu-rt-functional-NOFLASH",
                          build_rt_images_generated="PASS",
                          build_rt_compiled_end_to_end="PASS_WITH_INSTRUMENTATION_CAVEAT",
                          build_aggregate_step="FAIL_CCACHE_STATS",
                          pipa_rt_image_sha256="f818b0be240b738864669a44015d6fd1d7e1b24bd6154c5199394caacdcaa83f",
                          qemu_rt_image_sha256="8b5f5cce769e35fb469510cc58e6881504473483418da12933c467ad454e50d1",
                          toolchain="ANDROID_CLANG_21_r563880c",
                          abi_diff="NOT_MEASURED",
                          runtime_functional="NOT_READY"),
        "7_fast_ccache":item("PARTIAL","reports/exp76-ccache-three-full-images.json",
                             fast_p95_s=0.226974,
                             fast_benchmark_run=41897623229,
                             fast_classification=mutants["classification"],
                             fast_mutations_detected=mutants["detected_count"],
                             fast_technical_gate="FAIL_AS_TECHNICAL_GATE",
                             fast_technical_candidate="PUBLISHED_FIXTURE_CI_PENDING_REAL_KBUILD_UNWIRED",
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
