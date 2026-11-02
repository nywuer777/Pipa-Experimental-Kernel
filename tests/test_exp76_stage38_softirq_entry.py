#!/usr/bin/env python3
# Python 3 / GitHub Actions Ubuntu / EXP76 Stage38 softirq reject-merge regression / NO FLASH
"""Test exact RT conditional restoration, unchanged non-RT path, and drift gates."""
from __future__ import annotations

import json
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/exp76-rt-stage38-softirq-entry.py"
M = runpy.run_path(str(TOOL), run_name="stage38_test")
NAME = M["NAME_ANCHOR"]
WAKE = M["WAKE_ANCHOR"]
KSOFT = M["KSOFTIRQD_ANCHOR"]
REJECT = """diff a/kernel/softirq.c b/kernel/softirq.c (rejected hunks)
@@ -56,12 +59,136 @@
 DEFINE_PER_CPU(struct task_struct *, ksoftirqd);
+#ifdef CONFIG_PREEMPT_RT_FULL
+#define TIMER_SOFTIRQS ((1 << TIMER_SOFTIRQ) | (1 << HRTIMER_SOFTIRQ))
+DEFINE_PER_CPU(struct task_struct *, ktimer_softirqd);
+#endif
 const char * const softirq_to_name[NR_SOFTIRQS] = {
        "HI"
 };
+#ifdef CONFIG_NO_HZ_COMMON
+# ifdef CONFIG_PREEMPT_RT_FULL
+static inline void softirq_set_runner(unsigned int sirq) { real_set(sirq); }
+static inline void softirq_clr_runner(unsigned int sirq) { real_clear(sirq); }
+void softirq_check_pending_idle(void) { check_pending(); }
+# else
+void softirq_check_pending_idle(void) { check_nort_pending(); }
+# endif
+#else /* !CONFIG_NO_HZ_COMMON */
+static inline void softirq_set_runner(unsigned int sirq) { }
+static inline void softirq_clr_runner(unsigned int sirq) { }
+#endif
@@ -77,6 +204,38 @@
 void wakeup_softirqd(void)
 {
 }
+#ifdef CONFIG_PREEMPT_RT_FULL
+static void wakeup_timer_softirqd(void) { wake_timer(); }
+#endif
+static void handle_softirq(unsigned int vec_nr) { process_vector(vec_nr); }
+#ifndef CONFIG_PREEMPT_RT_FULL
@@ -92,6 +251,47 @@
 int ksoftirqd_running(void)
 {
 }
+static inline int ksoftirqd_softirq_pending(void) { return local_softirq_pending(); }
+static void handle_pending_softirqs(u32 pending) { handle_bits(pending); }
+static void run_ksoftirqd(unsigned int cpu) { run_pending(cpu); }
@@ -251,10 +451,8 @@
 context
@@ -273,36 +471,7 @@
 context
@@ -359,6 +831,7 @@ void irq_enter(void)
 static inline void invoke_softirq(void)
 {
+#ifndef CONFIG_PREEMPT_RT_FULL
 	if (!force_irqthreads) {
"""
BODY = (
    KSOFT + "\n" + NAME + "\n"
    + WAKE + "\n"
    + "/* preempt_count and SOFTIRQ_OFFSET usage: */\n"
    + "static void legacy_bh(void) { do_legacy_bh(); }\n"
    + "void nonrt_dispatch(void) { handle_pending_softirqs(local_softirq_pending()); }\n"
    + M["RT_ELSE"] + "\n"
    + "static void rt_bh(void) { handle_softirq(0); softirq_set_runner(0); }\n"
    + "#endif /* PREEMPT_RT_FULL */\n"
    + "static inline void invoke_softirq(void)\n"
    + "{\n\n"
    + "\tif (!force_irqthreads) {\n"
    + "\t\tserve_nonrt_softirq();\n"
    + "\t}\n"
    + M["INVOKE_RT_ELSE"] + "\n"
    + "\twakeup_softirqd();\n"
    + "#endif /* PREEMPT_RT_FULL */\n"
    + "}\n"
)


def put(root: Path, rel: str, contents: str) -> None:
    dest = root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(contents, encoding="utf-8")


def seed(root: Path) -> None:
    put(root, M["SOFTIRQ"], BODY)
    put(root, M["REJECT"], REJECT)
    put(root, M["PENDING"], "pending\n")
    for n in range(62):
        put(root, f"pending/{n:02d}.rej", "pending\n")


