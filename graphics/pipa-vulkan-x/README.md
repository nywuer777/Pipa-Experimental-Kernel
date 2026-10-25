# Pipa Vulkan X — EXP29.1: Frame Engine

Early experimental native C++17 component for **owned/authorized Android Vulkan applications**.

It **does not replace** the Vulkan driver, remove game-engine caps, hook third-party games, or change Android system/vendor files. Future Turnip driver experiments are separate.

## Implemented

- Rolling 1024 frame intervals: average FPS, 1% low, p50/p95/p99 frametimes.
- A cadence heuristic for 24/30/40/45/60/72/90/120/144/165/240 Hz. Cadence is **not proof** of an engine cap.
- Pure deadline calculator for a test application's own frame loop: 0 means no artificial pacing imposed by this library; does not change SurfaceFlinger.

## Build on Linux/Windows host

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
ctest --test-dir build --output-on-failure
```

## Android arm64 using Android NDK r27c

```sh
cmake -S . -B build-android \
  -DCMAKE_TOOLCHAIN_FILE="$ANDROID_NDK_HOME/build/cmake/android.toolchain.cmake" \
  -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-29 \
  -DPIPA_BUILD_TESTS=OFF -DCMAKE_BUILD_TYPE=Release
cmake --build build-android
```

Output: `libpipa_frame_engine.so`, a support library for an **app we build**, not a Vulkan ICD or an installable APK. It cannot globally unlock games or bypass game caps. Supported Vulkan present modes, application simulation tick, compositor, thermals and display refresh limit realized FPS.

## API

Include `include/pipa_frame_engine.h`. A loop owned by the developer supplies monotonic `uint64_t` timestamps in nanoseconds to `pipa_frame_engine_record` and can call `pipa_frame_engine_stats`. Do **not** equate recording timestamps at CPU submit or present request to actual physical scan-out/display timing; integrate Vulkan/Android frame timing explicitly in a future iteration. This initial engine does not modify the existing Android render pipeline.

The frame planner `pipa_frame_engine_next_deadline` computes a deadline only; it performs no sleeping or system hook and does not raise GPU/display frequency. In uncapped mode (`target_hz=0`), no delay is introduced by the planner. Actual FPS depends on the application, WSI and compositor.

Next: owner-controlled Vulkan sample APK, baseline measurements from stock GPU driver, Turnip/KGSL isolated driver build pinned to upstream Mesa, app-scoped A/B comparison. No device reboot, vendor replacement, root injection or kernel flash.
