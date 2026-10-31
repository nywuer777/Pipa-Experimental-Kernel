#!/usr/bin/env bash
set -Eeuo pipefail
export GIT_TERMINAL_PROMPT=0
REPORT="${REPORT:-$PWD/rt-report-v2}"
PATCH="${PATCH:-$PWD/rt.patch}"
mkdir -p "$REPORT"
BASE=fed88a6024cd4d46c52eda607a95d97d7371ba81
git clone https://github.com/kvsnr113/xiaomi_sm8250_kernel_e404.git kernel
git -C kernel fetch --unshallow origin 2>"$REPORT/unshallow.log" || {
  if git -C kernel rev-parse --is-shallow-repository | grep -qx false; then echo 'Already full clone' >> "$REPORT/unshallow.log"; else exit 1; fi
}
test "$(git -C kernel rev-parse --is-shallow-repository)" = false
git -C kernel checkout --detach "$BASE"
test "$(git -C kernel rev-parse HEAD)" = "$BASE"
git -C kernel rev-parse HEAD > "$REPORT/e404-commit.txt"
git -C kernel rev-parse --is-shallow-repository > "$REPORT/shallow.txt"
# Build EXP25A source in a separate full-history clone, matching its official workflow.
git clone --shared kernel exp25a
git -C exp25a checkout --detach "$BASE"
echo 'Reconstructing EXP01, EXP24 and EXP25A from repository tooling' > "$REPORT/reconstruction.log"
echo '548ebb47ad0febe3c4541b9e93f2233bb9188c78d8f9ec298dd397a11216b852  PipaExperimental-EXP01-source.zip' | sha256sum -c - >> "$REPORT/reconstruction.log"
mkdir -p exp01-src
unzip -q PipaExperimental-EXP01-source.zip -d exp01-src
cp patches/0001-pipa-exp01-schedutil-rate-limit.patch exp01-src/0001-pipa-exp01-schedutil-rate-limit.patch
# Reproduce the pinned EXP01 changes without letting prepare-build replace the full-history checkout.
python3 exp01-src/validate.py >> "$REPORT/reconstruction.log" 2>&1
git -C exp25a apply --check "$PWD/exp01-src/0001-pipa-exp01-schedutil-rate-limit.patch"
git -C exp25a apply "$PWD/exp01-src/0001-pipa-exp01-schedutil-rate-limit.patch"
python3 tools/exp24-apply-ethernet.py --source configs/ethernet.config --kernel "$PWD/exp25a" --out "$PWD/exp25a-out" --mode apply >> "$REPORT/reconstruction.log" 2>&1
python3 tools/exp25-apply-touch.py --kernel "$PWD/exp25a" --mode apply >> "$REPORT/reconstruction.log" 2>&1
git -C exp25a diff --check
git -C exp25a diff --binary > "$REPORT/exp25a-overlay.diff"
sha256sum "$REPORT/exp25a-overlay.diff" > "$REPORT/exp25a-overlay.sha256"
# Do not assert source equivalence to final EXP25A until config and KernelSU are checked.
git -C exp25a status --short > "$REPORT/exp25a-status.txt"
for variant in e404 exp25a; do
  source_dir=kernel
  [[ "$variant" == exp25a ]] && source_dir=exp25a
  mkdir -p "$REPORT/$variant"
  # A pristine detached full-history clone for each independent attempt.
  git clone --shared "$source_dir" "audit-$variant-threeway"
  git clone --shared "$source_dir" "audit-$variant-reject"
  if [[ "$variant" == exp25a ]]; then
    git -C "audit-$variant-threeway" apply "$REPORT/exp25a-overlay.diff"
    git -C "audit-$variant-reject" apply "$REPORT/exp25a-overlay.diff"
  fi
  (cd "audit-$variant-threeway" && git apply --3way --check "$PATCH") > "$REPORT/$variant/threeway.log" 2>&1 && echo PASS > "$REPORT/$variant/threeway-status.txt" || echo FAIL > "$REPORT/$variant/threeway-status.txt"
  (cd "audit-$variant-reject" && git apply --reject "$PATCH") > "$REPORT/$variant/reject.log" 2>&1 && echo PASS > "$REPORT/$variant/reject-status.txt" || echo FAIL > "$REPORT/$variant/reject-status.txt"
  find "audit-$variant-reject" -type f -name '*.rej' -print | sed "s@^audit-$variant-reject/@@;s@\.rej$@@" | sort > "$REPORT/$variant/rejected-files.txt"
  grep -Ei 'missing blob|repository lacks|does not exist in index|cannot fall back to three-way' "$REPORT/$variant/threeway.log" > "$REPORT/$variant/missing-blobs.txt" || true
  python3 - "$REPORT/$variant" <<'PY'
import pathlib,sys,csv
d=pathlib.Path(sys.argv[1]);p=d.joinpath('rejected-files.txt').read_text().splitlines()
def subsystem(x):
 for prefix,name in [('kernel/sched/','sched'),('kernel/locking/','locking'),('kernel/irq/','irq'),('kernel/rcu/','rcu'),('drivers/','drivers'),('mm/','mm'),('arch/arm64/','arm64')]:
  if x.startswith(prefix):return name
 return 'other'
with (d/'rejections.csv').open('w') as f:
 w=csv.writer(f);w.writerow(['file','subsystem','origin','semantic_status']);w.writerows((x,subsystem(x),'UNVERIFIED','REVIEW_REQUIRED') for x in p)
(d/'rejected-count.txt').write_text(str(len(p))+'\n')
PY
done
cat > "$REPORT/limitations.txt" <<'EOF'
This audit performs full-history 3-way and reject checks on E404 and reconstructed EXP25A overlays.
Clean application is NOT proof of RT semantic correctness. Manual review of sched, locking, irq, rcu, Qualcomm and driver paths is mandatory.
EXP25A reconstruction source changes are applied, but final compiled .config, KernelSU submodule and build equivalence have NOT been verified.
Do not integrate, flash, or mark RT ready. FLASH_READY=false.
EOF
