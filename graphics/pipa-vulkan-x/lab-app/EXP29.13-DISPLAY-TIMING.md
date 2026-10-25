# EXP29.13 — Vulkan WSI display timing lab

## EXP29.12: verified Xiaomi Pad 6 / Adreno 650 on-device evidence

The user provided three screenshots of the standalone Vulkan FIFO presenter, in its own Android SurfaceView. Reported surface extent: **2844×1310**. The diagnostic uploaded two static synthetic 1280×720 RGBA8 input frames to GPU, generated intermediates with existing SPARSE+TILED compute shaders and copied/blitted source/output into VkSwapchainKHR images.

| Requested CPU cadence | Accepted vkQueuePresentKHR submissions | Native API calls/s (CPU wall-clock) |
| --- | ---: | ---: |
| 60 Hz | 240 (120 original submissions, 120 generated submissions) | 60.139371 |
| 120 Hz | 240 (120/120) | 120.059730 |
| 144 Hz | 240 (120/120) | 143.945296 |

**Important:** These are submissions of alternating copies of two static input images and GPU-generated midpoints, not a continuously rendering gameplay simulation. Successful calls and screenshots prove the Vulkan presenter can run, **not** that every frame was physically scanned out at the requested rate or that gaming latency improves. The application and queue may be subject to compositor restrictions.

## EXP29.13 additions

- Optional query and activation of Vulkan `VK_GOOGLE_display_timing` after `vkEnumerateDeviceExtensionProperties`. `VK_KHR_swapchain` remains required; timing extension is not assumed on Adreno 650.
- When the extension is enabled and its entry points are available, append `VkPresentTimesInfoGOOGLE` to each present with a unique presentID. `desiredPresentTime=0` means no forced GPU/display schedule change; the existing FIFO pacing is preserved.
- Poll `vkGetPastPresentationTimingGOOGLE` asynchronously every 8 presentations and once after queue idle, collecting nonzero `actualPresentTime` records by ID. Avoid relying on a single final poll which might exceed the implementation's bounded history.
- Compute mean interval, p95 interval and implied cadence **only for adjacent presentation IDs with monotonic actualPresentTime**. Show number of valid observed timings and missing timing support explicitly. The refresh-cycle duration is obtained via `vkGetRefreshCycleDurationGOOGLE`, if possible.
- Android UI displays its `Display.getRefreshRate()` alongside requested cadence. Buttons use density-aware dimensions; fixes the tiny/cropped controls seen in EXP29.12 screenshots.
- MainActivity retains the old offscreen Vulkan benchmark and its untouched shader profiles.

## Validation boundaries

An actualPresentTime supplied by the presentation engine is stronger evidence than successful vkQueuePresentKHR submissions. It is still driver-level reporting, **not an independent optical/hardware scanout instrument**. Present feedback may be delayed, incomplete, or unavailable. Missing timing data must be displayed as unavailable, not treated as zero or as proof of 120/144 displayed FPS. For deeper confidence use external high-frame-rate recording / system compositor instrumentation.

The EXP29.13 presenter still loops over a synthetic pattern with only two repeated input images; motion remains subtle. It does not represent a game rendering 60 unique frames per second. Real-world verification still requires an owned continuously rendering scene with changing geometry, correct frame-generation scheduling and input-to-photon latency measurement.

### On-device test procedure

1. Install a **successful CI-build** ARM64 EXP29.13 APK. No root/kernel flash.
2. Open Vulkan Presenter, request 60 Hz, then 120 and 144 Hz one at a time.
3. Record: Android display refresh rate, WSI timing support, number of valid actualPresentTime records, measured mean/p95 intervals, any Vulkan errors, and API calls/s.
4. If timing extension is unavailable, stop treating 143.95 calls/s as a physical frame-rate measurement. Follow up with Android Frame Pacing / supported compositor telemetry rather than extrapolating.
5. If timing measurements exist, repeat runs and compare rate vs the Android screen mode, checking stutters, intervals >2 refreshes, and thermal consistency.

## Build

Workflow `.github/workflows/exp29.13-display-timing-apk.yml`. Pins Android NDK r27c and SDK; validates all compute SPIR-V blobs and source contracts, builds the native C++ Vulkan presenter and packages signed debug APK. VersionName 29.13-lab, versionCode 303.

EXP27 kernel, Turnip, KGSL and SurfaceFlinger remain unchanged. `FLASH_READY=false`.
