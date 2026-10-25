# EXP29.20 — Adreno 650 Motion/Warp GPU breakdown + radius comparison

## EXP29.19 on-device evidence (Xiaomi Pad 6 / Android 16 / 144Hz)

Two screenshot reports, both 1440 accepted Vulkan FIFO present calls and WSI_SYNC enabled.

| Statistic | FG 720 real + 720 generated | HOLD 720 real + 720 repeats |
| --- | ---: | ---: |
| WSI cycle chosen | 6.959220ms | 6.956924ms |
| CPU wake >1 period | 0/1440 | 0/1440 |
| Inherited overrun / newly overslept | 0 / 0 | 0 / 0 |
| GPU original+blit avg / p95 | 0.899409 / 0.934792ms | 0.871715 / 1.517448ms |
| GPU generated+blit avg / p95 | 4.737008 / 6.041719ms | unavailable |
| CPU fence wait mean / p95 | 0.130345 / 0.775052ms | 0.006682 / 0.010729ms |
| CPU acquire mean / p95 | 1.176426 / 3.018542ms | 0.038044 / 0.052552ms |
| Accepted API calls per second | 143.698055 | 143.830723 |
| WSI timing returned IDs | 541 (37.57%) | 805 (55.90%) |
| WSI adjacent present intervals | 361 | 625 |
| WSI interval mean / p95 | 6.995266 / 6.956822ms | 6.962275 / 6.965834ms |
| Observed interval >1.5 cycles | 1/361 | 0/625 |
| WSI inferred cadence | 142.953819Hz | 143.631202Hz |

The 501 CPU deadline count in EXP29.18 HOLD (fixed nominal scheduling) was not reproduced with WSI_SYNC, but without same-version same-conditions FIXED runs, do not claim isolated causal proof. The current experiment is a self-contained Vulkan synthetic scene, NOT a gaming FPS test. WSI timing coverage is partial, not optical scanout.

## EXP29.20 changes

- Retain the same `pipa_scene_v2.comp` source and all prior modes including WSI_SYNC and 10-second stress.
- Reuse the already defined `pipa_framegen_vk_record_profiled` instrumentation in the FrameGen core to generate **three additional GPU timestamps** (motion begin, motion end, warp end) on synthesized frames, alongside total command TOP/BOTTOM timestamps.
- Expand reusable `VkQueryPool` from two to five queries and reset all five in the frame command buffer; read them only after the submit fence is signaled, and only for a synthesized frame (not HOLD or original). The query split measures *Motion*, *Warp plus compute barrier*, while the total includes layout transitions, blit and ancillary operations. Component timings are not assumed perfectly additive.
- New optional `Motion FAST experimental: raio 3` checkbox (unchecked by default). Default radius 4 retains the previous behavior. Radius 3 tests a smaller search for current 2px synthetic motion; it may worsen quality for larger or occluded movement and must not be activated indiscriminately in games.
- Report includes counts, means and p95 for Motion, Warp and total generated workload, plus query failures. CPU/WSI reporting is unchanged.

## Test protocol

1. Keep SYNC enabled, FAST off, run **STRESS 10s V2 FrameGen** (radius 4); copy complete report.
2. Enable FAST (radius 3), repeat same FrameGen stress. Compare Motion average/p95, Warp average/p95, total generated average/p95, WSI intervals, CPU acquire/fence delays, and visual quality.
3. Run V2 HOLD for unchanged control; timestamps for Motion/Warp should say 'sem amostras' in HOLD mode.
4. Optionally repeat radius 4 after radius 3 to check heat/order artifacts; do not conclude speed gain from single sample.
5. Do not infer 144 physical FPS or input-to-photon latency; those require independent measurements.

All shaders and EXP27/Turnip/KGSL/SurfaceFlinger remain unchanged; no root, flash, or game interception. `FLASH_READY=false`.
