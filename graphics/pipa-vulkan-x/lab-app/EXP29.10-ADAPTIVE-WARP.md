# EXP29.10 — Adaptive warp (SPARSE motion retained)

## Confirmed hardware baseline: EXP29.9 Xiaomi Pad 6 / Adreno 650

The user supplied four on-device benchmark screenshots on 25 Oct 2026. 1 warmup + 8 timed passes, Vulkan Compute offscreen.

| GPU metric | PARALLEL 640x360 | SPARSE FIX 640x360 | PARALLEL 1280x720 | SPARSE FIX 1280x720 |
|---|---:|---:|---:|---:|
| Motion avg ms | 2.905944 | 1.097780 | 7.352337 | 3.597897 |
| Motion p95 ms | 2.920000 | 1.111250 | 11.373541 | 4.272187 |
| Warp+barrier avg ms | 1.880391 | 1.863340 | 4.579381 | 6.047682 |
| Warp+barrier p95 ms | 1.900052 | 1.892552 | 7.539583 | 7.545833 |
| Total avg ms | 4.786335 | 2.961120 | 11.931718 | 9.645579 |
| Total p95 ms | 4.805156 | 3.003802 | 18.913125 | 11.810781 |
| Synthetic MAE | 0.00 | 0.00 | 0.00 | 0.00 |

The EXP29.9 corrected SPARSE workgroup dispatch works on the device for the known translation scenario. Relative GPU-total reduction: **38.1% at 640x360**, **19.2% at 720p**, measured in *one A/B run per profile*. p95 at 720p is still above 144 Hz full present interval (6.944 ms). GPU timestamp intervals do not include actual physical presentation, JNI allocation, uploads, readback or input latency.

## Adaptive warp experiment

Original `pipa_interpolate.comp` always loads 4 texels per input (8 total) and computes bilinear filtering, even if the subpixel coordinates are integer or lie on a pixel row/column.

`pipa_interpolate_adaptive.comp` checks subpixel fractions after clamping, then:
- both fractions zero: 1 imageLoad per input
- only one nonzero: 2 imageLoads per input
- both nonzero: preserve the original full 4-tap bilinear interpolation per input

All decisions are mathematically equivalent to the original bilinear interpolation for these coordinates; **this is a shader optimization hypothesis, not a hardware result**. Dynamic GPU branches can introduce overhead or reduce gains for divergent vectors. At `phase=0.5` with an integer (2,0) motion vector, both warped pixel positions are integer and require one read from each image.

All previous shader/ABI modes are preserved. Added two UI comparisons:
- SPARSE baseline 640x360 vs SPARSE+ADAPTIVE 640x360 (8 GPU timestamp samples after warmup)
- SPARSE baseline 1280x720 vs SPARSE+ADAPTIVE 1280x720 (8 samples after warmup)

No changes to motion estimator, shader descriptors, JNI parameter layout, Vulkan queue submission, or EXP27 kernel. The app uses the same `motionVariant=3` and loads the alternative interpolation SPIR-V asset for the new two benchmark buttons.

## Validation

CI `.github/workflows/exp29.10-adaptive-warp-apk.yml` compiles and validates every compute shader with `glslangValidator` and `spirv-val`, executes the previous regression contracts plus a new CPU equivalence oracle (`tests/test_adaptive_warp_equivalence.py`), builds signed-debug ARM64 APK and publishes its SHA256.

Hardware test: record GPU Motion/Warp/Total avg, p50 and p95, quality MAE and end-to-end timing with baseline and ADAPTIVE at **both** resolutions. Repeat in reversed order and stable thermal conditions. Do not promote the shader unless GPU Warp and total p95 improve with no MAE regression across synthetic and more complex scenes.

**Limits:** The synthetic 2px translation does not exercise occlusion, motion-vector failures, scene cuts, HUD, partial transparency or rapidly divergent flows. No swapchain presentation. No claims of 60->120 FPS or 144Hz compatibility without the native presenter and end-to-end latency test. `FLASH_READY=false`.
