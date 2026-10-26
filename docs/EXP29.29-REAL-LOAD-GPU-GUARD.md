# EXP29.29 — GPU Guard on real FrameGen workload

## Hardware evidence

Captures 31740 and 31741 used the Xiaomi Pad 6 (Adreno 650), **3D 10s FrameGen 72→144**, **SYNC experimental** off, **Motion FAST experimental** on at radius 3, and **3D IDENTITY WSI** on. The GPU Guard was the only changed option.

- Guard on (31740): 719 interpolated, 1 repeated; 4/719 measured pairs over the 11.805555 ms ceiling; 1,109 CPU starts over one period; 2/363 sampled WSI intervals over 1.5 cycles.
- Guard off (31741): 720 interpolated, 0 repeated; 0/1,440 CPU starts over one period; 1/424 sampled WSI intervals over 1.5 cycles.
- Reported WSI cadence was 142.952 Hz and 143.431 Hz respectively. The sampling windows differ, so one pair is evidence for follow-up, not proof of causation.

## Source finding

presenter.cpp added four diagnostic scene recomputes whenever the GPU Guard was enabled. The added work ran even in **3D 10s FrameGen 72→144**, so the Guard comparison changed both the guard and the GPU workload. That made the 31740 CPU lateness result unsuitable for judging the Guard on the normal scene.

## EXP29.29 change

- The standard 3D FrameGen path now measures the actual real-plus-generated pair without adding four hidden scene passes.
- The stress-pass count is carried explicitly into the native presenter and reported as passes stress cena=0 for the standard 3D test.
- The four-pass diagnostic injection is removed from the FrameGen run path; the telemetry reports `passes stress cena=0`.
- The visible controls, scene geometry, Vulkan identity transform, and swapchain behavior are unchanged.
- Android version is 29.29-real-load-gpu-guard (versionCode 319).

## Device validation

Install this APK and run **3D 10s FrameGen 72→144** with **GPU GUARD PAR 85%: HOLD após 3 pares GPU acima do teto** enabled, keeping **SYNC experimental** off and the other two checkboxes as in 31740. Confirm the report shows passes stress cena=0, then compare generated/repeated counts, CPU late starts, pair GPU timings, and WSI intervals with the guard unchecked. Repeat in reverse order. This is an app-only experiment; it does not modify or flash the kernel.
## Xiaomi Pad 6 validation (31743–31744; 21:25–21:26)

Both EXP29.29 runs used **3D 10s FrameGen 72→144**, **SYNC experimental** off, **Motion FAST experimental** off (radius 4), and **3D IDENTITY WSI** on. Only **GPU GUARD PAR 85%** changed.

| Capture | GPU Guard | Frames | GPU pair and fallback | CPU pacing | WSI cadence |
|---|---|---|---|---|---|
| 31743 | On | 720 real, 719 interpolated, 1 repeated | 3/719 pairs over 11.805555 ms; 1 trip and 1 HOLD; mean 7.238309 ms, p95 7.763646 ms | 0/1,440 starts over one period | 143.423138 Hz; 1/380 long intervals |
| 31744 | Off | 720 real, 720 interpolated, 0 repeated | Guard inactive; no pair samples | 1/1,440 starts over one period, inherited before sleep | 143.349042 Hz; 1/361 long intervals |

Both runs show `passes stress cena=0`, confirming the EXP29.29 fix on device. Generated+blit mean/p95 was 6.102681/6.272708 ms with Guard on and 6.136133/6.229323 ms with Guard off. The WSI cadence differs by about 0.074 Hz; each capture has one sampled interval above 1.5 cycles. The Guard's single hold did not produce a measurable presentation-regularity improvement. This reverse-order hardware pair also fails to reproduce the 31740 CPU-lateness anomaly: both runs had zero or one late start.

Decision: EXP29.29 is hardware-validated for the intended pair-budget behavior. Keep **GPU GUARD PAR 85%** off in the normal reference profile; retain it as an optional experiment. This result closes the GPU Guard comparison. The next implementation stage should move to the presentation pacing path rather than retune the Guard on these near-identical results.
