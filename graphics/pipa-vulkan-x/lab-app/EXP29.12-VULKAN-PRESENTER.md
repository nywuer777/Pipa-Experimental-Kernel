# EXP29.12 — Native Vulkan swapchain presenter (Android arm64 / Adreno 650)

## EXP29.11 actual device measurements (reported screenshots)

All measurements are 1280×720, 1 warmup + 8 GPU timestamp pairs, synthetic two-pixel motion, Xiaomi Pad 6/Adreno 650.

| GPU | SPARSE+ADAPTIVE | SPARSE32+ADAPTIVE | SPARSE+TILED | SPARSE32+TILED |
| --- | ---: | ---: | ---: | ---: |
| Motion average (ms) | 4.241016 | 4.211211 | 4.253997 | 4.213835 |
| Warp+barrier average (ms) | 3.629792 | 3.742545 | 1.976230 | 1.977617 |
| Total average (ms) | 7.870807 | 7.953756 | 6.230228 | 6.191452 |
| Total p95 (ms) | 7.886041 | 8.190729 | 6.295052 | 6.235000 |
| Synthetic midpoint MAE | 0 | 0 | 0 | 0 |

TILED cuts the SPARSE Warp cost by 45.6% and total GPU cost by 20.8% (one measured A/B). SPARSE32+TILED leads in this single run by only 0.6% over SPARSE+TILED—too small to select 32 lanes as default. Both tiled profiles are retained. 6.19ms GPU p95 excludes Android presentation, rendering, storage-image transitions, input latency and frame queuing; a 144Hz interval is 6.944ms.

## New presenter architecture

A new in-app `PresenterActivity` uses a real Android `SurfaceView` and a native Vulkan `VkSurfaceKHR`, `VkSwapchainKHR`, `VK_PRESENT_MODE_FIFO_KHR` and calls `vkQueuePresentKHR`. It uses the existing **SPARSE 64-thread motion + TILED 16×16 warp** shader pair; source and destination images are resident in the GPU (no repeated CPU readback of generated frames). It keeps previous offscreen tests intact in MainActivity.

- The activity offers 60, 120 and 144 Hz *requested CPU pacing*, not changes to the hardware screen refresh mode.
- The presenter initializes two persistent RGBA8 synthetic frames at 1280×720, sends them to device-local images once, and executes the Vulkan motion/warp pipeline for each intermediate frame.
- The surface alternates a repeating oscillation of real A / computed midpoint / real B / computed midpoint. This is a **synthetic presentation integration diagnostic**, not a live game renderer and not streaming/interception of third-party frames.
- Uses one compute-and-present queue, a one-frame-in-flight fence, per-swapchain-image render-complete semaphores, an image-available semaphore, and one recording command buffer. Swapchain usage requires `VK_IMAGE_USAGE_TRANSFER_DST_BIT`; a native blit scales/format-converts the interpolated/output image to the swapchain when necessary. Unsupported capabilities report a clear diagnostic rather than attempting an invalid present.
- Uses the actual device's surface extent and a FIFO present mode. Handles surface loss/out-of-date by stopping the session (surface recreation is a future gate).
- UI reports the number of successfully accepted `vkQueuePresentKHR` calls, requested pacing, GPU name, wall time, and accepted calls/s. **Accepted swapchain present calls do not prove physical display presents or end-to-end latency.** The actual display cadence is compositor- and device-dependent; the test does not use `VK_GOOGLE_display_timing` or external high-speed capture.

### Build and test

CI: `.github/workflows/exp29.12-vulkan-presenter-apk.yml` compiles shaders to Vulkan 1.1 SPIR-V, runs source ABI/dispatch/surface tests, assembles and signs the ARM64 APK. No kernel flash. No root.

Install the successful APK on a Vulkan-compatible Xiaomi Pad 6. Open **Pipa FrameGen Lab EXP29.12**, then **Abrir Vulkan Presenter**. Choose 60/120/144 Hz request. Verify a changing pattern is visible **in the SurfaceView**, and capture the report of accepted present calls, GPU name, and any Vulkan errors. Stop or navigate away to terminate the native loop.

**Next gate after first on-device present:** actual frame presentation timing through a supported Vulkan presentation-timing extension or independent frame capture, then steady-state GPU compute+blit timing, VSync pacing, resource reuse, thermal behavior and real/virtual frame latency. No 120/144 displayed FPS claims on the strength of API submission counts alone.

`FLASH_READY=false`; EXP27, Turnip, KGSL, SurfaceFlinger untouched.
