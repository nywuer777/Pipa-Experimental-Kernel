#!/usr/bin/env bash
# Bash / GitHub Actions Ubuntu 24.04 / pinned AOSP Clang 21 / EXP76 arm64 object-only diagnostic
set -Eeuo pipefail
export GIT_TERMINAL_PROMPT=0
ROOT="$(git rev-parse --show-toplevel)"
K="$ROOT/exp76-trial-overlay"
OUT="$ROOT/exp76-stage18-out"
REPORT="$ROOT/exp76-stage18-report"
CLANG="$ROOT/android-clang-prebuilt/clang-r563880c/bin"
mkdir -p "$REPORT" "$OUT"
test -d "$K/.git"
test -f "$K/kernel/sched/cpupri.c.rej"
test -f "$ROOT/exp76-rt-report/stage19/stage19-status.json"
test -f "$ROOT/exp76-rt-report/stage20/stage20-status.json"
test -f "$ROOT/exp76-rt-report/stage21/stage21-status.json"
test -f "$ROOT/exp76-rt-report/stage26/stage26-status.json"
test -f "$ROOT/exp76-rt-report/stage27/stage27-status.json"
test -f "$ROOT/exp76-rt-report/stage28/stage28-status.json"
test -f "$ROOT/exp76-rt-report/stage29/stage29-status.json"
test -f "$ROOT/exp76-rt-report/stage31/stage31-status.json"
test -f "$ROOT/exp76-rt-report/stage34/stage34-status.json"
test -f "$ROOT/exp76-rt-report/stage35/stage35-status.json"
test -f "$ROOT/exp76-rt-report/stage36/stage36-status.json"
test -f "$ROOT/exp76-rt-report/stage38/stage38-status.json"
test -f "$ROOT/exp76-rt-report/stage40/stage40-status.json"
test -x "$CLANG/clang"
test -x "$CLANG/ld.lld"

export PATH="$CLANG:$PATH"
export ARCH=arm64
export CROSS_COMPILE=aarch64-linux-gnu-
export CLANG_TRIPLE=aarch64-linux-gnu-
export CC=clang
export LD=ld.lld
export HOSTCC=gcc
export LLVM_IAS=1
clang --version > "$REPORT/clang-version.txt"
grep -F 'clang version 21.0.0' "$REPORT/clang-version.txt"
grep -F 'Android (14054515,' "$REPORT/clang-version.txt"
"$CLANG/ld.lld" --version > "$REPORT/lld-version.txt"

cat > "$REPORT/limitations.txt" <<'EOF'
Clang21 ARM64 OBJECT DIAGNOSTIC ONLY. RT patch targets 4.19.325-rt140,
not E404 4.19.404R. Trial tree excludes some EXP75 inline shims,
final EXP75 config and exact KernelSU integration.
No Image, boot.img, vmlinux or flash candidate is built.
EOF

set +e
git -C "$K" submodule update --init --depth 1 KernelSU > "$REPORT/kernelsu-submodule.log" 2>&1
SUBMODULE_RC=$?
set -e
printf '%s\n' "$SUBMODULE_RC" > "$REPORT/kernelsu-submodule-rc.txt"

set +e
make -C "$K" O="$OUT" ARCH=arm64 CC=clang LD=ld.lld HOSTCC=gcc \
  CROSS_COMPILE=aarch64-linux-gnu- CLANG_TRIPLE=aarch64-linux-gnu- \
  vendor/pipa_defconfig > "$REPORT/defconfig.log" 2>&1
CONFIG_RC=$?
set -e
printf '%s\n' "$CONFIG_RC" > "$REPORT/defconfig-rc.txt"
if [ "$CONFIG_RC" -ne 0 ] || [ ! -s "$OUT/.config" ]; then
  echo 'EXP76_STAGE18=CONFIG_GENERATION_FAILED; BUILD_VALID=false; FLASH_READY=false' \
    | tee "$REPORT/status.txt"
  exit 0
fi

"$K/scripts/config" --file "$OUT/.config" \
  --disable LTO_CLANG --disable LTO_CLANG_THIN --disable LTO_CLANG_FULL \
  --enable LTO_NONE --disable PREEMPT --enable PREEMPT_RT_FULL
set +e
make -C "$K" O="$OUT" ARCH=arm64 CC=clang LD=ld.lld HOSTCC=gcc \
  CROSS_COMPILE=aarch64-linux-gnu- CLANG_TRIPLE=aarch64-linux-gnu- \
  olddefconfig > "$REPORT/olddefconfig.log" 2>&1
OLD_RC=$?
set -e
printf '%s\n' "$OLD_RC" > "$REPORT/olddefconfig-rc.txt"
if [ "$OLD_RC" -ne 0 ] || ! grep -qx 'CONFIG_PREEMPT_RT_FULL=y' "$OUT/.config"; then
  grep -E '^((# )?CONFIG_PREEMPT|CONFIG_HAVE_PREEMPT_LAZY)' "$OUT/.config" \
    > "$REPORT/preempt-config.txt" || true
  echo 'EXP76_STAGE18=RT_CONFIG_NOT_ESTABLISHED; BUILD_VALID=false; FLASH_READY=false' \
    | tee "$REPORT/status.txt"
  exit 0
