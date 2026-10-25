# EXP29.7 — Cooperative Vulkan motion estimation

Device baseline, **observed on Xiaomi Pad 6 / Adreno 650** with EXP29.6 FAST at **640×360** (1 warmup, 8 GPU timestamp samples):

| Metric | Observed |
| --- | ---: |
| Motion GPU mean / p95 | 4.732077 / 5.375625 ms |
| Warp + barrier GPU mean / p95 | 1.882637 / 1.888021 ms |
| Total GPU mean / p50 / p95 | 6.614713 / 7.014687 / 7.261823 ms |
| CPU queue submit + fence | 60.795833 ms for 9 passes |
| End-to-end JNI/Vulkan call | 144.13 ms |
| Synthetic midpoint MAE / blend MAE | 0.00 / 20.98 |

These numbers are a single real device session, not proof of steady-state performance. The 144 Hz refresh period is approximately 6.944 ms; EXP29.6 GPU p95 was above that *before* rendering or presentation overhead.

## Changes in EXP29.7

- New `pipa_motion_parallel.comp` shader. **One 8×8 workgroup (64 invocations) processes one 16×16 motion tile**. All lanes cooperatively cache the previous image's 2-pixel-stride tile samples in shared workgroup memory; candidate SAD searches run concurrently across lanes, followed by a barrier, deterministic coarse winner selection and 3×3 refinement. Same output motion field format `RGBA16F` and push-constant ABI as EXP29.6. No change to interpolation shader.
- `pipa_framegen_vk_create_ex(..., flags, ...)` supports `PIPA_FRAMEGEN_VK_MOTION_GROUP_PER_TILE`, switching the motion dispatch from one invocation per tile (old pipeline: 8×8 tiles per workgroup) to one workgroup per tile (parallel shader). Existing `pipa_framegen_vk_create` and `pipa_framegen_vk_record` remain available for old users.
- LAB UI adds PARALLEL 256×128 (32 samples) and PARALLEL 640×360 (8 samples) next to LEGACY and FAST. Mode is selected together with its shader SPIR-V asset; tests use identical synthetic displacement and output quality scoring.
- VersionCode 297; independent build workflow: `.github/workflows/exp29.7-parallel-motion-apk.yml` compiles and validates SPIR-V, checks source contracts, builds native ARM64 APK and verifies its signature.

## Run A/B test

1. Install the APK from a successful EXP29.7 workflow run. Because per-run debug signing keys may differ, you might need to uninstall only the previous `dev.pipa.framegen.lab` package. It contains no persistent user data.
2. On the same tablet/thermal state, run **FAST 256×128**, **PARALLEL 256×128**; then **FAST 640×360**, **PARALLEL 640×360**. Repeat and reverse order. Capture Motion/Warp/Total GPU avg and p95 and synthetic image MAE.
3. FAST is the EXP29.6 serial-per-tile control. PARALLEL is the new shader; **speedup is not claimed until on-device measurement proves it**. Reject optimization if image MAE regresses, flickering occurs or p95 deteriorates.

## Boundaries

These are offscreen Vulkan Compute microbenchmarks. The app does not supply input latency, a game render loop, synthetic game frame presents, swapchain frame generation or physical-display FPS measurements. No Turnip, system compositor, kernel, root or KGSL changes. `FLASH_READY=false`.

The candidate-per-thread design is a hypothesis for improving GPU occupancy. Some Adreno drivers may suffer from workgroup memory/barrier or wave occupancy overhead. Measure before continuing to 720p. Resolve oclusions/UI and late-latching separately in a developer-owned Vulkan renderer.
