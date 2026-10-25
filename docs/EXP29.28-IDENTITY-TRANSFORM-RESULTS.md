# EXP29.28 — Identity transform A/B on Adreno 650

Evidence: four user-provided Xiaomi Pad 6 screenshots captured at 18:33–18:34, with battery at 7–8%. The layer is active in all captures.

## Results

| Profile | IDENTITY | Reported presentation result | Visual output | Other observations |
|---|---:|---|---|---|
| HOLD control | On | 1,440 top-level and per-swapchain VK_SUBOPTIMAL_KHR; 0 errors | Preserves the validated scene geometry | 0 CPU late starts; WSI long intervals 1/741 |
| HOLD control | Off | 1,440 VK_SUCCESS; 0 VK_SUBOPTIMAL_KHR; 0 errors | Captured output is visibly flattened | 0 CPU late starts; WSI long intervals 0/663 |
| Pair-budget FrameGen | On | 1,440 top-level and per-swapchain VK_SUBOPTIMAL_KHR; 0 mismatches; 0 errors | Preserves the validated scene geometry | 719 interpolated, 1 repeated; 6/719 pairs above budget; 1 trip and 1 HOLD; 763/1,440 CPU late starts; WSI long intervals 1/363 |
| Pair-budget FrameGen | Off | 1,440 VK_SUCCESS; 0 VK_SUBOPTIMAL_KHR; 0 errors | Captured output is visibly flattened | 719 interpolated, 1 repeated; 4/719 pairs above budget; 1 trip and 1 HOLD; 180/1,440 CPU late starts; WSI long intervals 2/363 |

For IDENTITY-on, the diagnostic query succeeded and reported current surface extent 2844x646, current transform 2, and selected preTransform 1. The top-level and per-swapchain results matched on every call. For the unambiguous IDENTITY-off FrameGen capture, preTransform was 2 and currentTransform was 2.

## Decision

The transform choice controls the status: IDENTITY-on preserves the validated output but consistently produces VK_SUBOPTIMAL_KHR; the current-transform path returns VK_SUCCESS but visibly flattens the scene. Keep IDENTITY enabled for the validated geometry. Do not select the current-transform path solely to clear the status.

The pair governor behaves similarly in both FrameGen captures: 719 of 720 synthetic slots are generated and one slot is held. The large difference in CPU late-start counts (763 versus 180) is not reflected in the WSI long-interval counts or reported cadence. The device was at 7–8% battery during both runs, so treat that CPU difference as confounded and repeat the A/B after charging, with the same scene, settings, and run order reversed.

VK_SUBOPTIMAL_KHR indicates presentation still occurred while the swapchain was not optimally configured for its surface. It is not an error here: all 1,440 calls were accounted for, and the trace layer reported zero errors. The captured WSI cadence is driver-reported and does not prove physical scanout or displayed FPS.

The screenshot heading remains EXP29.25; it is stale experiment text. No UI geometry or kernel state was changed.

## Follow-up captures (31724–31727)

Four more screenshots were supplied at 18:38–18:39. The tablet still showed only 7–8% battery and a charging indicator, so this is not yet a charged-device repeat.

| Capture | Profile and transform | Frame counts and GPU guard | Present result and cadence | CPU pacing |
|---|---|---|---|---|
| 31724 | HOLD, IDENTITY on | 720 real, 720 repeated; guard inactive | 1,440/1,440 top-level and per-swapchain VK_SUBOPTIMAL_KHR; query succeeded; WSI 143.731728 Hz; long intervals 0/736 | 0 late starts |
| 31725 | Normal FrameGen, IDENTITY off | 720 real, 720 interpolated; report says guard inactive and no pair probes | 1,440 VK_SUCCESS; WSI 143.799363 Hz; long intervals 0/500; output is visibly flattened | 0 late starts |
| 31726 | Pair-budget FrameGen, IDENTITY off | 719 interpolated, 1 repeated; pair mean 9.164044 ms, p95 9.965781 ms; 4/719 over budget, 1 trip/HOLD | 1,440 VK_SUCCESS; WSI 142.958773 Hz; long intervals 2/363 | 1,435/1,440 late starts, all counted before sleep; 0 new late starts after sleep |
| 31727 | Pair-budget FrameGen, IDENTITY on | 719 interpolated, 1 repeated; pair mean 9.502318 ms, p95 9.796562 ms; 6/719 over budget, 1 trip/HOLD | 1,440/1,440 top-level and per-swapchain VK_SUBOPTIMAL_KHR; query succeeded; WSI 143.338222 Hz; long intervals 1/363 | 8/1,440 late starts, all counted before sleep; 0 new late starts after sleep |

Both guarded FrameGen runs stayed below the 11.8 ms pair ceiling at p95 and preserved 719 of 720 generated slots. Their reported cadence and long-interval counts are close, while the CPU late-start totals differ sharply. In both captures, the late starts were attributed to the pre-sleep portion; neither recorded new late starts after sleep. This mismatch between CPU counters and WSI interval behavior means the count difference cannot yet be attributed to IDENTITY or to the GPU guard. The battery was low and charging, and the run order/settings were not independently controlled.

These captures reinforce the geometry/status decision: IDENTITY-on keeps the validated perspective and returns VK_SUBOPTIMAL_KHR on every present; IDENTITY-off clears that status but the rendered scene is flattened. Retain IDENTITY. The 31725 report's guard status is taken from its telemetry (inactive, no pair probes), even though the current checkbox appears checked in the screenshot.

Next useful hardware step: repeat the IDENTITY-on/off pair-budget comparison after charging and letting the device reach a stable thermal state, use the same scene and controls, and reverse the run order. Compare CPU late starts alongside WSI intervals; do not use the CPU counter alone as evidence of visible cadence loss.

These present counters and driver-reported timestamps do not prove physical scanout, displayed FPS, or touch-to-photon latency. No kernel change or flash was part of these experiments.
