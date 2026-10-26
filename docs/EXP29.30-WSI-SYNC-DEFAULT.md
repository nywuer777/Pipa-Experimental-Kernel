# EXP29.30 — WSI_SYNC default pacing

## Decision

Make **SYNC experimental: usar período Vulkan WSI do monitor (144 Hz)** checked by default. The checkbox remains available for an A/B comparison. The native presenter still uses WSI_SYNC only at a 144 Hz request and only when the queried display period is within 3% of nominal; 60/120 Hz and unavailable/out-of-range timing continue to use FIXED_REQUEST.

## Evidence carried forward

- Capture 31739 used normal **3D 10s FrameGen 72→144** with WSI_SYNC on and reported 0/1,440 late starts, 1/541 long WSI intervals, and 143.475 Hz cadence.
- Capture 31735 used the same scene with WSI_SYNC off and reported 318/1,440 late starts, 1/364 long intervals, and similar cadence (~143.5 Hz).
- The later Guard A/B captures 31743–31744 used WSI_SYNC off and reported 0 and 1 late starts after the EXP29.29 hidden-load correction. This means the earlier late-start difference is not established as a repeatable WSI_SYNC benefit.

## EXP29.30 change

- `SYNC experimental` initializes checked; it remains user-controllable.
- GPU Guard stays unchecked by default.
- Scene geometry, UI layout, swapchain configuration, and Vulkan identity transform are unchanged.
- Android version: 29.30-wsi-sync-default (`versionCode 320`).
- CI adds CPU pacing and display-timing source contracts to the APK build.

## Device validation

On the Xiaomi Pad 6, use **3D 10s FrameGen 72→144**, keep **GPU GUARD PAR 85%** off, **Motion FAST experimental** off, and **3D IDENTITY WSI** on. Compare one run with **SYNC experimental** checked and one unchecked; repeat in reverse order. Confirm the report says `CPU pacing=WSI_SYNC` when checked and `FIXED_REQUEST` when unchecked. Compare late starts, WSI interval tails, reported cadence, and GPU generated+blit cost. This remains app-only; no kernel flash.

## Xiaomi Pad 6 A/B (31746–31747; 21:36; battery 69%)

Both captures used **3D 10s FrameGen 72→144**, **GPU GUARD PAR 85%** off, **Motion FAST experimental** off (radius 4), and **3D IDENTITY WSI** on. Only **SYNC experimental** changed.

| Capture | SYNC experimental | Frames | CPU pacing | WSI cadence | Long intervals |
|---|---|---|---|---|---|
| 31746 | On | 720 interpolated, 0 repeated | WSI_SYNC 6.957779 ms; 0/1,440 starts over one period | 143.360933 Hz; interval mean 6.975401 ms | 1/363 |
| 31747 | Off | 720 interpolated, 0 repeated | FIXED_REQUEST 6.944444 ms; 7/1,440 starts over one period, all inherited before sleep | 143.338053 Hz; interval mean 6.976514 ms | 1/361 |

Both runs have similar reported WSI cadence and one long interval each. WSI_SYNC reduced the CPU late-start count from 7 to 0 in this paired run without reducing the number of generated frames. This supports the EXP29.30 default for CPU pacing; it does not show a change in physical scanout rate or prove lower touch-to-photon latency. Generated+blit mean/p95 was 5.853205/6.248125 ms with WSI_SYNC and 6.141542/6.233698 ms with FIXED_REQUEST; these are GPU timestamps, not scanout measurements.

## Xiaomi Pad 6 A/B follow-up (31749–31750; 22:09–22:10; battery 55%)

Both screenshots show **3D 10s FrameGen 72→144**, **GPU GUARD PAR 85%** off, **Motion FAST experimental** off (radius 4), and **3D IDENTITY WSI** on. Each reports 1,440 accepted presents (720 real, 720 interpolated, 0 repeated). The screenshots are timestamped with SYNC on at 22:09 (31749), then off at 22:10 (31750); this is the same visible run order as the prior pair, not the requested off-then-on order.

| Capture | SYNC experimental | CPU pacing | WSI cadence and intervals | Generated+blit |
|---|---|---|---|---|
| 31749 | On | WSI_SYNC 6.957795 ms; 0/1,440 starts over one period | 143.460312 Hz; mean 6.970569 ms; long 1/410 | mean 5.772421 ms; p95 6.210208 ms |
| 31750 | Off | FIXED_REQUEST 6.944444 ms; 3/1,440 starts over one period, all inherited before sleep; max streak 2 | 143.326707 Hz; mean 6.977067 ms; long 1/361 | mean 6.134894 ms; p95 6.465937 ms |

This pair again shows the same direction in the CPU pacing counter (0 vs. 3 late starts), with 720 generated frames in both runs and similar reported WSI cadence. It adds evidence for the WSI_SYNC default, but the order was not reversed, so it does not control for run order. The GPU measurements are separate runs and do not establish a causal performance difference.

### Separate WSI transform diagnostic

Both captures report `topSuboptimal=1440`, `perSwapchainSuboptimal=1440`, `resultMismatch=0`, and `errors=0`. They also report `IDENTITY ativa=1`, `currentTransform=2`, `selectedPreTransform=1`, and surface extent 2844×646. This is a distinct WSI status diagnostic; it is not evidence that SYNC caused the result, and it does not indicate a Vulkan present error. Investigate why the app receives SUBOPTIMAL on every present while the identity transform is active before drawing further conclusions about swapchain status.

Decision: retain WSI_SYNC as the default candidate for 144 Hz. The pacing counter has shown 0 late starts with WSI_SYNC in both reported pairs versus 7 and 3 with FIXED_REQUEST, while generated-frame counts and sampled WSI tails remain comparable. Keep the option available. The latest captures require no APK code change; EXP29.30 remains the current APK. No kernel flash.


## Follow-up source inspection

The presenter calls `querySurfaceAfterSuboptimal()` when the top-level present result is SUBOPTIMAL, but the function is guarded by `surfaceCapsQueriedAfterSuboptimal` and returns after the first successful or failed query. The 1,440 SUBOPTIMAL results therefore do not cause 1,440 surface-capability queries. The present loop counts the results and continues; it exits on OUT_OF_DATE or another error. No pacing or render-path code change is justified by these captures alone.

Next isolating device comparison: retain **SYNC experimental** checked in both runs, keep the scene and other controls fixed, and compare **3D IDENTITY WSI** checked versus unchecked. Record whether `selectedPreTransform` follows identity or `currentTransform`, the top-level/per-swapchain SUBOPTIMAL counts, CPU late starts, and WSI interval tails. This tests the transform/status hypothesis separately from pacing. EXP29.30 remains the APK for this test.
