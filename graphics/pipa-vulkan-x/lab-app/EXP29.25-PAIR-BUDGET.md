# EXP29.25 — GPU budget across a real + synthetic frame pair

## Hardware evidence | Xiaomi Pad 6 / Adreno 650 / Vulkan WSI FIFO / 144Hz

EXP29.24 at 10:45–10:46 local time: 1440 accepted Vulkan presentation calls, 720 real frames in all modes, 0 CPU periods missed, `VK_GOOGLE_display_timing` WSI cadence approximately 143Hz. Both modes used 3D scene, WSI_SYNC, Motion FAST radius 3 and IDENTITY preTransform.

| Metric | GPU Guard OFF | GPU Guard 85% ON |
|---|---:|---:|
| FrameGen frames | 720 | 240 |
| Repeated (HOLD) frames | 0 | 480 |
| Generated+blit mean | 5.809055ms | 6.863570ms |
| Generated+blit p95 | 7.008750ms | 7.074114ms |
| WSI long intervals >1.5 cycles | 1/541 | 1/528 |
| WSI apparent cadence | 143.479213Hz | 143.463250Hz |

The old threshold of 85% of **one** 6.96ms monitor cycle was ~5.915ms and triggered on all 240 probes; each overrun caused two HOLD frames. The mode reduced generated frames by 66.7% without evidence of improved presentation cadence. GPU timestamps are not scanout or input-to-photon times. The generated GPU means are measured from different subsets and not controlled direct equivalents.

## Change (reversible; default OFF)

EXP29.25 compares measured **paired** work: original scene+blit plus next synthetic compute+blit, against `0.85 * (2 * current refresh period)`. At 144Hz, that is roughly 11.83ms. Two frames form a pair; a single frame's GPU cost must not be judged against an arbitrary 85% margin without considering the neighboring frame.

The governor now needs **3 consecutive over-budget completed pairs** to request **1** HOLD slot; a subsequent generated frame probes again. Any below-budget pair resets the streak. If timestamp support is absent or pair readings unavailable, fail open (no fallback). All counts and GPU paired average/p95 are logged.

No scene renderer, camera projection, shader, depth geometry, source WSI orientation, kernel, Turnip or KGSL changes. The existing EXP29.23 visual result is preserved.

## On-device A/B acceptance

1. Keep SYNC, 3D IDENTITY, Motion FAST checked and screen set to 144Hz.
2. Run 3D 10s FrameGen with GPU Guard unchecked: record real/generated/repeated, GPU pair p95, WSI long gaps and CPU late count.
3. Repeat with GPU Guard checked. Expected under EXP29.24-like load: nearly 720 generated, zero HOLD, paired mean ~7–9ms vs ~11.83ms threshold.
4. Repeat at warmer GPU conditions, ideally 3 alternating passes. Adaptive HOLD is acceptable only if there are sustained measured pair overruns and meaningful relief; otherwise preserve 2x.
5. Note: accepted `vkQueuePresentKHR` calls and reported WSI timings do not prove physical screen FPS.

`FLASH_READY=false`. Safe app-level build; EXP27 kernel untouched.