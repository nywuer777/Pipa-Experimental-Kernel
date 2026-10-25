# EXP29.19 — CPU pacing attribution and Vulkan WSI-aligned 10-second comparator

## Source of truth: EXP29.18 Adreno 650 screenshots, 2026-10-25

| Measurement | FrameGen 2x | HOLD (no FrameGen) |
| --- | ---: | ---: |
| 144Hz requested, calls accepted | 1440 | 1440 |
| Real / interpolated / held | 720 / 720 / 0 | 720 / 0 / 720 |
| CPU recorded "missed deadlines" | 0 | **501** |
| vkQueuePresentKHR accepted calls/sec | 143.921339 | 143.799386 |
| GPU original + blit mean / p95 ms | 0.937396 / 1.916302 | 1.001434 / 1.604010 |
| GPU generated + blit mean / p95 ms | 4.707615 / 6.144583 | N/A |
| GPU timestamp failures | 0 | 0 |
| VK_GOOGLE_display_timing records (coverage) | 587 (40.763889%) | 561 (38.958333%) |
| Valid consecutive-ID intervals | 407 | 381 |
| WSI mean / p95 interval ms | 6.977757 / 6.965572 | 6.956902 / 6.966666 |
| WSI cadence inferred from observed intervals | 143.312526Hz | 143.742142Hz |
| >1.5 display cycles (observed intervals) | 1/407 | 0/381 |
| WSI reported display cycle | 6.960285ms | 6.960832ms |
| CPU vkQueuePresentKHR p95 | 0.249062ms | 0.210678ms |

**Interpretation.** These short 10s synthetic tests show a low frequency of *observed* long WSI intervals. The 501 CPU "missed deadlines" occur when software passes a nominal 6.944444ms scheduling grid by more than one slot, regardless of when the display presents the image. HOLD can be late by this definition while recording regular WSI timestamps. It is NOT proof of 501 dropped physical frames, nor proof of no dropped frames, because actualPresentTime samples cover only ~39-41% of accepted IDs.

The GPU generated-frame cost, measured as TOP/BOTTOM command timestamps around motion + warp + blit + barriers, averages 4.71ms with p95 6.14ms; it cannot be called pure shader time or game-independent latency. Original compute + blit 0.94ms. There is limited headroom at the 6.96ms reported scan cycle under this synthetic load.

### Hypothesis to test — fixed clock accumulation

Previous code uses `interval = 1_000_000_000ns / 144` exactly while WSI reports the actual period ~6.9608ms. A 0.0164ms per-frame mismatch may accumulate to ~23.6ms over 1440 frames if the CPU is naturally paced by WSI FIFO. That is >3 nominal frame periods. Fixed clock phase drift, blocking in vkAcquireNextImageKHR, fence waiting and sleep timer jitter are plausible *contributors*. Their relative impact was not previously measured; avoid assigning all 501 to drift without evidence.

## Changes for EXP29.19

- The **FIXED_REQUEST** comparator retains nominal 1/144s scheduling.
- The experimental **WSI_SYNC** checkbox, only for a 144Hz request when VK_GOOGLE_display_timing returns a cycle within 3% of the nominal period, uses the actual refresh period. On no extension, zero period or other target Hz, it silently uses FIXED_REQUEST and **reports** that fallback.
- Per-frame CPU metrics separate `beforeSleep` already >1 slot late (inherited overrun), `afterWake` newly >1 slot late (timer oversleep), CPU lateness distribution mean/p95/p99/max, vkWaitForFences wait, vkAcquireNextImageKHR wait and vkQueueSubmit wall duration.
- The original `deadlineMisses` counter is retained for compatibility, now explicitly labeled **CPU wake > one selected period** in the new report. WSI p50/p95/p99, coverage and GPU timestamp data are retained and not conflated.
- Android clipboard button copies the complete full report for reliable analysis, avoiding unreadable screenshots.
- All legacy profiles, SPIR-V shaders, Motion/Warp GPU implementation, native WSI blit and V2 source remain unchanged. No kernel/Turnip/KGSL changes.

## Hardware A/B validation

At screen mode 144Hz:
1. Untick SYNC. Run **STRESS 10s V2 HOLD** and then **STRESS 10s V2 FrameGen**. Copy and archive both complete reports.
2. Tick SYNC. Repeat same two stress profiles, preferably several passes interleaved to reduce thermal-order bias.
3. Report selected pacing mode and period, inherited late entries, new oversleeps, longest late burst, fence wait/acquire wait, CPU submit and vkQueuePresent p95, GPU real/generated and WSI long-gap/coverage.
4. Classify: if SYNC reduces inherited overruns without worsening WSI intervals and display quality, it may be the more appropriate target cadence. If timer oversleeps dominate, investigate Android scheduler/CPU load. If acquire waits dominate, presentation queue/backpressure is likely.
5. No claim of real gaming FPS, photon latency or system-wide frame generation; the test currently controls its own Vulkan Surface and submits synthetic frames.

CI compiles SPIR-V, tests ABI and CPU pacing contracts, assembles signed debug arm64-v8a APK. No flash. EXP27 preserved; FLASH_READY=false.
