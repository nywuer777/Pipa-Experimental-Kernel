# EXP29.18 — sustained GPU timestamp timing and WSI coverage

## EXP29.17 on-device signoff

Two Xiaomi Pad 6 (Adreno 650, Android 16) screenshots showed both corrected procedural V2 modes without the EXP29.14-15 bottom barcode, stripe or green HUD blocks.

| 144Hz request (short, 240 presentations) | Accepted | WSI timing records | Adjacent valid IDs | Mean interval | p95 | WSI inferred cadence |
| --- | --- | --- | --- | --- | --- | --- |
| V2 FG 72→144 | 120 real + 120 interpolated | 117 | 87 | 7.034265ms | 6.984167ms | 142.161267Hz |
| V2 HOLD 72→144 | 120 real + 120 held | 150 | 120 | 6.957340ms | 6.964740ms | 143.733098Hz |

Both zero missed CPU sleep deadlines; native reports preTransform=2 (90°), useBlit=1, swapFormat=37 (R8G8B8A8_UNORM), 144Hz screen mode. This confirms **visual correction of the synthetic source**, not that output is physically 144FPS in a commercial game.

## New work EXP29.18

1. Two 10-second *requested* profiles: **STRESS 10s V2 HOLD** vs **STRESS 10s V2 FrameGen**. 1440 presentation attempts each, 720 distinct procedural original images and 720 repeated/FG slots respectively. Expected duration at 144Hz ~10s; if queue/compositor pacing is slower, actual runtime can be longer. Never report 1440 frames as if they were all physically scanned out.
2. Vulkan timestamps for every successfully submitted command buffer (where queueFamily.timestampValidBits > 0 and timestampPeriod > 0). Uses a recycled VkQueryPool, two timestamps per command (TOP and BOTTOM), reads previous frame only after fence completion, distinguishes source-render+blit from FG-compute+blit. These are **GPU in-command workload** durations; not presentation/scanout and not standalone kernel timing. Optional: no timestamp support means unavailable, not 0ms.
3. WSI reported actualPresentTime statistics: count and explicit percentage coverage relative to accepted vkQueuePresentKHR submissions; mean/p50/p95/p99/max for intervals between consecutive IDs with strictly increasing actualPresentTime; count of observed intervals >1.5 refresh cycles. The WSI subset is not necessarily representative of all presented frames and is not exhaustive dropped-frame detection.
4. p95 CPU wall time spent inside vkQueuePresentKHR calls. A CPU call duration is not the GPU execution duration, and neither is an independent sensor-based optical FPS metric.
5. The old short V2, diagnostic, procedural, and static A/B profiles are preserved. No kernel changes.

## Test protocol

1. Install EXP29.18 debug APK from passing GitHub Actions workflow (version 308).
2. First run **STRESS 10s: V2 HOLD 72→144**, capture output and any visual instability. Then run **STRESS 10s: V2 FrameGen 72→144** under comparable conditions.
3. Record WSI coverage, valid adjacent IDs, p95/p99/max, >1.5 cycles, and GPU real/FG sample p95. Note that HOLD GPU 'original+blit' includes repeated original copies in one class.
4. Repeat 2-3 times at controlled device temperature. Compare first and later samples, monitor jank/thermal throttling and independent screen presentation before inferring any 2x usability.
5. If shader time exceeds 6.94ms on many frames at 144Hz, prioritize removing synchronization and GPU idle, evaluating asynchronous buffering/multi-queue and workload adaptivity, not forcing 144Hz in games.

No game interception, driver modification, root, kernel flash or promise of gaming FPS. EXP27, KGSL, Turnip and SurfaceFlinger preserved. `FLASH_READY=false`.
