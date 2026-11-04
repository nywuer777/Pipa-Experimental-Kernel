#!/usr/bin/env bash
# Bash / QEMU ARM64 guest with insmod and dmesg / assert RT sleeping-spinlock behavior / NO FLASH
set -Eeuo pipefail

KO="$1"
CONFIG="$2"
test -f "$KO" && test -f "$CONFIG"
command -v insmod >/dev/null
command -v rmmod >/dev/null
command -v dmesg >/dev/null

for flag in CONFIG_PREEMPT_RT_FULL=y CONFIG_MODULES=y CONFIG_MODULE_UNLOAD=y; do
  grep -qx "$flag" "$CONFIG" || { echo "BLOCKED_CONFIG: $flag missing" >&2; exit 2; }
done
if [ -d /sys/module/exp76_rt_spin_sleep ]; then
  echo 'BLOCKED_STATE: module already loaded' >&2
  exit 2
fi

tmp="$(mktemp -d)"
loaded=false
cleanup() {
  if [ "$loaded" = true ]; then rmmod exp76_rt_spin_sleep || true; fi
  rm -rf "$tmp"
}
trap cleanup EXIT

dmesg > "$tmp/before.log" || { echo 'BLOCKED_LOG: dmesg unreadable' >&2; exit 2; }
insmod "$KO"
loaded=true
dmesg > "$tmp/after.log" || { echo 'BLOCKED_LOG: dmesg unreadable' >&2; exit 2; }
for marker in 'EXP76_RT_SPIN_SLEEP BEGIN' 'EXP76_RT_SPIN_SLEEP PASS elapsed_us='; do
  before_count="$(grep -Fc "$marker" "$tmp/before.log" || true)"
  after_count="$(grep -Fc "$marker" "$tmp/after.log" || true)"
  if (( after_count <= before_count )); then
    echo "FAIL_STALE_MARKER: $marker" >&2
    exit 1
  fi
done
awk '/EXP76_RT_SPIN_SLEEP BEGIN/ { output=""; found=1 } found { output=output $0 "\n" } END { printf "%s", output }' \
  "$tmp/after.log" > "$tmp/test.log"

grep -q 'EXP76_RT_SPIN_SLEEP PASS elapsed_us=' "$tmp/test.log" || {
  cat "$tmp/test.log" >&2; echo 'FAIL: PASS marker missing' >&2; exit 1;
}
if grep -Ei 'BUG:|WARNING:|sleeping function called from invalid context|scheduling while atomic|FAIL_' "$tmp/test.log"; then
  echo 'FAIL: kernel diagnostic during spin-sleep test' >&2
  exit 1
fi
printf 'TEST_ID=EXP76_RT_SPIN_SLEEP_QEMU_V1\nCONFIG_SHA256='
sha256sum "$CONFIG" | cut -d ' ' -f1
printf 'GUEST_KERNEL=%s\n' "$(uname -r)"
cat "$tmp/test.log"
echo 'QEMU_RT_SPIN_SLEEP=PASS; FLASH_READY=false'
