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


## Fixed-request pacing captures (31734–31735; 19:57; battery 92%)

Both captures used IDENTITY-on, the fixed 144 Hz request period (6.944444 ms), no WSI_SYNC, no Motion FAST, and no GPU Guard. The HOLD capture had 720 real plus 720 repeated frames, 0/1,440 CPU late starts, WSI mean 6.956923 ms, reported cadence 143.741718 Hz, and 0/522 intervals above 1.5 cycles. It returned VK_SUBOPTIMAL_KHR on all 1,440 presents.

The normal FrameGen capture had 720 real plus 720 interpolated frames, 0 repeats, and 318/1,440 CPU late starts; all 318 were classified before sleep, with 0 new after sleep and a maximum late sequence of 310. The GPU pair guard was disabled. GPU generated+blit mean/p95 were 6.148960/6.246562 ms. WSI consecutive intervals averaged 6.976017 ms, with 1/364 above 1.5 cycles and reported cadence approximately 143.4 Hz. All 1,440 presents returned VK_SUBOPTIMAL_KHR, consistent with IDENTITY-on.

This adds evidence that fixed-request pacing can accumulate CPU deadline lateness during FrameGen even while the sampled WSI intervals remain mostly regular; it does not establish that the lateness caused visible cadence loss. The HOLD result has a different workload, so it is only a control. The next isolating comparison is FrameGen with identical settings and IDENTITY-on, changing only WSI_SYNC; then repeat in reverse order. Keep GPU Guard disabled for this scheduler comparison.

The 31734–31735 capture adds no code change. The EXP29.28 APK remains the applicable binary for reproducing this comparison.


## Additional WSI_SYNC control captures (31736–31738; 20:02–20:05)

All three screenshots show **3D 10s HOLD 72→144** in the report, not **3D 10s FrameGen 72→144**: each reports 720 real, 0 interpolated, 720 repeated, with `cena=continua GPU HOLD sem FG`. The checkbox **SYNC experimental: usar período Vulkan WSI do monitor (144 Hz)** is checked; **3D IDENTITY WSI (teste principal)** is checked; **Motion FAST experimental: raio 3 (padrão 4)** and **GPU GUARD PAR 85%: HOLD após 3 pares GPU acima do teto** are unchecked. CPU late starts are zero in all three captures. The app reports all 1,440 presents as VK_SUBOPTIMAL_KHR, with zero trace-layer errors.

| Capture | Reported WSI cycle | WSI interval window | Reported cadence | Long intervals |
|---|---:|---:|---:|---:|
| 31736 | 6.957863 ms | n=722, mean 6.956662 ms | 143.741718 Hz | 0/722 |
| 31737 | 6.956090 ms | n=363, mean 6.976322 ms | 143.420070 Hz | 0/363 |
| 31738 | 6.957863 ms | n=377, mean 6.975343 ms | 143.362128 Hz | 1/377 |

These captures confirm the WSI_SYNC HOLD control only. They do not provide the requested normal FrameGen comparison with **SYNC experimental** checked. For that measurement, run the button **3D 10s FrameGen 72→144**; verify the report says `interpolado=720` (or close) and `cena=continua GPU 2x` before saving the screenshot.


Capture 31739 (20:07; battery 87%) is **3D 10s FrameGen 72→144**, with **SYNC experimental: usar período Vulkan WSI do monitor (144 Hz)** and **3D IDENTITY WSI (teste principal)** checked; **Motion FAST experimental: raio 3 (padrão 4)** and **GPU GUARD PAR 85%: HOLD após 3 pares GPU acima do teto** unchecked. Telemetry: 720 real, 720 interpolated, 0 repeated; 0/1,440 CPU late starts; WSI pacing period 6.955519 ms; WSI mean interval 6.969839 ms; reported cadence 143.475331 Hz; long intervals 1/541; all 1,440 presents VK_SUBOPTIMAL_KHR with zero trace-layer errors. GPU generated+blit mean/p95 were 6.145310/6.277500 ms.


Compared with 31735 (**3D 10s FrameGen 72→144**, SYNC unchecked; same IDENTITY-on, Motion FAST-off, Guard-off settings), capture 31739 has 0 versus 318 CPU late starts. The reported WSI cadence is similar (approximately 143.5 Hz in both); long intervals were 1/541 with SYNC on versus 1/364 with it off. This supports using **SYNC experimental** for this workload to avoid the CPU late-start count, while the measured WSI cadence stayed similar. It is a single paired observation with unequal WSI windows, so repeat with reversed order before treating the effect as established.


## Pair-budget A/B with fixed-request pacing (31740–31741; 20:14–20:17)

Both captures used **3D 10s FrameGen 72→144**, **SYNC experimental** off, **Motion FAST experimental** on at radius 3, and **3D IDENTITY WSI** on. Only **GPU GUARD PAR 85%: HOLD após 3 pares GPU acima do teto** changed between runs. Both report the continuous 2× scene and 1,440 accepted Vulkan presents.

| Capture | GPU Guard | Frames | Guard telemetry | CPU pacing | WSI cadence |
|---|---|---|---|---|---|
| 31740 | On | 720 real, 719 interpolated, 1 repeated | 719 pairs; 4 over the 11.805555 ms ceiling; 1 three-strike trip; pair mean 9.479760 ms, p95 9.843385 ms | FIXED_REQUEST 6.944444 ms; 1,109/1,440 starts over one period, all classified before sleep; 0 new after sleep | 142.952369 Hz; 2/363 intervals >1.5 cycles |
| 31741 | Off | 720 real, 720 interpolated, 0 repeated | Guard inactive; no pair probes | FIXED_REQUEST 6.944444 ms; 0/1,440 starts over one period | 143.431206 Hz; 1/424 intervals >1.5 cycles |

The no-Guard capture retained all 720 interpolated frames and reported zero late starts. With the Guard enabled, only one generated slot was repeated, while the report recorded 1,109 late starts. The sampled WSI cadences are close and the windows differ in length; this pair shows no presentation-regularity benefit from enabling the Guard and a large CPU-pacing anomaly in 31740. Treat the late-start difference as a result to reproduce, not proof of causation from one run. Keep the Guard off for the normal FrameGen reference; repeat this same pair in reverse order before making a stronger causal claim.

