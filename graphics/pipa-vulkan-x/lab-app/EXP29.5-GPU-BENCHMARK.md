# EXP29.5 — GPU Timestamp Benchmark (Xiaomi Pad 6 / Adreno 650)

## Device evidence that motivated this cycle (EXP29.4)

A screenshot from the actual Xiaomi Pad 6 shows `Adreno (TM) 650`, successful Vulkan Compute interpolation of a synthetic 256x128 image sequence translated horizontally by 2 pixels, reported midpoint error `GPU=0.00`, naive blend `20.92`, CPU-side submission/fence `5.804114 ms`, and full JNI/Vulkan call `48.19 ms`. This is a successful **small synthetic on-device functional test**, not a reliable per-frame GPU shader duration, game FPS, or input latency. Values are one observation from the device UI, not statistical performance evidence.

## What this release adds

- A second button, `Benchmark GPU (1 aquecimento + 32 amostras)`.
- Reuses shader pipelines, descriptors, allocations and input images for all passes within the measurement. The initial pass warms the pipeline and is excluded from statistics.
- Optional Vulkan timestamp query pool with two queries around each complete motion/interpolation dispatch pair.
- Correct Vulkan compute-to-compute memory barrier between passes, plus existing motion-to-interpolation image barrier.
- Compute timings are converted from query ticks using `VkPhysicalDeviceProperties.limits.timestampPeriod` and masked to the compute queue family's `timestampValidBits`.
- Reports number of GPU samples, mean, median (p50) and p95 in ms. Query-unavailable devices receive an explicit `indisponiveis` status rather than invented timing.
- Keeps original output image, accuracy comparison, end-to-end wall clock and CPU queue submission + fence duration.

**Interpretation:** the GPU timestamp span covers two Vulkan compute stages and their internal dependency, but not device creation, image upload, readback, CPU/UI overhead, or Android presentation. All 32 samples use the same synthetic inputs; this is a GPU microbenchmark, not a real video or game loop. An interpolated output cannot improve the game's simulation tick and **does not prove extra physical display frames**.

## How to test

1. Install the CI-built `app-debug.apk` on the Xiaomi Pad 6. Because CI may sign successive debug APKs using different debug keys, uninstall the old `dev.pipa.framegen.lab` package if an update produces `INSTALL_FAILED_UPDATE_INCOMPATIBLE`. The lab does not store important user data.
2. Launch the Pipa FrameGen Lab EXP29.5 app.
3. Tap `Executar interpolação na GPU` for a single frame and verify image + correctness.
4. Tap `Benchmark GPU (1 aquecimento + 32 amostras)`. Capture the reported GPU device, `GPU Compute` mean/p50/p95, total CPU time and output error.

To investigate suspicious results: capture `adb logcat -d -s AndroidRuntime VulkanLoader`, device refresh mode and approximate skin temperature. The app never modifies KGSL, SurfaceFlinger, Turnip or EXP27.

## Limits / next gate

- Await successful CI NDK compile, SPIR-V validation and `apksigner verify` before claiming the new APK build is ready.
- Await on-device screenshot for EXP29.5 GPU timestamp support and distribution.
- Next: measure multiple resolutions (e.g. 640x360 and 1280x720), isolate motion and warp pass GPU times, avoid mixing thermal throttling into a single run, and build an **owned Vulkan swapchain sample** to measure actual physical frame presentation.
- `FLASH_READY=false`.
