# EXP29.28 — Identity transform A/B on Adreno 650

Evidence: user-provided Xiaomi Pad 6 screenshots from two sessions. The explicit Vulkan trace layer was active in all instrumented captures.

## Initial results (18:33–18:34; battery 7–8%)

| Profile | IDENTITY | Reported presentation result | Visual output | Other observations |
|---|---:|---|---|---|
| HOLD control | On | 1,440 top-level and per-swapchain VK_SUBOPTIMAL_KHR; 0 errors | Preserves validated scene geometry | 0 CPU late starts; WSI long intervals 1/741 |
| HOLD control | Off | 1,440 VK_SUCCESS; 0 VK_SUBOPTIMAL_KHR; 0 errors | Captured output visibly flattened | 0 CPU late starts; WSI long intervals 0/663 |
| Pair-budget FrameGen | On | 1,440 top-level and per-swapchain VK_SUBOPTIMAL_KHR; 0 mismatches; 0 errors | Preserves validated geometry | 719 interpolated, 1 repeated; 6/719 pairs above budget; 1 trip and 1 HOLD; 763/1,440 CPU late starts; WSI long intervals 1/363 |
| Pair-budget FrameGen | Off | 1,440 VK_SUCCESS; 0 VK_SUBOPTIMAL_KHR; 0 errors | Captured output visibly flattened | 719 interpolated, 1 repeated; 4/719 pairs above budget; 1 trip and 1 HOLD; 180/1,440 CPU late starts; WSI long intervals 2/363 |

For IDENTITY-on, the surface query succeeded and reported current extent 2844x646, current transform 2, and selected preTransform 1. Top-level and per-swapchain results matched. In the IDENTITY-off FrameGen capture, preTransform and currentTransform were both 2.

## Follow-up captures (31724–31727; 18:38–18:39; battery 7–8%)

| Capture | Profile and transform | Frame counts and GPU guard | Present result and cadence | CPU pacing |
|---|---|---|---|---|
| 31724 | HOLD, IDENTITY on | 720 real, 720 repeated; guard inactive | 1,440/1,440 top-level and per-swapchain VK_SUBOPTIMAL_KHR; query succeeded; 143.731728 Hz; long intervals 0/736 | 0 late starts |
| 31725 | Normal FrameGen, IDENTITY off | 720 real, 720 interpolated; telemetry says guard inactive, no pair probes | 1,440 VK_SUCCESS; 143.799363 Hz; long intervals 0/500; output visibly flattened | 0 late starts |
| 31726 | Pair-budget FrameGen, IDENTITY off | 719 interpolated, 1 repeated; pair mean 9.164044 ms, p95 9.965781 ms; 4/719 over budget; 1 trip/HOLD | 1,440 VK_SUCCESS; 142.958773 Hz; long intervals 2/363 | 1,435/1,440 late starts, all before sleep; 0 new after sleep |
| 31727 | Pair-budget FrameGen, IDENTITY on | 719 interpolated, 1 repeated; pair mean 9.502318 ms, p95 9.796562 ms; 6/719 over budget; 1 trip/HOLD | 1,440/1,440 top-level and per-swapchain VK_SUBOPTIMAL_KHR; query succeeded; 143.338222 Hz; long intervals 1/363 | 8/1,440 late starts, all before sleep; 0 new after sleep |

The selected CPU periods were 6.944444 ms and 6.957265 ms in 31726 and 31727; the WSI interval means were 6.995024 ms and 6.976506 ms. If each difference persisted across all 1,440 presents, it would accumulate to roughly 73 ms (10.5 cycles) and 28 ms (4 cycles). WSI samples cover only reported consecutive windows; this is a pacing-drift hypothesis, not proof of whole-run drift or cause.

## High-battery repeat (31729–31732; 19:51–19:52; battery 93–94%, charging)

| Capture | Profile and transform | Frame counts and GPU guard | Present result and cadence | CPU pacing |
|---|---|---|---|---|
| 31729 | HOLD, IDENTITY on | 720 real, 720 repeated; guard inactive | 1,440/1,440 top-level and per-swapchain VK_SUBOPTIMAL_KHR; query succeeded; 143.504065 Hz; long intervals 1/720 | 0 late starts |
| 31730 | Pair-budget FrameGen, IDENTITY on | 615 interpolated, 105 repeated; pair mean 12.121753 ms, p95 13.587968 ms; 318/615 over 11.828330 ms; 106 trips, 105 HOLDs | 1,440/1,440 top-level and per-swapchain VK_SUBOPTIMAL_KHR; 142.946970 Hz; long intervals 2/364 | 11/1,440 late starts, all before sleep; 0 new after sleep |
| 31731 | HOLD, IDENTITY off | 720 real, 720 repeated; guard inactive | 1,440 VK_SUCCESS; 143.748344 Hz; long intervals 0/510; output visibly flattened | 0 late starts |
| 31732 | Pair-budget FrameGen, IDENTITY off | 718 interpolated, 2 repeated; pair mean 10.813382 ms, p95 11.165208 ms; 6/718 over 11.828097 ms; 2 trips, 2 HOLDs | 1,440 VK_SUCCESS; 141.795664 Hz; long intervals 5/364; output visibly flattened | 1,436/1,440 late starts, all before sleep; 0 new after sleep |

This high-battery run validates the governor's overload response in 31730: elevated pair cost corresponded to many threshold overruns and 105 intentional holds. In 31732, the pair mean and p95 remained below the ceiling and the governor held only two slots. Both runs used four scene stress passes. They were not thermally instrumented or randomized, so the GPU-cost and CPU-pacing differences cannot be assigned to IDENTITY alone. The large CPU late-start count in 31732 again does not map cleanly to the smaller WSI sample window; 5/364 intervals were long and the reported cadence was lower, so the result should be retained as a real pacing anomaly to reproduce, not dismissed.

The pacing periods in 31730 and 31732 were 6.957841 ms and 6.957704 ms; reported WSI interval means were 6.995601 ms and 7.052402 ms. These sampled means suggest possible drift, especially in 31732, but the consecutive windows cover only part of the run. They do not establish whole-run phase drift.

## Decision and next step

IDENTITY-on preserves the validated perspective and consistently returns VK_SUBOPTIMAL_KHR; IDENTITY-off clears that status but visibly flattens the scene. Keep IDENTITY enabled. Do not choose the current-transform path solely to clear the status.

At high battery, the guard preserved 615/720 generated slots under the heavier measured pair load in 31730 and 718/720 in 31732 under a lower measured pair load. This shows the three-strike policy responds to measured overload; it does not show that either transform choice caused the workload difference. The guard remains optional, and this stress-enabled result is not a normal-load recommendation.

The next hardware comparison should use the same transform and scene first, then repeat with only IDENTITY changed; keep the four stress passes, mode, and run duration identical, reverse run order on a second pair, and log device temperature if available. Compare paired GPU distributions, CPU late starts, selected pacing period, and WSI interval distribution together. The 31729–31732 session was at 93–94% battery but still charging; temperature stability was not recorded.

The screenshot heading still says EXP29.25 and is stale experiment text. Present calls and driver-reported WSI timestamps do not prove physical scanout, displayed FPS, or touch-to-photon latency. No kernel change or flash was part of these experiments.
