#!/usr/bin/env bash
set -Eeuo pipefail
DURATION="${DURATION:-30}"
[[ "$DURATION" =~ ^[0-9]+$ ]] && (( DURATION>=5 && DURATION<=120 )) || { echo 'DURATION must be 5..120'; exit 1; }
command -v adb >/dev/null || { echo 'Install Android Platform Tools (adb)'; exit 1; }
adb wait-for-device
OUT="pad6-baseline-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"
for spec in "interrupts|cat /proc/interrupts" "input-devices|cat /proc/bus/input/devices" "uname|uname -a" "threads|ps -A -T" "tracers|cat /sys/kernel/tracing/available_tracers"; do
  file="${spec%%|*}"; cmd="${spec#*|}"
  adb shell "$cmd" >"$OUT/$file.txt" 2>"$OUT/$file.err" || true
done
grep -Ei 'novatek|nt36532|nvt|touch|ts_' "$OUT/interrupts.txt" > "$OUT/irq-candidates.txt" || true
ROOT=''
if [[ "$(adb shell id -u 2>/dev/null | tr -d '\r')" == 0 ]]; then ROOT=direct
elif [[ "$(adb shell su -c 'id -u' 2>/dev/null | tr -d '\r')" == 0 ]]; then ROOT=su; fi
rootrun() { if [[ "$ROOT" == direct ]]; then adb shell "$1"; else adb shell su -c "$1"; fi; }
if [[ -n "$ROOT" ]] && rootrun 'command -v trace-cmd' >/dev/null 2>&1; then
  for tracer in irqsoff preemptoff; do
    echo "Capturing $tracer for $DURATION seconds; keep workload consistent."
    if rootrun "trace-cmd record -p $tracer -o /data/local/tmp/exp-$tracer.dat sleep $DURATION" >"$OUT/$tracer.log" 2>&1; then
      adb pull "/data/local/tmp/exp-$tracer.dat" "$OUT/$tracer.dat" >"$OUT/$tracer-pull.log" 2>&1 || true
      rootrun "trace-cmd report -i /data/local/tmp/exp-$tracer.dat" >"$OUT/$tracer-report.txt" 2>"$OUT/$tracer-report.err" || true
      rootrun "rm -f /data/local/tmp/exp-$tracer.dat" >/dev/null 2>&1 || true
    fi
  done
else echo 'Root or trace-cmd unavailable: only diagnostic information collected' > "$OUT/trace-status.txt"; fi
printf '%s\n' 'irqsoff/preemptoff are global windows, not input-thread p99.9. Need IRQ+input+sched correlation and controlled A/B.' > "$OUT/LIMITATIONS.txt"
tar -czf "$OUT.tar.gz" "$OUT"
echo "Send $OUT.tar.gz for analysis"
