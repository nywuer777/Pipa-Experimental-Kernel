# EXP29.6 — Motion FAST and split GPU timing

**Confirmed baseline (EXP29.5 screenshot, Xiaomi Pad 6 / Adreno 650):** 256×128 RGBA8, 1 warmup + 32 measured compute pairs; GPU total mean 3.228105 ms, p50 2.115 ms, p95 4.778125 ms, MAE=0.00 against known midpoint (naive blend MAE=20.92), CPU submission + fence wall 110.636354 ms, whole JNI/Vulkan call 198.01 ms. This proves the compute pipeline works on the device for synthetic translation; it does not prove any additional displayed frames.

## EXP29.6 changes

1. Preserve the original exhaustive `pipa_motion.comp` shader as the reference.
2. Add `pipa_motion_fast.comp`: search candidates on a stride-2 coarse grid (radius <=4), then refine the best candidate in a bounded 3×3 neighborhood. Uses the same 16×16 tile output, RGBA16F motion image, storage binding contract and interpolation shader.
3. Add optional `pipa_framegen_vk_record_profiled` without breaking `pipa_framegen_vk_record`. T0 before motion dispatch, T1 after motion, T2 after interpolation. Phase intervals are **Motion** (T1-T0), **Warp+barrier** (T2-T1), **Total** (T2-T0). Timestamp support is detected; no substituted CPU clock values.
4. Benchmark choices:
   - 1 pass LEGACY 256×128 (functional check)
   - 1+32 passes LEGACY 256×128 (baseline comparison)
   - 1+32 passes FAST 256×128 (same image and resolution)
   - 1+8 passes FAST 640×360 (scaling probe)
5. Report each phase's mean, median and p95, plus a synthetic accuracy check versus a known ideal intermediate image. Shader/pipeline creation, Vulkan images, CPU/JNI transfers, and Android UI are outside GPU phase timings.
6. The pipeline remains **offscreen**. No game insertion, global FPS unlock, SurfaceFlinger interception, Turnip replacement, KGSL patch, kernel flash or persistent system modification.

## Comparison protocol

Run LEGACY 256, FAST 256, LEGACY 256, FAST 256 after the tablet has reached thermal equilibrium; record each set. Then run FAST 640. Repeat under comparable refresh mode and temperature, checking both **MAE** and **p95**; look for negative scaling in either shader. Avoid declaring FAST superior from a single cold sample.

**Interpretation limits:** stride-2 coarse search plus 3×3 refinement is a heuristic; ambiguous textures, occlusions, fast displacements and scene cuts can select a poorer vector than exhaustive search. Zero MAE for the known +2 pixel synthetic translation does not imply image quality in real games. At 144 Hz, a 6.944 ms present interval is shared with the entire game/rendering/compositor pipeline; a 4.78 ms isolated shader measurement at 256×128 is *not* sufficient to claim playable 144 FPS with generation.

## Build

GitHub Actions workflow `.github/workflows/exp29.6-motion-compare-apk.yml`: pins NDK r27c and Gradle, compiles every `shaders/*.comp` to Vulkan 1.1 SPIR-V with `glslangValidator` and `spirv-val`, runs ABI/source tests, signs and archives the debug APK and SHA-256 evidence.

APK package `dev.pipa.framegen.lab`, version 29.6 (296). If a previous debug signing key differs, uninstall only the previous lab package before installing. The application has no persistent user data.

**Release gates:** CI shader and Android ARM64 PASS -> install PASS -> correctness on Adreno 650 PASS -> timestamp measurements -> final recommendation about performance. Do not confuse these stages.

`FLASH_READY=false`. Existing kernel EXP27 unchanged.