fi
grep -E '^((# )?CONFIG_PREEMPT|CONFIG_HAVE_PREEMPT_LAZY)' "$OUT/.config" \
  > "$REPORT/preempt-config.txt" || true

# Stage22: make prepare is the real common prerequisite, including arm64
# asm-offsets.s. Capture its first fatal errors once, without building Image.
set +e
timeout 210s make -C "$K" O="$OUT" ARCH=arm64 CC=clang LD=ld.lld \
  HOSTCC=gcc CROSS_COMPILE=aarch64-linux-gnu- CLANG_TRIPLE=aarch64-linux-gnu- \
  -j2 prepare > "$REPORT/prepare.log" 2>&1
PREPARE_MAKE_RC=$?
set -e
python3 tools/exp76-stage23-prepare-gate.py \
  --output "$OUT" \
  --log "$REPORT/prepare.log" \
  --report "$REPORT" \
  --make-rc "$PREPARE_MAKE_RC"
PREPARE_RC="$(cat "$REPORT/prepare.rc")"
if [ "$PREPARE_RC" -eq 0 ]; then
  echo 'EXP76_STAGE22_PREPARE=PASS; OBJECT_COMPILE=ATTEMPTED' | tee "$REPORT/prepare-status.txt"
  for obj in kernel/sched/cpupri.o kernel/sched/core.o kernel/fork.o; do
    name="$(printf '%s' "$obj" | tr '/' '_')"
    set +e
    timeout 210s make -C "$K" O="$OUT" ARCH=arm64 CC=clang LD=ld.lld \
      HOSTCC=gcc CROSS_COMPILE=aarch64-linux-gnu- CLANG_TRIPLE=aarch64-linux-gnu- \
      -j2 "$obj" > "$REPORT/$name.log" 2>&1
    rc=$?
    set -e
    printf '%s\n' "$rc" > "$REPORT/$name.rc"
    grep -m 30 -E 'fatal error:|error:|undefined reference|No rule to make target|Error [0-9]+|warning:' \
      "$REPORT/$name.log" > "$REPORT/$name.errors.txt" || true
  done
else
  echo 'EXP76_STAGE22_PREPARE=FAILED; OBJECT_COMPILE=SKIPPED' | tee "$REPORT/prepare-status.txt"
  for obj in kernel/sched/cpupri.o kernel/sched/core.o kernel/fork.o; do
    name="$(printf '%s' "$obj" | tr '/' '_')"
    printf '%s\n' 'BLOCKED_BY_PREPARE' > "$REPORT/$name.skipped"
    : > "$REPORT/$name.log"
    : > "$REPORT/$name.errors.txt"
  done
fi
# Object-only: no Image, vmlinux, boot.img or partition writes.
test ! -e "$OUT/arch/arm64/boot/Image"
test ! -e "$OUT/arch/arm64/boot/Image.gz"
test ! -e "$OUT/boot.img"
test ! -e "$OUT/vmlinux"

python3 - "$REPORT" <<'PY'
# Python 3 / CI diagnostic / emit object build evidence without claiming a kernel
import json
import pathlib
import sys
report = pathlib.Path(sys.argv[1])
targets = {}
prepare_rc = int((report / "prepare.rc").read_text().strip())
prepare_errors = (report / "prepare.errors.txt").read_text().splitlines()
for obj in ("kernel_sched_cpupri.o", "kernel_sched_core.o", "kernel_fork.o"):
    skipped = report / (obj + ".skipped")
    attempted = not skipped.exists()
    rc = int((report / (obj + ".rc")).read_text().strip()) if attempted else None
    errors = (report / (obj + ".errors.txt")).read_text().splitlines()
    targets[obj] = {
        "attempted": attempted,
        "exit_code": rc,
        "compiled": attempted and rc == 0,
        "skip_reason": skipped.read_text().strip() if skipped.exists() else None,
        "errors_excerpt": errors[:20],
    }
summary = {
    "stage": "EXP76_STAGE22_CLANG21_PREPARE_AND_OBJECT_DIAGNOSTIC",
    "compiler": "AOSP Clang 21.0.0 build 14054515",
    "config_preempt_rt_full": True,
    "preparation": {
        "target": "prepare",
        "exit_code": prepare_rc,
        "completed": prepare_rc == 0,
        "errors_excerpt": prepare_errors[:30],
    },
    "targets": targets,
    "all_target_objects_compiled": all(x["compiled"] for x in targets.values()),
    "kernel_built": False,
    "flash_ready": False,
}
(report / "OBJECT_DIAGNOSTIC.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
PY
if [ "$PREPARE_RC" -eq 0 ]; then
  echo 'EXP76_STAGE22=PREPARE_PASS_OBJECT_DIAGNOSTIC_CAPTURED; KERNEL_BUILT=false; FLASH_READY=false' \
    | tee "$REPORT/status.txt"
else
  echo 'EXP76_STAGE22=PREPARE_FAILED_OBJECTS_NOT_ATTEMPTED; KERNEL_BUILT=false; FLASH_READY=false' \
    | tee "$REPORT/status.txt"
fi
