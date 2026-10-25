# EXP29.4 — Pipa FrameGen Vulkan Lab APK

A standalone, reversibly installable **Android arm64 experimental test application** for Xiaomi Pad 6 / Adreno 650 (not a kernel/driver replacement).

## What happens when you press the button

1. The app synthesizes two reproducible 256×128 RGBA8 frames. Frame B is translated +2 pixels horizontally from frame A.
2. Native JNI initializes Vulkan and selects a compute-capable queue, then allocates storage images, a host-coherent staging buffer and a command buffer.
3. The app loads two validated SPIR-V compute shaders from APK assets and constructs the experimental EXP29.3 Vulkan pipeline.
4. Upload A and B, estimate tile motion, interpolate at t=0.5, transfer result back to CPU memory and display the returned image in Android UI.
5. The app reports Vulkan device identity, submit-to-fence **CPU wall time**, total JNI call wall time, and quality MAE against known correct midpoint alongside a naive 50/50 blend baseline.

These are not physical presentation times and not 60-to-120 FPS claims. There is no rendering loop, swapchain interception, FPS unlock, interaction with commercial games, driver replacement, root requirement or kernel modification.

## Build using GitHub Actions

Open [Pipa EXP29.4 - FrameGen Vulkan Lab APK](../../../../actions/workflows/exp29.4-vulkan-lab-apk.yml) in the repository. Download artifact named `pipa-exp29-4-vulkan-lab-<run_number>` from a successful run. It includes `app-debug.apk`, shader SPIR-V blobs, the SHA-256 report and build logs.

The build pipeline pins:
- Android Gradle Plugin 8.13.2, Gradle 8.13, API 35 compileSdk, targetSdk 34, minSdk 29.
- Android NDK 27.2.12479018, arm64-v8a, CMake 3.22.1.
- glslangValidator + spirv-val Vulkan 1.1 shader validation before APK packaging.

The Gradle wrapper is generated in CI and uploaded in the artifact; this source checkout can also be built using an installed Gradle 8.13.

## Manual build

```bash
sudo apt-get install -y glslang-tools spirv-tools
mkdir -p lab-app/app/src/main/assets
for shader in shaders/*.comp; do
  glslangValidator -V --target-env vulkan1.1 -S comp "$shader" -o "lab-app/app/src/main/assets/$(basename "$shader").spv"
  spirv-val --target-env vulkan1.1 "lab-app/app/src/main/assets/$(basename "$shader").spv"
done
# Configure ANDROID_HOME with API 35, Build Tools 35, NDK r27c, CMake 3.22.1.
gradle --project-dir lab-app :app:assembleDebug
```

Install on a testing device:

```bash
adb install -r lab-app/app/build/outputs/apk/debug/app-debug.apk
adb logcat -s AndroidRuntime VulkanLoader
```

The app can fail cleanly when Vulkan is unavailable, RGBA16F storage-image format is unsupported, the feature `shaderStorageImageExtendedFormats` is unsupported, or host-coherent Vulkan transfer memory is unavailable. Those failures do not mean a kernel change is needed.

## Engineering limitations / next gates

- Native Vulkan image transfers/command submission are implemented, but actual Adreno execution **must** be verified from a device log and displayed image, not from successful compilation.
- Vulkan work is done **offscreen**; Android UI displays the returned bitmap. It is not an Android game swapchain implementation.
- Source QA must distinguish compilation, SPIR-V validation, on-device successful dispatch, image quality, and physical presentation frame rate.
- Future work: use GPU timestamp queries, many-frame steady-state benchmarking without recreating resources, independent per-frame descriptor sets, optional quality safeguards and a developer-owned Vulkan swapchain test.
- `FLASH_READY=false`; EXP27/USB Ethernet remain unchanged.
