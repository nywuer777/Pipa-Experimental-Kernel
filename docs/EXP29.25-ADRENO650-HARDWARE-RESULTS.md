# EXP29.25 — Adreno 650 hardware follow-up

Date: 2026-10-25, screenshots received at approximately 15:25 local time.
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

## HOLD control — 3D HOLD 10 s

This is a separate no-FrameGen control, not the Guard-off FrameGen run:

- Accepted presents: 1,440 (720 real, 0 interpolated, 720 repeated).
- GPU budget requested/active: 0/0; no pair probes.
- CPU deadlines missed: 0/1,440.
- WSI report: 143.393281 Hz from 431 consecutive intervals; 1/431 intervals exceeded 1.5 cycles.

The HOLD and Guard-enabled runs use different workloads and sample counts. Their WSI rates do not establish a cadence improvement or regression.

## Comparison and decision

EXP29.24's normal FrameGen reference also produced 720 interpolated frames and zero repeats, with a reported 143.479213 Hz cadence and 1/541 long WSI intervals. EXP29.25's Guard-enabled capture matches the reference frame counts. The current screenshots do not include a same-session EXP29.25 FrameGen run with Guard disabled, so they do not form a controlled on/off A/B.

Keep the Guard optional and off by default. The on-device result confirms 2× is retained with measured GPU margin. The sustained-overbudget path (three consecutive pairs above 11.83 ms, then one adaptive HOLD and a subsequent probe) remains unexercised on hardware.
