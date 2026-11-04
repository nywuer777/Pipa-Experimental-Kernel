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
preemptible() is true and IRQs are enabled while spin_lock() is held;
msleep(40) elapsed >= 30ms; dmesg is readable; a PASS marker is present
without BUG/WARNING/atomic-scheduling diagnostics after BEGIN.

The module refuses to sleep under spin_lock on non-RT kernels. This proves
schedulability under spinlock_t only: not rt_mutex internals, priority
inheritance, RCU semantics, Android boot, or readiness to flash.

Not executed: vendor baseline has MODULES=n and no QEMU build or guest
exists in the local environment. FLASH_READY=false.