def run(root: Path, mode: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), "--tree", str(root),
         "--report", str(root / "report"), "--mode", mode],
        capture_output=True, text=True,
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        good = base / "good"
        seed(good)
        checked = run(good, "verify")
        assert checked.returncode == 0, checked.stderr
        assert (good / M["SOFTIRQ"]).read_text() == BODY
        applied = run(good, "apply")
        assert applied.returncode == 0, applied.stderr
        source = (good / M["SOFTIRQ"]).read_text()
        for marker in (
            "DEFINE_PER_CPU(struct task_struct *, ktimer_softirqd);",
            "static inline void softirq_set_runner(unsigned int sirq)",
            "static void handle_softirq(unsigned int vec_nr)",
            "static inline int ksoftirqd_softirq_pending(void)",
            "static void run_ksoftirqd(unsigned int cpu)",
            "#ifndef CONFIG_PREEMPT_RT_FULL",
            M["RT_ELSE"],
        ):
            assert marker in source
        assert source.index("#ifndef CONFIG_PREEMPT_RT_FULL") < source.index(M["RT_ELSE"])
        assert "static void legacy_bh(void)" in source
        assert "static void rt_bh(void)" in source
        manifest = json.loads((good / "report/stage38-status.json").read_text())
        assert manifest["original_rejected_hunks_consumed"] == 4
        assert manifest["stage39_invoke_softirq_guard_restored"] is True
        assert source.count("#ifndef CONFIG_PREEMPT_RT_FULL") == 2
        assert source.index("static inline void invoke_softirq(void)") < source.rindex("#ifndef CONFIG_PREEMPT_RT_FULL")
        assert source.rindex("#ifndef CONFIG_PREEMPT_RT_FULL") < source.index(M["INVOKE_RT_ELSE"])
        assert manifest["preprocessor_branches_balanced"] is True
        assert manifest["conditional_directives_checked"] >= 9
        assert manifest["remaining_rejected_files"] == 64
        assert manifest["full_softirq_semantics_verified"] is False
        assert not manifest["kernel_built"] and not manifest["flash_ready"]

        drift = base / "unpaired-else"
        seed(drift)
        put(drift, M["SOFTIRQ"], BODY.replace(M["RT_ELSE"], "/* removed */"))
        assert run(drift, "apply").returncode != 0
        assert (drift / M["SOFTIRQ"]).read_text() != source

        mismatch = base / "missing-vector-handler"
        seed(mismatch)
        put(mismatch, M["REJECT"], REJECT.replace(
            "+static void handle_softirq(unsigned int vec_nr)",
            "+static void handler_missing(unsigned int vec_nr)"
        ))
        assert run(mismatch, "apply").returncode != 0

        duplicate = base / "already-ported"
        seed(duplicate)
        put(duplicate, M["SOFTIRQ"], BODY + "\n#ifndef CONFIG_PREEMPT_RT_FULL\n#endif\n")
        assert run(duplicate, "apply").returncode != 0

        invalid = base / "missing-reject"
        seed(invalid)
        (invalid / "pending/00.rej").unlink()
        assert run(invalid, "apply").returncode != 0

        orphan_endif = base / "extra-endif"
        seed(orphan_endif)
        put(orphan_endif, M["SOFTIRQ"], BODY + "\n#endif /* stray */\n")
        assert run(orphan_endif, "apply").returncode != 0

        missing_invoke_reject = base / "missing-invoke-reject"
        seed(missing_invoke_reject)
        put(missing_invoke_reject, M["REJECT"], REJECT.replace(
            "+#ifndef CONFIG_PREEMPT_RT_FULL\n \tif (!force_irqthreads) {",
            "+#ifndef CONFIG_PREEMPT_RT_OTHER\n \tif (!force_irqthreads) {",
        ))
        assert run(missing_invoke_reject, "apply").returncode != 0

        missing_invoke_source = base / "missing-invoke-source"
        seed(missing_invoke_source)
        put(missing_invoke_source, M["SOFTIRQ"], BODY.replace(
            "\tif (!force_irqthreads) {", "\tif (missing_vendor_condition) {",
        ))
        assert run(missing_invoke_source, "apply").returncode != 0

        split = base / "missing-name-anchor"
        seed(split)
        put(split, M["SOFTIRQ"], BODY.replace(NAME, "const char * wrong_name;"))
        assert run(split, "apply").returncode != 0
    print("EXP76_STAGE39_SOFTIRQ_DUAL_GUARD_TESTS=9_PASS; FLASH_READY=false")


if __name__ == "__main__":
    main()
