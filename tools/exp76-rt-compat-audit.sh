#!/usr/bin/env bash
# Bash / Ubuntu GitHub Actions / EXP76 E404+EXP overlays RT compatibility audit / NO FLASH
set -Eeuo pipefail
export GIT_TERMINAL_PROMPT=0

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
REPORT="$ROOT/exp76-rt-report"
mkdir -p "$REPORT"
BASE="fed88a6024cd4d46c52eda607a95d97d7371ba81"
RT_URL="https://cdn.kernel.org/pub/linux/kernel/projects/rt/4.19/patch-4.19.325-rt140.patch.xz"
RT_SHA="c79d3efb5daccc5a3f58d502189eadc7dd31a962215ca0a16fa8c3eb98cd88ce"
KERNEL_URL="https://github.com/kvsnr113/xiaomi_sm8250_kernel_e404.git"
printf '%s\n' "$RT_URL" > "$REPORT/rt-source-url.txt"
printf '4.19.325-rt140 => E404 4.19.404R: exact-version match is FALSE\n' > "$REPORT/version-mismatch.txt"

curl --fail --location --retry 3 --retry-delay 5 "$RT_URL" --output "$ROOT/exp76-rt.patch.xz"
echo "$RT_SHA  exp76-rt.patch.xz" | sha256sum -c - | tee "$REPORT/official-archive-hash.txt"
xz -t exp76-rt.patch.xz
xz -dc exp76-rt.patch.xz > exp76-rt.patch
sha256sum exp76-rt.patch > "$REPORT/decompressed-patch-sha256.txt"

git clone --filter=blob:none "$KERNEL_URL" exp76-e404
git -C exp76-e404 checkout --detach "$BASE"
test "$(git -C exp76-e404 rev-parse HEAD)" = "$BASE"
git -C exp76-e404 rev-parse HEAD > "$REPORT/e404-base-commit.txt"

# Reconstruct only source overlays available as standalone EXP tools.
# EXP75 CI-only compatibility shims, KernelSU submodule and resolved config
# are NOT reproduced. A passing textual check is NOT a build.
git clone --shared exp76-e404 exp76-overlay
echo '548ebb47ad0febe3c4541b9e93f2233bb9188c78d8f9ec298dd397a11216b852  PipaExperimental-EXP01-source.zip' | sha256sum -c -
git -C exp76-overlay apply --check "$ROOT/patches/0001-pipa-exp01-schedutil-rate-limit.patch"
git -C exp76-overlay apply "$ROOT/patches/0001-pipa-exp01-schedutil-rate-limit.patch"
python3 tools/exp24-apply-ethernet.py --source configs/ethernet.config --kernel "$ROOT/exp76-overlay" --out "$ROOT/exp76-overlay-out" --mode apply > "$REPORT/ethernet-overlay.log" 2>&1
python3 tools/exp25-apply-touch.py --kernel "$ROOT/exp76-overlay" --mode apply > "$REPORT/touch-overlay.log" 2>&1
python3 tools/exp76-fix-uname.py --kernel "$ROOT/exp76-overlay" --mode apply | tee "$REPORT/uname-fix.log"
python3 tools/exp76-fix-uname.py --kernel "$ROOT/exp76-overlay" --mode verify
git -C exp76-overlay diff --check
git -C exp76-overlay diff --binary > "$REPORT/exp-source-overlays.patch"
sha256sum "$REPORT/exp-source-overlays.patch" > "$REPORT/exp-source-overlays.sha256"

