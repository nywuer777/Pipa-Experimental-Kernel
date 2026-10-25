# EXP29.22 — visual geometry and aspect ratio correction for 3D FrameGen

## On-device baseline EXP29.21 (Xiaomi Pad 6 Adreno 650 / Android 16)

Two actual screenshots at local 09:52-09:53, both Motion FAST radius=3 and WSI_SYNC enabled. The lab rendered analytical ray-based 3D spheres and plane with motion, occlusion and stationary HUD. Both runs returned 1440 accepted presentation calls and zero CPU wake periods over budget.

| Metric | 3D FrameGen | 3D HOLD |
| --- | ---: | ---: |
| Accepted present calls | 1440 (720 real + 720 interpolated) | 1440 (720 real + 720 held) |
| WSI inferred cadence of sampled consecutive intervals | 143.272546Hz | 143.550500Hz |
| GPU original+blit avg/p95 | 1.404030 / 1.440937 ms | 1.330260 / 2.266198 ms |
| GPU generated+blit avg/p95 | 6.511056 / 6.887916 ms | N/A |
| Motion GPU mean/p95 | 2.188982 / 2.226458 ms | N/A |
| Warp+barrier GPU mean/p95 | 4.035176 / 4.245625 ms | N/A |
| WSI reported count/accepted coverage | 801 / 55.625% | 924 / 64.1667% |
| Consecutive valid WSI pairs / long >1.5 monitor periods | 621 / 2 | 744 / 1 |

The 3D generated-frame GPU workload averaged ~32% more than the 2D V2 benchmark radius3, 4.933ms vs 6.511ms. Its 6.888ms p95 is close to the ideal 144Hz 6.944ms frame interval. These timing results cover one synthetic scene and must not be asserted as 144 real game FPS. WSI timing coverage is incomplete.

### Visual root cause hypothesis

Both 3D screenshots show spheres appearing strongly horizontally flattened into ellipsoids in the portion of the app allocated to the swapchain. Earlier presenter code used a fixed 1280×720 source but unconditionally blitted to all of the current swapchain extent; the device reported an extent of **2844×790** (~3.60:1), while source geometry is **16:9** (~1.78:1). This nonuniform X/Y scale alone can distort scene geometry, even for correctly raytraced spheres. preTransform=2 is reported by the device, and post-compositor scaling must also be verified visually. Do not blame ray geometry or interpolator until the blit is aspect-preserved.

## EXP29.22 changes

- Keep 3D ray shader, Motion+Warp pipeline, WSI_SYNC, all benchmark UI profiles and complete metrics unchanged.
- 3D scene requests `fit3dAspect` via JNI; 2D historical baselines keep full-stretch behavior to preserve comparisons.
- Compute a centered 16:9 destination rectangle inside the current swapchain extent, using uniform scale and integer rounding.
- For blit-capable swapchain format, clear the destination to opaque black with `vkCmdClearColorImage`, insert transfer-write→transfer-write memory barrier, then blit source only into the destination rect, keeping color/depth geometry undistorted and ensuring old swap images cannot show uninitialized bars.
- Emit `FIT 16:9=1` and `viewport destino=WIDTHxHEIGHT` in the copied diagnostic report. The source always stays 1280×720.
- Where the surface is very wide, black side bars are expected **and correct**. A future UI iteration can allocate a larger 16:9 SurfaceView instead of squeezing the scene beneath the controls.

## Next test

1. EXP29.22 on real device: SYNC on; FAST radius3 or radius4 but keep the same setting throughout comparison.
2. Run 3D HOLD 10s and 3D FrameGen 10s; ensure spheres look circular, not flattened. Copy logs.
3. Confirm `FIT 16:9=1` with sane viewport dimensions and no leftover region or stretch. Black bars are acceptable.
4. Compare Motion/warp generated GPU times with EXP29.21 as regression information only. The extra clear could increase GPU blit time; do not claim performance gains.
5. Video or side-by-side photo of moving sphere edges required to evaluate occlusion ghosting, HUD jitter and temporal artifacts. Still screenshots cannot prove motion smoothness.

No Turnip/KGSL/SurfaceFlinger/kernel change; `FLASH_READY=false`. Source/CI validation is not hardware certification.
