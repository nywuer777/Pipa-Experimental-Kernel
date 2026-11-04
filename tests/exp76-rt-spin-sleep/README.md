# EXP76 QEMU RT spin-sleep probe (NOFLASH)

The pinned E404 arch/arm64/configs/vendor/pipa_defconfig has
# CONFIG_MODULES is not set (line 726), # CONFIG_SERIAL_AMBA_PL011 is not set
(line 2311), # CONFIG_DEVTMPFS is not set (line 1487), and
# CONFIG_VIRTIO_MENU is not set (line 4155). This is a QEMU-only probe,
not for the pipa. A guest-specific kernel config, Image, and initramfs
are prerequisites; enabling modules alone is insufficient for QEMU boot.

Prepare isolated QEMU config after defconfig:

    scripts/config --file "$OUT/.config" -e MODULES -e MODULE_UNLOAD -e PREEMPT_RT_FULL
    make O="$OUT" ARCH=arm64 CC=clang LD=ld.lld olddefconfig
    grep -E '^CONFIG_(MODULES|MODULE_UNLOAD|PREEMPT_RT_FULL)=' "$OUT/.config"

Build the module with pinned Clang 21 and matching prepared E404 tree:

    make -C "$KERNEL" O="$OUT" ARCH=arm64 CC=clang LD=ld.lld \
      CROSS_COMPILE=aarch64-linux-gnu- \
      M="$PWD/tests/exp76-rt-spin-sleep" modules

Copy the .ko and exact effective kernel .config into a disposable ARM64 QEMU
guest initramfs. As root inside the guest:

    ./run-in-guest.sh ./exp76_rt_spin_sleep.ko ./effective.config

PASS requires PREEMPT_RT_FULL=y, MODULES=y, MODULE_UNLOAD=y; insmod succeeds;
T1 holds spinlock_t and signals T1_HELD; T2 records its attempt timestamp
and signals T2_ATTEMPT; T1 sleeps 40ms under the lock before T1_RELEASED;
T2 must observe T1 release on acquiring the lock AND wait >= 30,000us.
T1 must be preemptible with IRQs enabled and sleep >= 30,000us.
The script requires fresh BEGIN, T1_HELD, T2_ATTEMPT, T1_RELEASED,
CONTENTION_PASS, and PASS markers, with readable dmesg and no BUG/WARNING.
Host-side QEMU must enforce a timeout around insmod, including deadlock cases.

The module refuses to run on non-RT kernels. Test_id:
EXP76_RT_SPIN_SLEEP_QEMU_V2. A passing run demonstrates schedulability
and measured serialization of spinlock_t for this test, not independent
proof of rt_mutex internals, priority inheritance, RCU, or all scheduling
interleavings. A no-op could theoretically appear to wait if T2 is
involuntarily descheduled for >=30ms; a kernel-trace/negative lock
injection test is still required before claiming exhaustive no-op immunity.

Not executed: vendor baseline has MODULES=n and no QEMU build or guest
exists in the local environment. FLASH_READY=false.
