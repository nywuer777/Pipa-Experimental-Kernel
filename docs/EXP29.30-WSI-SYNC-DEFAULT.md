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