for variant in e404 overlay; do
    source="exp76-e404"
    [ "$variant" = overlay ] && source="exp76-overlay"

    git clone --shared "$source" "exp76-trial-$variant"
    if [ "$variant" = overlay ]; then
        git -C "exp76-trial-$variant" apply "$REPORT/exp-source-overlays.patch"
    fi

    mkdir -p "$REPORT/$variant"
    if git -C "exp76-trial-$variant" apply --check "$ROOT/exp76-rt.patch" > "$REPORT/$variant/apply-check.log" 2>&1; then
        printf 'PASS\n' > "$REPORT/$variant/apply-check-status.txt"
    else
        printf 'FAIL\n' > "$REPORT/$variant/apply-check-status.txt"
    fi

    if git -C "exp76-trial-$variant" apply --reject "$ROOT/exp76-rt.patch" > "$REPORT/$variant/apply-reject.log" 2>&1; then
        printf 'PASS\n' > "$REPORT/$variant/apply-reject-status.txt"
    else
        printf 'FAIL\n' > "$REPORT/$variant/apply-reject-status.txt"
    fi

    find "exp76-trial-$variant" -type f -name '*.rej' -print | sed -e "s#^exp76-trial-$variant/##" -e 's#\.rej$##' | sort > "$REPORT/$variant/rejected-paths.txt"
    wc -l < "$REPORT/$variant/rejected-paths.txt" | tr -d ' ' > "$REPORT/$variant/rejected-count.txt"

    python3 - "$REPORT/$variant" <<'PY'
# Python 3 / GitHub Actions / classify patch rejects for manual review
import csv
import pathlib
import sys

directory = pathlib.Path(sys.argv[1])
paths = directory.joinpath("rejected-paths.txt").read_text().splitlines()
def subsystem(path):
    groups = (
        ("kernel/sched/", "scheduler"), ("kernel/locking/", "locking"),
        ("kernel/irq/", "irq"), ("kernel/rcu/", "rcu"),
        ("arch/arm64/", "arm64"), ("drivers/", "drivers"),
        ("mm/", "memory"),
    )
    return next((name for prefix, name in groups if path.startswith(prefix)), "other")
