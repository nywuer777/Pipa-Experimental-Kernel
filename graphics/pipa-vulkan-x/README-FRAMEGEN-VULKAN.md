# EXP29.3 — Pipa FrameGen Vulkan Compute (experimental)

**Scope:** app-owned Vulkan compute frame interpolation. No GPU driver, KGSL, Android compositor, kernel, root or vendor image modification. `FLASH_READY=false`.

## Implemented source

- `shaders/pipa_motion.comp`: GLSL 450, 8x8 compute groups, 16x16-pixel blocks, search radius 0..4, sampled RGB SAD displacement to RGBA16F flow image.
- `shaders/pipa_interpolate.comp`: RGBA8 bilinear previous/current warps and temporal blending, per-tile mismatch fallback. Input `phase` from 0 to 1.
- `src/pipa_framegen_vk.cpp`: creates compute pipelines/descriptors, records motion dispatch, a motion-image WRITE-to-READ barrier and interpolation dispatch.
- Original EXP29.1 telemetry/EXP29.2 CPU reference preserved.

## Shader validation

```sh
sudo apt-get update && sudo apt-get install -y glslang-tools spirv-tools
mkdir -p build-shaders
for f in shaders/*.comp; do
  glslangValidator -V --target-env vulkan1.1 -S comp "$f" -o "build-shaders/$(basename "$f").spv"
  spirv-val --target-env vulkan1.1 "build-shaders/$(basename "$f").spv"
done
python3 tests/test_vk_contract.py
```

## NDK r27c ARM64 build

```sh
cmake -S . -B build-android -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_TOOLCHAIN_FILE="$ANDROID_NDK_HOME/build/cmake/android.toolchain.cmake" \
  -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-29 \
  -DPIPA_ENABLE_VULKAN=ON -DPIPA_BUILD_TESTS=OFF
cmake --build build-android
```

Outputs: `libpipa_frame_engine.so` (original CPU component) and `libpipa_framegen_vk.so` (new optional Vulkan component). SPIR-V binary shaders are separate assets, **not** embedded into the library. CI archives both native libraries and the compiled shaders if successful.

## Integration contract

Caller owns the `VkInstance`, `VkPhysicalDevice`, compute-enabled `VkDevice`/queue, 2D single-mip single-layer Vulkan images, image views, command buffer, scheduling, fences, swapchain and presentation.

Required VkImage usage includes `VK_IMAGE_USAGE_STORAGE_BIT` and all image layouts must already be `VK_IMAGE_LAYOUT_GENERAL` at record time. Formats and extents:

- Previous/current/output: `VK_FORMAT_R8G8B8A8_UNORM`, `width × height`.
- Motion: `VK_FORMAT_R16G16B16A16_SFLOAT`, `ceil(width/16) × ceil(height/16)`.

Set 0 bindings 0/1/2/3 are four storage images. Push constants are 20 bytes: `int32 width,height,radius; float phase,errorCutoff`. Framegen rejects missing optimal tiling storage-image format support. Supply two *valid* SPIR-V blobs to `pipa_framegen_vk_create()`; supply an already-recording compute-capable command buffer and views to `pipa_framegen_vk_record()`. The function records dispatches only, not queue submission.

Caller must make previous/current readable by compute before recording and must insert an output write-to-read/transfer barrier and transition before presentation. An internal barrier handles the motion field between the two compute passes. Caller must not update this context's descriptor set while a command buffer referring to it is still in flight; simplest is one context per in-flight frame. Destroy context after GPU work has completed.

**Limitations:** not FSR3 equivalence. No true full optical flow, edge-aware motion, occlusion handling, separate HUD composition, scene-cut detector, custom Vulkan swapchain or measured latency/performance yet. Compiling or recording commands does not prove frames appear on-screen. The next gate is a Vulkan Android sample APK and frame timing comparisons OFF/ON on Xiaomi Pad 6 (Adreno 650). Do not claim doubled FPS without physical presentation measurements.

Build/test state belongs to CI logs and on-device measurements; do not infer a successful hardware test from a compiled shader.
