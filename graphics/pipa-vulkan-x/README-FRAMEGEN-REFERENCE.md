# EXP29.2 - Pipa FrameGen: CPU reference (non-realtime)

This is a **real deterministic motion-compensated frame interpolation reference**, not a Vulkan-integrated runtime. It estimates per-16x16-tile integer motion using RGB sum-of-absolute-differences (2px sample interval, search radius up to 4px), warps two input frames using bilinear sampling, then synthesizes an intermediate RGBA8 image at a specified time fraction.

Call `pipa_framegen_reference_rgba8(previous, current, output, width, height, stride, phase, search_radius)` through the C ABI in `include/pipa_framegen_reference.h`. Separate output buffer is required. It accepts two frames owned by the app, not swapchain content captured from another process.

**This is a correctness oracle, not a speed claim.** The algorithm runs on CPU, does not enqueue Vulkan work, manage presentation, claim FSR3 equivalence, bypass frame caps, or produce additional display presents. It is intentionally limited to 8-bit SDR and small local displacements. Problems remain with fast movement, scene changes, UI/HUD, transparent objects, occlusions, frame pacing and input latency.

Host test: `ctest --test-dir build --output-on-failure` after CMake configuration. The existing `pipa_frame_engine` target includes the reference function, so the same C ABI is available in the NDK arm64 library.

## Next engineering stage (not implemented)

1. Vulkan shader port: downscaled block motion field; full-resolution warp and blend; synchronisation barriers and descriptor/pipeline management.
2. Two-stage UI handling (world frame before HUD; HUD composited afterward), conservative scene-change and high-motion skip.
3. Own-app swapchain integration with real frame pacing; compare OFF vs ON using frame timing and external frame capture.
4. Gate on latency/thermal stability and 1% lows. Roll back to passthrough when synthesis is slower than its available budget.

No kernel, KGSL, driver, SurfaceFlinger, Magisk or vendor changes in this stage.
