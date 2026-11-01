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

    find "exp76-trial-$variant" -type f -name '*.rej' -print | sed "s@^exp76-trial-$variant/@@;s@\.rej$@@" | sort > "$REPORT/$variant/rejected-paths.txt"
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
    echo "CONFIG_PREEMPT_RT_FULL_ENABLED=false"
    echo "KERNEL_BUILT=false"
    echo "DEVICE_TESTED=false"
    echo "FLASH_READY=false"
} | tee "$REPORT/summary.txt"

cat > "$REPORT/limitations.txt" <<'EOF'
Patch application audit only: official RT patch targets 4.19.325-rt140, not E404 4.19.404R.
The overlay reconstruction includes EXP01 scheduler, EXP24 Ethernet, EXP25A touch,
but not EXP75 inline CI source shims, KernelSU submodule, or EXP75 generated .config.
No claim of complete PREEMPT_RT integration, semantic correctness, compilation,
image bootability, or safe permanent installation. FLASH_READY=false.
EOF
