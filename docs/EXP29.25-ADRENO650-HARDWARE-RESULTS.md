# EXP29.25 — Adreno 650 hardware follow-up

Date: 2026-10-25. Guard-enabled capture at 15:25; HOLD at 15:31; Guard-off FrameGen at 15:32 local time.
Device: Xiaomi Pad 6, Adreno 650, 144 Hz, Vulkan FIFO, WSI_SYNC, Motion FAST radius 3, 3D IDENTITY, 16:9 fit.

## Guard enabled — 3D FrameGen 10 s

- Accepted presents: 1,440 (720 real, 720 interpolated, 0 repeated).
- GPU pair budget: 11.826881 ms; 720 paired probes.
- Pair overruns: 0; three-strike trips: 0; adaptive HOLDs: 0; unavailable pairs: 0.
- Last pair: 6.742760 ms; pair mean: 6.850637 ms; p95: 8.403021 ms.
- Generated frame + blit mean: 5.714641 ms; p95: 7.132552 ms.
- GPU query failures: 0; split-query failures: 0; CPU deadlines missed: 0/1,440.
- IDENTITY active; 16:9 fit active; destination viewport 1,148 × 646.
- WSI report: 143.216786 Hz from 541 consecutive intervals; 2/541 intervals exceeded 1.5 cycles. This is driver timing, not a physical scanout measurement.

Result: the corrected governor remained inactive because all measured pairs stayed below budget. The full 2× interpolation cadence was preserved.

## Guard disabled — 3D FrameGen 10 s

- Accepted presents: 1,440 (720 real, 720 interpolated, 0 repeated).
- GPU budget requested/active: 0/0; threshold displayed: 11.827490 ms; no pair probes.
- Original + blit mean: 1.561981 ms; p95: 1.672552 ms.
- Generated frame + blit mean: 5.665358 ms; p95: 6.408542 ms.
- GPU query failures: 0; CPU deadlines missed: 0/1,440.
- WSI report: 143.398033 Hz from 364 consecutive intervals; 1/364 exceeded 1.5 cycles.

## HOLD control — 3D HOLD 10 s (15:31)

This is a separate no-FrameGen control, not the Guard-off FrameGen run:

- Accepted presents: 1,440 (720 real, 0 interpolated, 720 repeated).
- GPU budget requested/active: 0/0; no pair probes.
- CPU deadlines missed: 0/1,440.
- WSI report: 143.551434 Hz from 708 consecutive intervals; 1/708 exceeded 1.5 cycles.

The HOLD and Guard-enabled runs use different workloads and sample counts. Their WSI rates do not establish a cadence improvement or regression.

## Comparison and decision

The 15:25 Guard-enabled and 15:32 Guard-disabled FrameGen runs both accepted 1,440 presents: 720 real, 720 interpolated, and zero repeated. Thus, with measured pair costs below the budget, enabling the Guard did not reduce 2× interpolation. The Guard-enabled run measured a pair mean of 6.850637 ms and p95 of 8.403021 ms against the 11.826881 ms limit; it recorded zero overruns and zero adaptive HOLDs.

The Guard-off run reports separate original and generated GPU distributions, not paired samples; their percentiles cannot be combined into a paired p95. The reported WSI cadence was 143.216786 Hz with Guard enabled and 143.398033 Hz with it disabled. These runs have different observation windows and WSI sample counts, so the small difference does not establish a cadence change. The separate 15:31 HOLD run is a no-FrameGen control, not an on/off comparison.

EXP29.24's normal FrameGen reference also produced 720 interpolated frames and zero repeats, with a reported 143.479213 Hz cadence and 1/541 long WSI intervals.

Keep the Guard optional and off by default. The functional on/off comparison is complete for the under-budget case. The sustained-overbudget path (three consecutive pairs above 11.83 ms, then one adaptive HOLD and a subsequent probe) remains unexercised on hardware. WSI timing is driver-reported and does not measure physical scanout or input-to-photon latency.
