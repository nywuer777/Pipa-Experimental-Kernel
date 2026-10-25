# EXP29.9 — SPARSE dispatch bug fixed (diagnostic correction)

## Hardware evidence EXP29.8, Xiaomi Pad 6 Adreno 650

The user's real screenshots show the following for synthetic RGBA8 two-pixel translation:

| GPU metric | PARALLEL 640x360 | SPARSE 640x360 | PARALLEL 1280x720 | SPARSE 1280x720 |
|---|---:|---:|---:|---:|
| Motion mean (ms) | 2.895332 | 0.058978 | 7.514180 | 0.095827 |
| Warp mean (ms) | 1.885312 | 1.867578 | 4.890371 | 7.535104 |
| Total mean (ms) | 4.780644 | 1.926556 | 12.404550 | 7.630931 |
| Total p95 (ms) | 4.815417 | 1.936458 | 18.914947 | 7.673802 |
| Image MAE vs ideal | 0.00 | **20.79** | 0.00 | **20.70** |
| Naive blend MAE | 20.98 | 20.98 | 20.96 | 20.96 |

**The EXP29.8 SPARSE 'speedup' is invalid.** The observed MAE shows that most interpolation failed. Do not use these figures to claim performance superiority or 60/120/144 FPS.

## Root cause

The SPARSE shader uses `gl_WorkGroupID.xy` to address each **16x16 image tile**. It requires **one 8x8-thread workgroup per tile**, exactly as the PARALLEL shader does.

The JNI originally set the per-tile flag using only:

```cpp
const uint32_t flags = motionVariant == 2 ?
    PIPA_FRAMEGEN_VK_MOTION_GROUP_PER_TILE : 0u;
```

However the Java UI selects **motionVariant=3 for SPARSE**. Variant 3 therefore entered the legacy dispatch formula `ceil(tilesX/8) x ceil(tilesY/8)` intended for shaders with `gl_GlobalInvocationID.xy`, whereas the shader expected `tilesX x tilesY` workgroups.

This dispatched workgroups for only **about 1/64 of the required tiles** at the tested resolutions. Many regions of the motion image were not initialized, leading to invalid flow inputs and failed interpolation. The too-small Motion time is attributable to insufficient dispatch coverage, not a legitimate shader improvement.

The corrected condition is:

```cpp
const uint32_t flags = (motionVariant == 2 || motionVariant == 3) ?
    PIPA_FRAMEGEN_VK_MOTION_GROUP_PER_TILE : 0u;
```

A dedicated regression test `tests/test_motion_dispatch_regression.py` guards this flag->shader mismatch, checks actual group count formulas for 256x128, 640x360, 1280x720 and 1920x1080, and independently tests synthetic two-pixel motion detection in a CPU reference. This test is a **static/source and CPU oracle**, not a GPU runtime assertion.

## New APP EXP29.9

- VersionCode 299 and versionName 29.9-lab.
- Keeps the original LEGACY, FAST, PARALLEL and SPARSE shader code for a direct A/B after the dispatch fix.
- Highlights `QUALIDADE FALHOU` in the test report if image synthetic MAE is above 1.0 channel level, or `QUALIDADE OK` otherwise; compiled/tested output correctness remains subject to an on-device run.
- Buttons for SPARSE 640x360 and SPARSE 1280x720 labelled `SPARSE FIX`.
- GitHub workflow `.github/workflows/exp29.9-motion-fix-apk.yml` compiles GLSL -> SPIR-V, validates SPIR-V, runs source/CPU contracts, builds Android NDK ARM64 library and APK, and verifies debug signing.
- `FLASH_READY=false`; no driver, SurfaceFlinger, Turnip, KGSL or EXP27 kernel changes.

## Device validation gate

1. Install the **CI successful** EXP29.9 APK.
2. Run PARALLEL 640x360, then SPARSE FIX 640x360; compare MAE, Motion, Warp, Total p95.
3. Repeat at 1280x720; reverse test order if possible.
4. Require **MAE approximately 0** for the known synthetic translation and valid shader times, and compare p95 rather than extrapolating a single sample. If MAE is still close to naive blending, do not promote SPARSE; collect output and logs for deeper motion image readback.
5. Full real-game Frame Generation remains unproven until a controlled Vulkan swapchain presenting interpolated frames is implemented and physical FPS/latency measured.

**No guarantee that SPARSE will still be faster after the dispatch is corrected.**