with (directory / "rejected-paths.csv").open("w", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow(("file", "subsystem", "semantic_review"))
    writer.writerows((p, subsystem(p), "REQUIRED") for p in paths)
PY
done

python3 tools/exp76-rt-conflict-report.py \
    --report "$REPORT" \
    --e404-trial "$ROOT/exp76-trial-e404" \
    --e404-paths "$REPORT/e404/rejected-paths.txt" \
    --overlay-trial "$ROOT/exp76-trial-overlay" \
    --overlay-paths "$REPORT/overlay/rejected-paths.txt" | tee "$REPORT/conflict-priority-summary.json"

# Stage-1 only: resolve two exact, SHA-pinned rejected hunks in the EXP overlay checkout.
# Keep the full original rejection manifest above as immutable evidence.
python3 tools/exp76-rt-stage1-port.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage1" \
    --mode apply | tee "$REPORT/stage1-port.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 80
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_RT_STAGE1=2_EXACT_HUNKS_PORTED; REMAINING_REJECTED_FILES=80; KERNEL_BUILT=false; FLASH_READY=false' | tee "$REPORT/stage1-gate.txt"

# Stage 2: add the ARM64 preempt_lazy_count field only if the exact upstream
# rejected hunk and prerequisite Stage1 feature select match.
# Capture rtmutex/spinlock API excerpts for semantic reconciliation.
python3 tools/exp76-rt-stage2-port.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage2" \
    --mode apply | tee "$REPORT/stage2-port.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 79
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_RT_STAGE2=1_ARM64_FIELD_PORTED; REMAINING_REJECTED_FILES=79; KERNEL_BUILT=false; FLASH_READY=false' | tee "$REPORT/stage2-gate.txt"

# Stage3: reconcile one exact rtmutex waiter/ww_ctx hunk against the actual
# E404 three-argument deadlock helper, preserving the original reject audit.
python3 tools/exp76-rt-stage3-rtmutex.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage3" \
    --mode apply | tee "$REPORT/stage3-port.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 78
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_RT_STAGE3=RTMUTEX_WW_CTX_PORTED; REMAINING_REJECTED_FILES=78; KERNEL_BUILT=false; FLASH_READY=false' | tee "$REPORT/stage3-gate.txt"

# Stage4 only: guard legacy read/write spinlock wrappers out of PREEMPT_RT_FULL.
# Keep the vendor raw spin operations and defer spinlock_types.h API split.
python3 tools/exp76-rt-stage4-spinlock.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage4" \
    --mode apply | tee "$REPORT/stage4-port.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 77
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_RT_STAGE4=SPINLOCK_LEGACY_GUARD_PORTED; REMAINING_REJECTED_FILES=77; SPINLOCK_TYPES_HEADER=BLOCKED; KERNEL_BUILT=false; FLASH_READY=false' | tee "$REPORT/stage4-gate.txt"

# Type/lockdep ABI review before altering spinlock_types.h (no source mutation).
python3 tools/exp76-spinlock-type-abi-audit.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/spinlock-type-abi" | tee "$REPORT/spinlock-type-abi.log"
test -f "$ROOT/exp76-trial-overlay/include/linux/spinlock_types.h.rej"
echo 'EXP76_SPINLOCK_HEADER=ABI_REVIEW_ONLY; HEADER_PORT=BLOCKED; KERNEL_BUILT=false; FLASH_READY=false' | tee "$REPORT/spinlock-type-gate.txt"

# Stage5: preserve E404 lockdep wait_type and nonRT spinlock initializer
# while switching to upstream RT split headers. Source-only; no build.
python3 tools/exp76-rt-stage5-spinlock-types.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage5" \
    --mode apply | tee "$REPORT/stage5-port.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 76
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_RT_STAGE5=SPINLOCK_TYPE_SPLIT_SOURCE_PORT; REMAINING_REJECTED_FILES=76; ABI_BUILD_UNVERIFIED=true; KERNEL_BUILT=false; FLASH_READY=false' | tee "$REPORT/stage5-gate.txt"

# Stage6: two vendor-equivalent IRQ_WORK_HARD_IRQ hunks require no code
# mutation; add only the source-verified swork include. All rejects SHA-locked.
python3 tools/exp76-rt-stage6-irq-work.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage6" \
    --mode apply | tee "$REPORT/stage6-port.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 73
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_RT_STAGE6=IRQ_WORK_VENDOR_EQUIVALENCE_AND_SWORK_INCLUDE; REMAINING_REJECTED_FILES=73; KERNEL_BUILT=false; FLASH_READY=false' | tee "$REPORT/stage6-gate.txt"

# Stage7: link upstream RT locking implementations only under PREEMPT_RT_FULL,
# preserve vendor non-RT mutex/rwsem selection, and verify existing 3-arg
# percpu rwsem wait. Two original rejects, SHA256-pinned.
python3 tools/exp76-rt-stage7-locking.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage7" \
    --mode apply | tee "$REPORT/stage7-port.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 71
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_RT_STAGE7=LOCKING_MAKEFILE_AND_PERCPU_RCUWAIT; REMAINING_REJECTED_FILES=71; KERNEL_BUILT=false; FLASH_READY=false' | tee "$REPORT/stage7-gate.txt"

# Stage8: recognize only two E404 RCU vendor-equivalent hunks: already
# present header includes and IRQ_WORK atomic_set(). Preserve original
# complete reject manifest above; leave all 18 functional RCU hunks pending.
python3 tools/exp76-rt-stage8-rcu-equivalence.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage8" \
    --mode apply | tee "$REPORT/stage8-port.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 71
test "$(grep -c '^@@ -' "$ROOT/exp76-trial-overlay/kernel/rcu/tree.c.rej")" -eq 18
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_RT_STAGE8=2_RCU_HUNKS_ALREADY_VENDOR_EQUIVALENT; RCU_HUNKS_REMAINING=18; REJECTED_FILES=71; KERNEL_BUILT=false; FLASH_READY=false' | tee "$REPORT/stage8-gate.txt"

# Stage9: check newer E404 RCU generation and post-RT softirq/task ABI.
# This is evidence only, not an attempt to port old-flavor RT callbacks.
python3 tools/exp76-rt-stage9-rcu-softirq-abi.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage9" | tee "$REPORT/stage9-abi.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 71
echo 'EXP76_RT_STAGE9=RCU_GENERATION_DIFFERENCE_DOCUMENTED; RCU_PORT_PENDING=true; SOFTIRQ_PORT_PENDING=true; KERNEL_BUILT=false; FLASH_READY=false' | tee "$REPORT/stage9-gate.txt"

# Stage10: mark two rcuwait vendor-equivalent hunks and add rcuwait_active()
# without changing kernel/exit.c wakeup ABI or wait lifecycle semantics.
python3 tools/exp76-rt-stage10-rcuwait.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage10" \
    --mode apply | tee "$REPORT/stage10-port.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 71
test "$(grep -c '^@@ -' "$ROOT/exp76-trial-overlay/include/linux/rcuwait.h.rej")" -eq 2
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_RT_STAGE10=RCUWAIT_ACTIVE_PORTED; RCUWAIT_HUNKS_REMAINING=2; REJECTED_FILES=71; KERNEL_BUILT=false; FLASH_READY=false' | tee "$REPORT/stage10-gate.txt"

# Stage11: complete rcuwait lifecycle ONLY when the post-RT int wakeup
# and finish_rcuwait() implementations exactly match the linked contract.
python3 tools/exp76-rt-stage11-rcuwait-lifecycle.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage11" \
    --mode apply | tee "$REPORT/stage11-port.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 70
test ! -e "$ROOT/exp76-trial-overlay/include/linux/rcuwait.h.rej"
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_RT_STAGE11=RCUWAIT_LIFECYCLE_LINKED; REJECTED_FILES=70; KERNEL_BUILT=false; FLASH_READY=false' | tee "$REPORT/stage11-gate.txt"

# Stage12: retain E404's already-equivalent call_rcu_bh forwarding; protect
# the lockdep read-side helper with the RT guard already used in update.c.
python3 tools/exp76-rt-stage12-rcupdate.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage12" \
    --mode apply | tee "$REPORT/stage12-port.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 69
test ! -e "$ROOT/exp76-trial-overlay/include/linux/rcupdate.h.rej"
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_RT_STAGE12=RCUPDATE_BH_LOCKDEP_PORTED; REJECTED_FILES=69; KERNEL_BUILT=false; FLASH_READY=false' | tee "$REPORT/stage12-gate.txt"

# Stage13: retire two obsolete old-flavor RCU header hunks only when
# unified E404 synchronize_rcu_bh()/rcu_barrier_bh() wrappers are verified.
python3 tools/exp76-rt-stage13-unified-rcu.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage13" \
    --mode apply | tee "$REPORT/stage13-port.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 68
test ! -e "$ROOT/exp76-trial-overlay/include/linux/rcutree.h.rej"
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_RT_STAGE13=UNIFIED_RCU_BH_WRAPPERS_ALREADY_PRESENT; REJECTED_FILES=68; KERNEL_BUILT=false; FLASH_READY=false' | tee "$REPORT/stage13-gate.txt"

# Stage14: scheduler core already defines sleeper-aware __wake_q_*
# functions. Make public wake_q wrappers match the actual ABI.
python3 tools/exp76-rt-stage14-wake-q.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage14" \
    --mode apply | tee "$REPORT/stage14-port.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 67
test ! -e "$ROOT/exp76-trial-overlay/include/linux/sched/wake_q.h.rej"
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_RT_STAGE14=WAKE_QUEUE_ABI_LINKED; REJECTED_FILES=67; KERNEL_BUILT=false; FLASH_READY=false' | tee "$REPORT/stage14-gate.txt"

# Stage15: adapt RT lazy-preempt feature to the E404 #define SCHED_FEAT_*
# interface without changing vendor TTWU_QUEUE=0 for non-RT or RT configs.
python3 tools/exp76-rt-stage15-sched-features.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage15" \
    --mode apply | tee "$REPORT/stage15-port.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 66
test ! -e "$ROOT/exp76-trial-overlay/kernel/sched/features.h.rej"
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_RT_STAGE15=PREEMPT_LAZY_FEATURE_ABI_PORTED; REJECTED_FILES=66; KERNEL_BUILT=false; FLASH_READY=false' | tee "$REPORT/stage15-gate.txt"

# Compile the E404 scheduler feature header with a host C compiler for
# non-RT, RT/no-lazy and RT/lazy configurations (NOT a kernel compile).
python3 tools/exp76-stage15-feature-cc-preflight.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage15" | tee "$REPORT/stage15-host-c-preflight.log"

# Stage16: the upstream cpupri.c reject expects task_struct.cpus_ptr.
# E404 has cpus_allowed instead; inventory all already-applied RT users and
# retain the reject until full affinity ABI is reconciled across scheduler.
python3 tools/exp76-rt-stage16-affinity-abi.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage16" | tee "$REPORT/stage16-affinity-abi.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 66
test -f "$ROOT/exp76-trial-overlay/kernel/sched/cpupri.c.rej"
echo 'EXP76_RT_STAGE16=AFFINITY_ABI_BLOCKER_DOCUMENTED; REJECTED_FILES=66; BUILD_BLOCKED=true; FLASH_READY=false' | tee "$REPORT/stage16-gate.txt"

# Stage17: E404 already assigns WF_TTWU=0x08, unlike the old RT patch.
# Use collision-free 0x100 for WF_LOCK_SLEEPER; keep nr_pinned pending.
python3 tools/exp76-rt-stage17-wake-flags.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage17" \
    --mode apply | tee "$REPORT/stage17-wake-flags.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 66
test "$(grep -c '^@@ -' "$ROOT/exp76-trial-overlay/kernel/sched/sched.h.rej")" -eq 1
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_RT_STAGE17=COLLISION_FREE_WAKE_LOCK_FLAG_PORTED; REJECTED_FILES=66; NR_PINNED=PENDING; KERNEL_BUILT=false; FLASH_READY=false' | tee "$REPORT/stage17-gate.txt"

# Stage19: pinned Clang21 object build exposed header breakage. Reconcile
# vendor rwsem/RT header split, softirq branch closure, task state macros,
# missing sleeping_lock field and duplicate RCU pointer import. Source only.
python3 tools/exp76-rt-stage19-header-fixes.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage19" \
    --mode apply | tee "$REPORT/stage19-header-fixes.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 65
test ! -e "$ROOT/exp76-trial-overlay/include/linux/rwsem.h.rej"
test -e "$ROOT/exp76-trial-overlay/include/linux/interrupt.h.rej"
test -e "$ROOT/exp76-trial-overlay/include/linux/sched.h.rej"
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_RT_STAGE19=COMPILER_HEADER_FIXES_PORTED; REJECTED_FILES=65; SCHED_AFFINITY_BLOCKED=true; KERNEL_BUILT=false; FLASH_READY=false' | tee "$REPORT/stage19-gate.txt"










# Stage20: take exactly the remaining RT swap.h locallock include reject,
# and suppress vendor percpu-rwsem owner hints on PREEMPT_RT_FULL, which uses
# a different rw_semaphore representation. Non-RT ABI is unchanged.
python3 tools/exp76-rt-stage20-headers.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage20" \
    --mode apply | tee "$REPORT/stage20-header-abi.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 64
test ! -e "$ROOT/exp76-trial-overlay/include/linux/swap.h.rej"
test -e "$ROOT/exp76-trial-overlay/include/linux/sched.h.rej"
test -e "$ROOT/exp76-trial-overlay/kernel/sched/cpupri.c.rej"
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_RT_STAGE20=SWAP_LOCALLOCK_AND_RWSEM_OWNER_GUARDED; REJECTED_FILES=64; KERNEL_BUILT=false; FLASH_READY=false' | tee "$REPORT/stage20-gate.txt"


# Stage21: the older RT tree redirects rbtree.h to a second RCU publishing
# macro. Restore E404's original rcupdate.h include, preserving its existing
# sparse/RCU contract. The 64 remaining RT reject files are unchanged.
python3 tools/exp76-rt-stage21-rcu-include.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage21" \
    --mode apply | tee "$REPORT/stage21-rcu-include.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 64
test -f "$REPORT/stage21/stage21-status.json"
test -e "$ROOT/exp76-trial-overlay/kernel/sched/cpupri.c.rej"
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_RT_STAGE21=E404_RCU_INCLUDE_RESTORED; REJECTED_FILES=64; RCU_RUNTIME_PORT=PENDING; FLASH_READY=false' | tee "$REPORT/stage21-gate.txt"


# Stage26: E404 ARM64 uses embedded cpus_allowed/cpus_requested and copies
# task_struct by value on fork. Drop the obsolete RT cpus_ptr rebasing,
# without modifying scheduler core migration/affinity semantics.
python3 tools/exp76-rt-stage26-fork-affinity.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage26" \
    --mode apply | tee "$REPORT/stage26-fork-affinity.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 64
test -f "$REPORT/stage26/stage26-status.json"
test -f "$ROOT/exp76-trial-overlay/kernel/sched/cpupri.c.rej"
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_RT_STAGE26=FORK_VALUE_AFFINITY_RECONCILED; REJECTED_FILES=64; SCHEDULER_CORE_PENDING=true; FLASH_READY=false' | tee "$REPORT/stage26-gate.txt"


# Stage27: restore vendor embedded cpus_allowed ABI at the eight core.c sites
# changed by RT-140. RT migration-disable and task-state logic remain pending.
python3 tools/exp76-rt-stage27-core-affinity.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage27" \
    --mode apply | tee "$REPORT/stage27-core-affinity.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 64
test -f "$REPORT/stage27/stage27-status.json"
test -f "$ROOT/exp76-trial-overlay/kernel/sched/cpupri.c.rej"
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_RT_STAGE27=CORE_VENDOR_AFFINITY_RECONCILED; REJECTED_FILES=64; MIGRATE_DISABLE_PENDING=true; FLASH_READY=false' | tee "$REPORT/stage27-gate.txt"


# Stage28: the RT wait_task_inactive hunk invokes check_task_state without
# its matching locked helper. Restore the upstream state/saved_state comparison.
# Retain the migrate_disable compiler blocker until the full RT migration
# lifecycle is ported; do not insert a fake field or runtime stub.
python3 tools/exp76-rt-stage28-task-state.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage28" \
    --mode apply | tee "$REPORT/stage28-task-state.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 64
test -f "$REPORT/stage28/stage28-status.json"
test -f "$ROOT/exp76-trial-overlay/kernel/sched/cpupri.c.rej"
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_RT_STAGE28=TASK_STATE_HELPER_RESTORED; REJECTED_FILES=64; MIGRATE_DISABLE_PENDING=true; FLASH_READY=false' | tee "$REPORT/stage28-gate.txt"


# Stage29: the rejected upstream sched.h hunk requires true migration state
# in task_struct under CONFIG_SMP && CONFIG_PREEMPT_RT_BASE. Preserve the
# vendor's cpus_allowed/cpus_requested masks and initialize RT-only child
# fields in __sched_fork. Runtime migrate_disable/enable remains NOT ported.
python3 tools/exp76-rt-stage29-migration-abi.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage29" \
    --mode apply | tee "$REPORT/stage29-migration-abi.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 64
test -f "$REPORT/stage29/stage29-status.json"
test -f "$ROOT/exp76-trial-overlay/include/linux/sched.h.rej"
test -f "$ROOT/exp76-trial-overlay/kernel/sched/cpupri.c.rej"
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_RT_STAGE29=RT_TASK_FIELDS_AND_FORK_INIT_ONLY; REJECTED_FILES=64; RT_MIGRATION_RUNTIME_PORTED=false; FLASH_READY=false' | tee "$REPORT/stage29-gate.txt"


# Stage31: RT class patch changes task affinity to cpus_ptr even though E404
# has embedded cpus_allowed. Restore only those exact rt/fair/deadline sites.
python3 tools/exp76-rt-stage31-class-affinity.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage31" \
    --mode apply | tee "$REPORT/stage31-class-affinity.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 64
test -f "$REPORT/stage31/stage31-status.json"
test -f "$ROOT/exp76-trial-overlay/kernel/sched/cpupri.c.rej"
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_RT_STAGE31=VENDOR_SCHED_CLASSES_AFFINITY; REJECTED_FILES=64; MIGRATION_RUNTIME_PORTED=false; FLASH_READY=false' | tee "$REPORT/stage31-gate.txt"


# Stage34: RT partial patch converted timer_update_keys to swork, but
# its timers_update_nohz() queue/init hunk was rejected by E404 context.
# Restore the original upstream queue, initcall and explicit swork header.
# Do not fall back to ordinary workqueues (different PREEMPT_RT semantics).
python3 tools/exp76-rt-stage34-timer-swork.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage34" \
    --mode apply | tee "$REPORT/stage34-timer-swork.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 64
test -f "$REPORT/stage34/stage34-status.json"
test -f "$ROOT/exp76-trial-overlay/kernel/time/timer.c.rej"
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_RT_STAGE34=TIMER_SWORK_QUEUE_AND_INIT_RESTORED; REJECTED_FILES=64; RT_RUNTIME_UNVERIFIED=true; FLASH_READY=false' | tee "$REPORT/stage34-gate.txt"


# Stage35: restore exact two macro definitions from kernel.h.rej for
# PREEMPT_RT rtmutex's might_sleep_no_state_check() call. Preserve the
# special ___might_sleep debug semantics and non-debug might_resched.
python3 tools/exp76-rt-stage35-might-sleep.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage35" \
    --mode apply | tee "$REPORT/stage35-might-sleep.log"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 64
test -f "$REPORT/stage35/stage35-status.json"
test -f "$ROOT/exp76-trial-overlay/include/linux/kernel.h.rej"
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_RT_STAGE35=KERNEL_SLEEP_CHECK_MACROS_RESTORED; REJECTED_FILES=64; RT_RUNTIME_UNVERIFIED=true; FLASH_READY=false' | tee "$REPORT/stage35-gate.txt"


# Stage36: CPU hotplug's cpu_nr_pinned() depends on the whole rejected RT
# migration-disable lifecycle, rq->nr_pinned, and E404 affinity ABI port.
# Read-only inventory: refuse fake helper/counter implementations.
python3 tools/exp76-stage36-migration-contract.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage36" \
    --mode audit | tee "$REPORT/stage36-migration-contract.log"
test -f "$REPORT/stage36/stage36-status.json"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 64
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_STAGE36=RT_PINNING_LIFECYCLE_INVENTORIED; CPU_NR_PINNED_RUNTIME_MISSING=true; FLASH_READY=false' | tee "$REPORT/stage36-gate.txt"


# Stage38: RT patch applied its non-RT/RT #else in softirq.c, but
# the matching #ifndef and helper definitions are in 3 rejected hunks.
# Recover those actual upstream definitions, not an empty compatibility shim.
python3 tools/exp76-rt-stage38-softirq-entry.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage38" \
    --mode apply | tee "$REPORT/stage38-softirq-entry.log"
test -f "$REPORT/stage38/stage38-status.json"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 64
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_STAGE39=SOFTIRQ_RT_DUAL_GUARDS_PORTED; SOFTIRQ_RUNTIME_VERIFIED=false; FLASH_READY=false' | tee "$REPORT/stage38-gate.txt"


# Stage40: softirq runner (restored Stage38/39) references the RT-only
# task_struct sleeping_lock in rejected include/linux/sched.h. Restore
# upstream field under CONFIG_PREEMPT_RT_FULL, initialize it in sched_fork;
# preserve vendor cpus_allowed masks and keep runtime unverified.
python3 tools/exp76-rt-stage40-sleeping-lock.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage40" \
    --mode apply | tee "$REPORT/stage40-sleeping-lock.log"
test -f "$REPORT/stage40/stage40-status.json"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 64
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_STAGE40=RT_TASK_SLEEPING_LOCK_REJECT_PORTED; FULL_RT_RUNTIME_VERIFIED=false; FLASH_READY=false' | tee "$REPORT/stage40-gate.txt"


# Stage41: the full rejected RT migration lifecycle is ported with a
# saved E404 cpus_allowed mask, runqueue pin counter and the original
# asynchronous CPU stopper/hotplug path. Rejects remain 64 NONFLASH.
# Never equate object compilation to verified migration or hotplug runtime.
python3 tools/exp76-rt-stage41-migration-lifecycle.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage41" \
    --mode apply | tee "$REPORT/stage41-migration-lifecycle.log"
test -f "$REPORT/stage41/stage41-status.json"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 64
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_STAGE41=RT_MIGRATION_E404_PORT_APPLIED; MIGRATION_RUNTIME_VERIFIED=false; KERNEL_BUILT=false; FLASH_READY=false' | tee "$REPORT/stage41-gate.txt"


# Stage42: complete RT hotplug handshake that Stage41 upstream migrate_enable
# expects: takedown_cpu_task task pointer, sleep/retry pin-drain and guarded
# arm64 TLB migration hook; no stubbed hotplug worker or artificial TLB function.
python3 tools/exp76-rt-stage42-hotplug-tlb.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage42" \
    --mode apply | tee "$REPORT/stage42-hotplug-tlb.log"
test -f "$REPORT/stage42/stage42-status.json"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 64
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_STAGE42=HOTPLUG_PIN_DRAIN_TLB_ARCH_GUARD; HOTPLUG_RUNTIME_VERIFIED=false; FLASH_READY=false' | tee "$REPORT/stage42-gate.txt"


# Stage47: port bounded RCU #endif hunks and one raw worker sleeping lock.
# Read all 3 pinned .rej files and validate preprocessor balance BEFORE
# writing any overlay files; never convert the other workqueue spinlocks.
python3 tools/exp76-rt-stage47-rcu-workqueue.py \
    --tree "$ROOT/exp76-trial-overlay" \
    --report "$REPORT/stage47" \
    --mode apply | tee "$REPORT/stage47-rcu-workqueue.log"
test -f "$REPORT/stage47/stage47-status.json"
test "$(find "$ROOT/exp76-trial-overlay" -name '*.rej' -type f | wc -l)" -eq 64
git -C "$ROOT/exp76-trial-overlay" diff --check
echo 'EXP76_STAGE47=RCU_PREPROCESSOR_AND_WORKER_RAW_LOCK_PORTED; RUNTIME_VERIFIED=false; KERNEL_BUILT=false; FLASH_READY=false' | tee "$REPORT/stage47-gate.txt"


# Export ALL partial source changes (including new RT files), excluding
# reject/scratch evidence. Verify that it reapplies to clean pinned E404.
# This remains an incomplete NONFLASH patch while 64 files are rejected.
python3 tools/exp76-export-partial-source.py \
    --trial "$ROOT/exp76-trial-overlay" \
    --clean-base "$ROOT/exp76-e404" \
    --report "$REPORT/partial-source" | tee "$REPORT/partial-source-export.log"
test -s "$REPORT/partial-source/EXP76-RT-PARTIAL-SOURCE-NONFLASH.patch"
test -s "$REPORT/partial-source/PARTIAL_SOURCE_MANIFEST.json"
echo 'EXP76_PARTIAL_SOURCE=REAPPLY_CHECKED; RT_NOT_BUILT=true; FLASH_READY=false' | tee "$REPORT/partial-source-gate.txt"












{
    echo "EXP76_RT_STAGE=AUDIT_ONLY"
    echo "RT_SOURCE=4.19.325-rt140"
    echo "E404_SOURCE_COMMIT=$BASE"
    echo "EXACT_VERSION_MATCH=false"
    for variant in e404 overlay; do
        echo "$variant.apply_check=$(cat "$REPORT/$variant/apply-check-status.txt")"
        echo "$variant.reject_count=$(cat "$REPORT/$variant/rejected-count.txt")"
    done
    echo "EXP75_INLINE_OVERLAYS_REPRODUCED=false"
    echo "EXP76_UNAME_SOURCE_FIX=APPLIED_IN_AUDIT_TREE_ONLY"
    echo "CONFIG_PREEMPT_RT_FULL_ENABLED=false"
    echo "KERNEL_BUILT=false"
    echo "DEVICE_TESTED=false"
    echo "FLASH_READY=false"
} | tee "$REPORT/summary.txt"

cat > "$REPORT/limitations.txt" <<'EOF'
Patch application audit only: official RT patch targets 4.19.325-rt140, not E404 4.19.404R.
The overlay reconstruction includes EXP01 scheduler, EXP24 Ethernet, EXP25A touch,
and EXP76 user-UID uname source fix,
but not EXP75 inline CI source shims, KernelSU submodule, or EXP75 generated .config.
No claim of complete PREEMPT_RT integration, semantic correctness, compilation,
image bootability, or safe permanent installation. FLASH_READY=false.
EOF
