# EXP76 local vmlinux link result (NONFLASH)

Date: 2026-11-03

## Result

A local ARM64 integration build linked `vmlinux` successfully with `CONFIG_PREEMPT_RT_FULL=y`.

- Source base: E404 commit `fed88a6024cd4d46c52eda607a95d97d7371ba81`.
- RT source: `4.19.325-rt140`; this is not an exact version match for E404 `4.19.404R`.
- Toolchain: Android Clang 21, r563880c, build 14054515; toolchain source commit `b54cd2c8e9e0bb057aef3804d42d39c5ac4674c7`.
- Link command:
  ```sh
  make -C exp76-trial-overlay \
    O="$PWD/exp76-stage18-out" ARCH=arm64 CC=clang LD=ld.lld HOSTCC=gcc \
    CROSS_COMPILE=aarch64-linux-gnu- CLANG_TRIPLE=aarch64-linux-gnu- \
    LLVM_IAS=1 -j8 vmlinux
  ```
- Exit code: `0`.
- Output: 36,725,664-byte AArch64 ELF; Build ID `4ff82e65982e83a5525c7cebad89840f07639267`.
- `System.map` was generated. No `Image` or `boot.img` was generated.

## Overlay status

The trial overlay includes local RT compatibility reconciliations for the phandle-cache free path, dynamically initialized spinlocks, radix-tree local locking, the gadget function's swait query, RT rwsem public entry points, and radix/IDR preload end functions. The exported partial source reapplication check passed; its SHA-256 is `6ab9278da4dd852c4ca4cf9e8b7b7b57f08936230447b2857fe49d505940061a`.

There are still 64 rejected RT patch files. The overlay changes and patch hash above are evidence from the local trial tree; this report commit does not add those source changes or make the build reproducible from the PR branch.

## Validation boundary

This is a successful link of the local trial configuration. Runtime behavior, device boot, latency, an `Image`/boot artifact, and flashing were not tested. `FLASH_READY=false`.
