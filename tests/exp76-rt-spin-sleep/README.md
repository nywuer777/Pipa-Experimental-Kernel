# EXP76 QEMU RT spinlock gate V3 (NOFLASH)

Scope: ARM64 E404-derived kernel with CONFIG_PREEMPT_RT_FULL=y and a
separate QEMU-only configuration. Never run the probe on the pipa/tablet.

## Input constraints

The pinned E404 vendor/pipa_defconfig has CONFIG_MODULES=n (line 726),
SERIAL_AMBA_PL011=n (line 2311), DEVTMPFS=n (line 1487) and
VIRTIO_MENU=n (line 4155). The QEMU config enables those guests-only
features; the effective PIPA RT build remains separate.

The checked-in rt-critical-configs.txt is the **exhaustive minimum**
set of RT-critical differences prohibited between generated configs.
check-config-diff.py reads that file (not an internal hardcoded list)
and produces QEMU_RT_PIPA_DIFF.json; any critical delta fails.

## QEMU orchestration

Reusable workflow: .github/workflows/exp76-rt-qemu-functional.yml.
Caller: .github/workflows/exp76-rt-provenance-network-probe.yml.

The workflow reconstructs the pinned E404+EXP76 RT source, applies
known source ports, generates three effective configs and attempts
three Image builds:
- PIPA_RT: effective vendor/pipa_defconfig with PREEMPT_RT_FULL=y
- QEMU_RT: derived effective PIPA_RT config plus guest drivers and modules
- QEMU_NONRT: same guest configuration with PREEMPT_RT_FULL=n

It compiles exp76_rt_spin_sleep.ko separately for QEMU_RT and QEMU_NONRT,
packs each and the matching effective .config in a minimal BusyBox
initramfs, and runs QEMU-system-aarch64 virt with a 60-second outer
timeout. This is a dedicated qualification job, not a flash artifact.

## Probe negative control

The C module has module_param_named(noop_mode,..., bool,0444). In
normal mode it uses the real spin_lock/spin_unlock. In noop mode both
are bypassed and an extra completion guarantees that T2 snapshots
T1_RELEASING=false before T1 is allowed to release; noop negative
must therefore fail with FAIL_SERIALIZATION_EARLY. The negative is
not accepted as success merely because 40 ms elapsed.

After successful insmod in normal mode, two kthreads establish
T1_HELD, T2_ATTEMPT and T1_RELEASED; T1 sleeps for 40 ms while
holding spinlock_t. T2's lock acquisition must observe release and
wait at least 30,000 microseconds. Both measurements are checked
in the module **and** in the serial log verifier.

Test identifier: EXP76_RT_SPIN_SLEEP_QEMU_V3.

## Gate invocation

Inside QEMU (BusyBox ash, running as root):

    /bin/sh /probe/gate.sh execute normal /probe/rt.ko /config/rt.config /tmp/normal
    /bin/sh /probe/gate.sh execute noop /probe/rt.ko /config/rt.config /tmp/noop
    /bin/sh /probe/gate.sh execute nonrt /probe/nonrt.ko /config/nonrt.config /tmp/nonrt

On Ubuntu/host (Bash; accepts serial log from a filename or stdin):

    bash tests/exp76-rt-spin-sleep/run-in-guest.sh verify normal RT.config console.log
    cat console.log | bash tests/exp76-rt-spin-sleep/run-in-guest.sh verify normal RT.config -

Exit codes: 0 = expected result PASS, 1 = failed assertion,
2 = BLOCKED_ENV (including unreadable or truncated dmesg),
3 = BLOCKED_CONFIG. noop success means **the expected injected
FAIL_SERIALIZATION was observed**, not that the noop spinlock worked.

## Evidence and remaining uncertainty

An actual QEMU PASS requires host and guest markers, guest dmesg,
two compiled raw Images with SHA256/config hash, the external .ko,
E404 base SHA, pinned Clang 21 SHA and QEMU_RT_PIPA_DIFF=PASS.

This probe demonstrates spinlock_t schedulability and serialized
acquisition under one controlled interleaving. It does NOT prove
the internal rt_mutex representation, priority inheritance, every
interleaving, RCU correctness or an Android device boot.

Source and workflow files committed != QEMU success. The CI
qualification run is the authority for real guest evidence.
RT_HANDOFF_READY=false, FLASH_READY=false.
