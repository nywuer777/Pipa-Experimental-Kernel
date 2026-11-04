#!/bin/sh
# BusyBox ash / ARM64 QEMU guest and offline GH artifact verifier / EXP76 RT spinlock V3 / NO FLASH
set -euo pipefail

usage() {
    echo "usage: $0 execute MODE MODULE.ko CONFIG OUTDIR" >&2
    echo "   or: $0 verify MODE CONFIG LOGFILE|-" >&2
    exit 2
}
blocked_env() { echo "BLOCKED_ENV: $*" >&2; exit 2; }
blocked_config() { echo "BLOCKED_CONFIG: $*" >&2; exit 3; }
fail() { echo "FAIL: $*" >&2; exit 1; }
count() { grep -Fc "$1" "$2" || :; }
exact() {
    n="$(count "$1" "$2")"
    [ "$n" -eq 1 ] || fail "marker [$1] count=$n expected=1"
}
config_gate() {
    cfg="$1"; mode="$2"
    [ -r "$cfg" ] || blocked_env "config unreadable: $cfg"
    grep -qx 'CONFIG_MODULES=y' "$cfg" || blocked_config "MODULES"
    grep -qx 'CONFIG_MODULE_UNLOAD=y' "$cfg" || blocked_config "MODULE_UNLOAD"
    if [ "$mode" = nonrt ]; then
        ! grep -qx 'CONFIG_PREEMPT_RT_FULL=y' "$cfg" ||
            blocked_config "nonRT has PREEMPT_RT_FULL=y"
    else
        grep -qx 'CONFIG_PREEMPT_RT_FULL=y' "$cfg" ||
            blocked_config "PREEMPT_RT_FULL is not y"
    fi
}
verify() {
    mode="$1"; cfg="$2"; source="$3"
    config_gate "$cfg" "$mode"
    temp="$(mktemp -d)" || blocked_env "mktemp"
    trap 'rm -rf "$temp"' EXIT
    if [ "$source" = "-" ]; then
        cat > "$temp/full" || blocked_env "stdin unreadable"
    else
        [ -r "$source" ] || blocked_env "artifact unreadable"
        cat "$source" > "$temp/full" || blocked_env "artifact read failed"
    fi
    tr -d '\r' < "$temp/full" > "$temp/clean" ||
        blocked_env "cannot normalize serial log"
    if grep -Fq 'EXP76_PROBE_BLOCKED_DMESG' "$temp/clean"; then
        blocked_env "guest dmesg unreadable"
    fi
    starts="$(count "EXP76_PROBE_LOG_BEGIN mode=$mode" "$temp/clean")"
    ends="$(count "EXP76_PROBE_LOG_END mode=$mode" "$temp/clean")"
    [ "$starts" -gt 0 ] && [ "$ends" -gt 0 ] ||
        blocked_env "truncated serial log: begin=$starts end=$ends"
    [ "$starts" -eq 1 ] && [ "$ends" -eq 1 ] ||
        fail "duplicate serial boundaries: begin=$starts end=$ends"
    awk -v begin="EXP76_PROBE_LOG_BEGIN mode=$mode" \
        -v end="EXP76_PROBE_LOG_END mode=$mode" \
        '$0==begin { on=1;next } $0==end { on=0;next } on {print}' \
        "$temp/clean" > "$temp/probe"
    exact 'EXP76_PROBE_INSMOD_RC=' "$temp/probe"
    rc="$(sed -n 's/^EXP76_PROBE_INSMOD_RC=//p' "$temp/probe")"
    case "$rc" in ''|*[!0-9]*) fail "invalid insmod rc";; esac
    [ "$rc" -le 255 ] || fail "insmod rc overflow"
    if grep -Ei 'BUG:|WARNING:|sleeping function called from invalid context|scheduling while atomic' "$temp/probe"; then
        fail "kernel diagnostic during probe"
    fi
    if [ "$mode" = nonrt ]; then
        [ "$rc" -ne 0 ] || fail "nonRT module unexpectedly loaded"
        exact 'EXP76_RT_SPIN_SLEEP BLOCKED_CONFIG PREEMPT_RT_FULL=n' "$temp/probe"
        exact 'EXP76_RT_SPIN_SLEEP END status=BLOCKED_CONFIG' "$temp/probe"
        [ "$(count 'EXP76_RT_SPIN_SLEEP BEGIN' "$temp/probe")" -eq 0 ] ||
            fail "nonRT code reached runtime test"
        echo 'EXPECTED_BLOCKED_CONFIG=PASS test_id=EXP76_RT_SPIN_SLEEP_QEMU_V3'
        return
    fi
    exact "EXP76_RT_SPIN_SLEEP BEGIN test_id=EXP76_RT_SPIN_SLEEP_QEMU_V3 mode=$mode" "$temp/probe"
    exact 'EXP76_RT_SPIN_SLEEP T1_HELD' "$temp/probe"
    exact 'EXP76_RT_SPIN_SLEEP T2_ATTEMPT' "$temp/probe"
    exact 'EXP76_RT_SPIN_SLEEP T1_RELEASED' "$temp/probe"
    if [ "$mode" = normal ]; then
        [ "$rc" -eq 0 ] || fail "normal insmod returned $rc"
        exact 'EXP76_RT_SPIN_SLEEP CONTENTION_PASS wait_us=' "$temp/probe"
        exact 'EXP76_RT_SPIN_SLEEP PASS elapsed_us=' "$temp/probe"
        exact 'EXP76_RT_SPIN_SLEEP END status=PASS' "$temp/probe"
        [ "$(count 'EXP76_RT_SPIN_SLEEP FAIL_' "$temp/probe")" -eq 0 ] ||
            fail "normal has FAIL marker"
        grep -Eq 'EXP76_RT_SPIN_SLEEP CONTENTION_PASS wait_us=[0-9]+ release_seen=1' "$temp/probe" ||
            fail "malformed contention proof"
        echo 'QEMU_RT_SPINLOCK=PASS test_id=EXP76_RT_SPIN_SLEEP_QEMU_V3'
    else
        [ "$rc" -ne 0 ] || fail "noop negative unexpectedly loaded"
        n="$(grep -Ec 'EXP76_RT_SPIN_SLEEP FAIL_SERIALIZATION_(EARLY|SHORT)' "$temp/probe" || :)"
        [ "$n" -eq 1 ] || fail "noop serialization failures=$n expected=1"
        exact 'EXP76_RT_SPIN_SLEEP END status=FAIL' "$temp/probe"
        [ "$(count 'EXP76_RT_SPIN_SLEEP PASS elapsed_us=' "$temp/probe")" -eq 0 ] ||
            fail "noop printed PASS (false positive)"
        echo 'EXPECTED_FAIL_SERIALIZATION=PASS test_id=EXP76_RT_SPIN_SLEEP_QEMU_V3'
    fi
}
execute() {
    mode="$1"; ko="$2"; cfg="$3"; output="$4"
    config_gate "$cfg" "$mode"
    [ -r "$ko" ] || blocked_env "module unreadable: $ko"
    for exe in dmesg insmod rmmod timeout awk grep sed cat mktemp wc tail tr; do
        command -v "$exe" >/dev/null 2>&1 || blocked_env "missing $exe"
    done
    mkdir -p "$output" || blocked_env "cannot create output dir"
    dmesg > "$output/before" || blocked_env "dmesg before unreadable"
    noop=0
    [ "$mode" = noop ] && noop=1
    set +e
    timeout -k 3 15 insmod "$ko" "noop_mode=$noop"
    result=$?
    set -e
    [ "$result" -ne 124 ] && [ "$result" -ne 137 ] ||
        blocked_env "insmod timed out"
    dmesg > "$output/after" || blocked_env "dmesg after unreadable"
    old="$(wc -l < "$output/before")"
    new="$(wc -l < "$output/after")"
    [ "$new" -ge "$old" ] || blocked_env "kernel ring wrapped"
    added="$((new-old))"
    [ "$added" -gt 0 ] || blocked_env "no fresh dmesg"
    {
        echo "EXP76_PROBE_LOG_BEGIN mode=$mode"
        echo "EXP76_PROBE_INSMOD_RC=$result"
        tail -n "$added" "$output/after"
        echo "EXP76_PROBE_LOG_END mode=$mode"
    } > "$output/probe.log"
    cat "$output/probe.log"
    if [ "$result" -eq 0 ]; then
        rmmod exp76_rt_spin_sleep || blocked_env "rmmod"
    fi
    "$0" verify "$mode" "$cfg" "$output/probe.log"
}
[ "$#" -ge 1 ] || usage
action="$1"; shift
case "$action" in
    verify)
        [ "$#" -eq 3 ] || usage
        case "$1" in normal|noop|nonrt) ;; *) usage;; esac
        verify "$1" "$2" "$3" ;;
    execute)
        [ "$#" -eq 4 ] || usage
        case "$1" in normal|noop|nonrt) ;; *) usage;; esac
        execute "$1" "$2" "$3" "$4" ;;
    *) usage ;;
esac
