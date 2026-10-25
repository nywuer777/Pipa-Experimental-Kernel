# EXP29.8 — Sparse cooperative motion benchmark

## Observed EXP29.7 device comparison (Xiaomi Pad 6, Adreno 650)

**640×360; GPU n=8; synthetic 2px horizontal translation; one run each.**

| Metric | FAST | PARALLEL |
| --- | ---: | ---: |
| Motion avg | 3.128997 ms | 2.907057 ms |
| Motion p95 | 3.144531 ms | 2.917760 ms |
| Warp+barrier avg | 1.851569 ms | 1.878268 ms |
| Total avg | 4.980566 ms | 4.785325 ms |
| Total p95 | 5.000260 ms | 4.806562 ms |
| MAE against ideal midpoint | 0.00 | 0.00 |

PARALLEL improves Motion by **7.09%**, total by **3.92%** and total p95 by **3.87%** in this single paired comparison. The measurements are **not** displayed FPS, and have small sample sizes; cross-run thermal and clock differences remain uncontrolled.

## Experimental modification

Preserve the workgroup-cooperative motion path (`pipa_motion_parallel.comp`, 2px sample spacing) as the control. New `pipa_motion_sparse.comp` keeps the same 64-invocation workgroup/candidate search, tile geometry and Vulkan pipeline contract but samples the previous/current image on a **4px grid** (16 samples per tile instead of 64). The aim is to reduce image-load bandwidth and ALU cost. It can miss fine image detail, occlusions and textured motion; **SPARSE must not automatically become the default**.

Motion variant 3 loads the SPARSE shader. The previous variants (LEGACY=0, FAST=1, PARALLEL=2) remain selectable. The JNI image-size limit increases from 1024×1024 to maximum 1920×1080, enabling 1280×720 offscreen benchmarking.

## New UI tests

- PARALLEL 640×360 / SPARSE 640×360: 1 warmup + 8 measured motion/warp GPU timestamp pairs.
- PARALLEL 1280×720 / SPARSE 1280×720: 1 warmup + 8 measured pairs.
- The existing FAST and LEGACY buttons remain unchanged.

For each test record GPU Motion/ Warp/ Total mean, p95, synthetic midpoint MAE, and CPU total wall. For valid quality, aim for MAE not worse than the corresponding PARALLEL reference. **A zero MAE for a single translated synthetic pattern does not validate real-game image quality.** Larger resolutions may expose severe nonlinear scaling, thermal throttling or driver limitations.

## On-device test order

1. Reproduce PARALLEL 640, then SPARSE 640; reverse order once to reduce thermal confounding.
2. Run PARALLEL 1280, then SPARSE 1280; reverse order once, after similar cooldown/temperature.
3. Prefer p95 and median over one mean. Reject SPARSE if motion/warp p95 regresses or error rises.
4. Device GPU timestamps include compute shader stages, not uploads or Android presentation. Remaining requirements: scenes with motion discontinuities and a native Vulkan swapchain to measure **actual** presented frames.

No Turnip/KGSL, vendor, SurfaceFlinger or kernel changes; the lab is a disposable application. `FLASH_READY=false`.
