# EXP29.23 — WSI orientation A/B: preserve 3D scene geometry

## Hardware evidence from EXP29.22 (Xiaomi Pad 6 / Adreno 650)

Two screen captures at 10:05, both WSI_SYNC and Motion FAST radius=3, 1440 accepted present submissions.

| Metric | 3D HOLD | 3D FrameGen |
|---|---:|---:|
| real/generated/held | 720 / 0 / 720 | 720 / 720 / 0 |
| mean GPU original+blit | 1.258409 ms | 1.348593 ms |
| mean GPU generated+blit | N/A | 6.432381 ms |
| generated p95 | N/A | 6.640105 ms |
| mean Motion / Warp | N/A | 2.172369 / 4.025205 ms |
| CPU late > period | 0 | 0 |
| vkQueuePresentKHR accepted / rate | 1440 / 143.873266/s | 1440 / 143.877439/s |
| WSI inferred cadence | 143.543268 Hz | 143.496212 Hz |
| WSI observed intervals >1.5 cycles | 1/751 | 1/542 |

Both screenshots show the 3D image still very narrow vertically, even after the EXP29.22 reported `FIT 16:9=1` and `viewport destino=1404x790` for a `2844x790` swapchain. The black bars appear above and below the scene on the Android screen, **not** to its left and right. The same log reports `preTransform=2`, which is `VK_SURFACE_TRANSFORM_ROTATE_90_BIT_KHR`. Therefore the previous 16:9 fix was applied in a coordinate space that did not correspond to the screen's visible axes. More data is needed to establish the full compositor mapping.

## EXP29.23

- Keep source scene shader, GPU Motion/Warp and 16:9 center fit/blit unchanged.
- Request `preTransform=IDENTITY` **only** on the 3D test when `caps.supportedTransforms` includes IDENTITY. Otherwise use `caps.currentTransform` as documented Vulkan fallback. Earlier 2D tests always use current transform for comparability.
- New default-on **3D IDENTITY WSI** checkbox. Turn it off to run **WSI CURRENT** (previous EXP29.22 path) on the same APK. Full log prints current, chosen and supported transform mask, identity requested and activated, plus viewport destination.
- This is an A/B experiment, not a guarantee that IDENTITY will resolve the visual distortion on every Android compositor. Compare screenshots including letterbox axis and roundness of sphere silhouettes. If identity unsupported, results cannot establish the comparison.
- `VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR` (1) presents without surface transform; `VK_SURFACE_TRANSFORM_ROTATE_90_BIT_KHR` (2) indicates clockwise 90-degree transform. Android's WSI implementation advertises supported transforms; explicit pre-rotation can reduce compositor work on some systems but requires the app to apply the geometry transform itself.

### Hardware test protocol

1. Run 3D HOLD for 10s with SYNC enabled, Motion FAST same setting, 3D IDENTITY WSI checked. Report `IDENTITY ativa=1` and if spheres now look correctly proportioned.
2. Run 3D FrameGen similarly; compare black bar direction and sphere silhouettes.
3. Uncheck 3D IDENTITY WSI and repeat 3D HOLD as A/B currentTransform control. This should reproduce the visible EXP29.22 issue if caused by WSI rotation.
4. Compare GPU generated p95 and WSI observed long gaps. IDENTITY may incur additional compositor work on Android; rendering correctness takes precedence at this stage.
5. If distortion persists, log surface actual displayed geometry, SurfaceView size and native-window extent, and consider a rotation-aware blit or Vulkan graphics compositor. A scene screenshot alone cannot confirm physical presentation FPS.

No kernel/Turnip/KGSL modifications. NO FLASH. `FLASH_READY=false`. CI verifies ABI, source safety, shader compilation and APK packaging, not in-device visual geometry.
