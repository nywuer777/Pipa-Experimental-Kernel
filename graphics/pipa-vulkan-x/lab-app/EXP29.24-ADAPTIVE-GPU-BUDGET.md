# EXP29.24 — Adaptive GPU Budget Governor (experimental)

## Baseline on Xiaomi Pad 6, EXP29.23
WSI IDENTITY solved prior squash/stretching; 3D HOLD and 3D FG both 1440 accepted presents and zero CPU late periods. Adreno 650 at 144Hz, WSI_SYNC, radius3. FG: 720 original + 720 generated, 5.718579ms generated+blit mean, 6.050677ms p95, Motion 2.093047ms mean, Warp 3.454291ms mean, WSI consecutive intervals inference ~143.19Hz. WSI samples partial. No user requested further UI/geometric changes; preserve current scene.

## Experimental behavior
Optional `GPU GUARD 85%`, default **off**, for the existing 3D FG stress profile only.
- Estimate budget = 85% of the selected pacing period (WSI_SYNC when compatible, nominal 1/144 otherwise). Typically ~5.91ms for a 6.96ms interval.
- After the submit fence is signaled, retrieve the previously-generated GPU timestamp including Motion + Warp + barrier + blit. If it exceeds budget, skip **two upcoming odd synthetic slots** and present the last real image instead (HOLD), then probe a new FG sample.
- Preserve each even real frame at the same cadence and never change source shader, Motion/Warp shader, format, swapchain orientation, blit layout, driver, or kernel.
- The governor is disabled automatically without timestamp support. No effect on HOLD, 2D historical controls, or static benchmarks. A generated query failure is reported; it does not directly trigger fallback.
- The complete report distinguishes accepted presentations (real/generated/repeated), `GPU BUDGET solicitado/ativo/teto`, generated probes, overruns and adaptive HOLD. Present counts alone do not prove FPS scanned by display or reduced input latency.

## Validation A/B
1. Same 144Hz device and conditions. SYNC on, IDENTITY on, Motion radius3 fixed.
2. Run `3D 10s FrameGen` with GPU GUARD **off**; copy report.
3. Turn GPU GUARD **on** and repeat; compare generated vs held counts, GPU p95, WSI intervals >1.5 cycles, CPU fence/acquire wait and scene visual smoothness.
4. Repeat interleaved to compensate for heating. If aggressive fallback reduces visual fluidity, disable it. Do **not** call a reduced number of generated frames a 2× gain.
5. Future next step: optional adaptive thresholds, screen-space motion quality and independent latency measurement based on real game input-to-photon instrumentation.

This is a user-space C++/Vulkan lab. No root, driver changes or kernel flashing. `FLASH_READY=false`; EXP27 preserved.