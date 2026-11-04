#!/bin/bash
# Bash / Ubuntu GitHub Actions / synthetic guest log-verifier regression V3 / NO FLASH
set -euo pipefail
GATE="tests/exp76-rt-spin-sleep/run-in-guest.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
printf 'CONFIG_MODULES=y\nCONFIG_MODULE_UNLOAD=y\nCONFIG_PREEMPT_RT_FULL=y\n' > "$tmp/rt.config"
printf 'CONFIG_MODULES=y\nCONFIG_MODULE_UNLOAD=y\n# CONFIG_PREEMPT_RT_FULL is not set\n' > "$tmp/nonrt.config"

cat > "$tmp/normal.log" <<'EOF'
EXP76_PROBE_LOG_BEGIN mode=normal
EXP76_PROBE_INSMOD_RC=0
[  12.000] EXP76_RT_SPIN_SLEEP BEGIN test_id=EXP76_RT_SPIN_SLEEP_QEMU_V3 mode=normal
[  12.001] EXP76_RT_SPIN_SLEEP T1_HELD
[  12.002] EXP76_RT_SPIN_SLEEP T2_ATTEMPT
[  12.043] EXP76_RT_SPIN_SLEEP T1_RELEASED
[  12.044] EXP76_RT_SPIN_SLEEP CONTENTION_PASS wait_us=42123 release_seen=1
[  12.045] EXP76_RT_SPIN_SLEEP PASS elapsed_us=40921 wait_us=42123 preemptible=1 irq_enabled=1
[  12.046] EXP76_RT_SPIN_SLEEP END status=PASS
EXP76_PROBE_LOG_END mode=normal
EOF
cat > "$tmp/noop.log" <<'EOF'
EXP76_PROBE_LOG_BEGIN mode=noop
EXP76_PROBE_INSMOD_RC=1
[  16.000] EXP76_RT_SPIN_SLEEP BEGIN test_id=EXP76_RT_SPIN_SLEEP_QEMU_V3 mode=noop
[  16.001] EXP76_RT_SPIN_SLEEP T1_HELD
[  16.002] EXP76_RT_SPIN_SLEEP T2_ATTEMPT
[  16.003] EXP76_RT_SPIN_SLEEP FAIL_SERIALIZATION_EARLY wait_us=5
[  16.044] EXP76_RT_SPIN_SLEEP T1_RELEASED
[  16.045] EXP76_RT_SPIN_SLEEP END status=FAIL
EXP76_PROBE_LOG_END mode=noop
EOF
cat > "$tmp/nonrt.log" <<'EOF'
EXP76_PROBE_LOG_BEGIN mode=nonrt
EXP76_PROBE_INSMOD_RC=1
[   9.123] EXP76_RT_SPIN_SLEEP BLOCKED_CONFIG PREEMPT_RT_FULL=n
[   9.124] EXP76_RT_SPIN_SLEEP END status=BLOCKED_CONFIG
EXP76_PROBE_LOG_END mode=nonrt
EOF

expect_rc() {
  local expected="$1"
  shift
  local rc=0
  "$@" > "$tmp/last.log" 2>&1 || rc="$?"
  if [[ "$rc" != "$expected" ]]; then
    printf 'FAIL_EXPECTED_RC expected=%s actual=%s command=%s\n' "$expected" "$rc" "$*" >&2
    cat "$tmp/last.log" >&2
    exit 1
  fi
}
expect_rc 0 bash "$GATE" verify normal "$tmp/rt.config" "$tmp/normal.log"
expect_rc 0 bash "$GATE" verify normal "$tmp/rt.config" - < "$tmp/normal.log"
expect_rc 0 bash "$GATE" verify noop "$tmp/rt.config" "$tmp/noop.log"
expect_rc 0 bash "$GATE" verify nonrt "$tmp/nonrt.config" "$tmp/nonrt.log"
sed '$d' "$tmp/normal.log" > "$tmp/truncated.log"
expect_rc 2 bash "$GATE" verify normal "$tmp/rt.config" "$tmp/truncated.log"
expect_rc 2 bash "$GATE" verify normal "$tmp/rt.config" "$tmp/missing.log"
cp "$tmp/normal.log" "$tmp/duplicate.log"
sed -i '/CONTENTion_unused/s/foo/bar/' "$tmp/duplicate.log"
sed -i '/END status=PASS/a [  12.047] EXP76_RT_SPIN_SLEEP END status=PASS' "$tmp/duplicate.log"
expect_rc 1 bash "$GATE" verify normal "$tmp/rt.config" "$tmp/duplicate.log"
sed '/T1_RELEASED/d' "$tmp/normal.log" > "$tmp/missing-marker.log"
expect_rc 1 bash "$GATE" verify normal "$tmp/rt.config" "$tmp/missing-marker.log"
sed '/T1_RELEASED/a [  12.042] WARNING: spinlock test warning' \
  "$tmp/normal.log" > "$tmp/warning.log"
expect_rc 1 bash "$GATE" verify normal "$tmp/rt.config" "$tmp/warning.log"
expect_rc 3 bash "$GATE" verify normal "$tmp/nonrt.config" "$tmp/normal.log"
echo 'EXP76_RT_SPIN_SLEEP_V3_LOG_VERIFIER=10_CASES_PASS; QEMU_RUNTIME_UNVERIFIED; NO_FLASH'
