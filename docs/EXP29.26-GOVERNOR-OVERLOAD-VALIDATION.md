# EXP29.26 — Controlled GPU Guard overload validation

This diagnostic build adds four extra Vulkan compute passes to the original-scene frame only when the GPU Guard is enabled. Each pass redraws the same two source images with the same pair index. The last result is identical; the additional work raises the measured original-frame GPU cost so the real pair-budget controller can be exercised.

No UI layout, camera, geometry, shader, swapchain policy, kernel, or device driver is changed. With the Guard unchecked, the extra passes are skipped. This is a test build, not a normal performance baseline.

## Xiaomi Pad 6 procedure

1. Keep 144 Hz, WSI_SYNC, Motion FAST radius 3, 3D IDENTITY, and 16:9 fit.
2. Select 3D 10s FrameGen and enable GPU GUARD PAR 85%.
3. Copy the report. Confirm GPU BUDGET active is 1 and scene stress passes is 4.
4. Inspect over-budget pair count, three-strike trips, adaptive HOLDs, generated/repeated counts, missed deadlines, and WSI gaps.

If all 540 probed pairs exceed the 11.8 ms budget during a 720-pair run, the policy-model expectation is 720 real, 540 interpolated, 180 adaptive HOLDs, and 180 governor trips. Actual device counts depend on measured GPU timings; this build does not assume every pair will exceed the threshold.

With the Guard unchecked, the extra passes are skipped and 2× FrameGen remains the control. WSI timing is driver-reported and does not establish physical scanout FPS or input-to-photon latency.

The EXP29.25 reference branch and APK remain unchanged. No kernel flash is involved.
