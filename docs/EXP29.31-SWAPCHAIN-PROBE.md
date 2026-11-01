# EXP29.31 — App-scoped Vulkan swapchain probe

## Goal

Advance the opt-in `VK_LAYER_PIPA_present_trace` from observing presents to observing the lifecycle of the controlled application's Vulkan swapchain. This is the first integration gate before attempting any image processing in a layer.

## Change

- Intercept `vkCreateSwapchainKHR` and `vkDestroySwapchainKHR` in the existing app-enabled Vulkan layer.
- After successful creation, query the downstream driver once for the number of swapchain images. Do not retain or modify app image handles.
- Report aggregate swapchain creates, destroys, and image count next to existing present counters.
- Leave command buffers, image contents, pacing, generated frames, scene geometry, UI layout, and kernel untouched.
- Build identity: `29.31-swapchain-probe`, `versionCode 321`.

## Xiaomi Pad 6 validation

Run **3D 10s FrameGen 72→144** with **SYNC experimental** checked, **GPU GUARD PAR 85%** off, **Motion FAST experimental** off, and **3D IDENTITY WSI** on. Confirm the report shows:

- `VK_LAYER_PIPA available=1 active=1`;
- one or more `swapchains created`, nonzero `images`, and matching destruction after the run;
- 1,440 accepted presents with the existing expected 720 real + 720 interpolated counts;
- no change in scene appearance or pacing behavior from EXP29.30.

The exact image count and lifetime counts are driver/window lifecycle dependent; report what the device returns rather than hard-coding a specific count.

## Boundary

This probe proves only that the layer can observe the controlled app's swapchain lifecycle. It does not read pixels, synthesize frames inside the layer, load into unrelated apps, replace a Vulkan driver, or modify the kernel. The next gate is to acquire a safe, app-owned source image and validate a read-only copy with correct Vulkan synchronization before a layer-owned compute pass is attempted.

No kernel flash. Hardware execution remains pending until the APK is run on device.


## Build artifact

- GitHub Actions run #64: source contracts passed, APK assembly succeeded, and `apksigner verify --verbose` succeeded.
- Android version: `29.31-swapchain-probe` (`versionCode 321`).
- APK SHA-256: `f57e8e34846299819ef8a218e6ffd664b740920b460582c5f023427e75614119`.
- Built for arm64-v8a; standalone lab APK only; not tested on device yet.
