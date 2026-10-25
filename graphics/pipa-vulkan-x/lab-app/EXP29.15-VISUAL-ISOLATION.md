# EXP29.15 — Visual source isolation: HOLD versus FrameGen 2x

## EXP29.14 Xiaomi Pad 6 Adreno 650 measurements

Five user screenshots from real Vulkan FIFO WSI; source GPU 1280x720, 240 presentations accepted, 120 real + 120 generated in each 2x mode. The GPU driver supports VK_GOOGLE_display_timing.

| Profile | WSI records | consecutive ID pairs | mean interval ms | p95 ms | WSI reported Hz | missed CPU deadlines |
|---|---:|---:|---:|---:|---:|---:|
| Static 60 | 204 | 174 | 16.713168 | 27.850156 | 59.833060 | 0 |
| Static 120 | 150 | 120 | 8.407991 | 13.927709 | 118.934471 | 0 |
| Continuous 60->120 | 151 | 121 | 8.337132 | 13.930416 | 119.945324 | 0 |
| Static 144 | 121 | 91 | 7.033362 | 6.977709 | 142.179506 | 0 |
| Continuous 72->144 | 127 | 97 | 7.027973 | 6.976042 | 142.288548 | 0 |

WSI cadence is calculated from *only observed consecutive present IDs*, not exhaustive display scanouts. 'Missed CPU deadlines=0' means the program did not detect sleep-wakeup delays of more than one intended interval; it is not proof of no compositor frame drops or stutter.

## Visual finding

Continuous-mode screenshots show lower striped area and green HUD-like marker. This is not proof of faulty interpolation. The procedural shader pipa_scene.comp computes patterned grain using x*17+y*23+(x*y)%29 and an animated bit-ID HUD in xy.y<42. The swapchain surface orientation can make the HUD appear near the physical bottom edge. Diagnostic A/B is required before rewriting Motion/Warp.

## EXP29.15 new isolated control

**HOLD GPU (72 source updates -> 144 presentation calls)** computes the same pair of procedurally changing Vulkan GPU images on each even presentation slot, but reuses the same real source image on each odd slot, **without executing FrameGen**. The existing continuous 2x 144Hz mode computes the same real sources, but the odd slot runs SPARSE+TILED interpolation.

Both modes share the same SurfaceView, native VkSwapchainKHR FIFO and optional Vulkan WSI timing extension. Separate counters report:
- HOLD: 120 real, 0 generated, 120 repeated (for 240 successful accepted calls).
- FG 2x: 120 real, 120 generated, 0 repeated (for 240 successful accepted calls).

Test: Install the CI-signed EXP29.15 APK. Compare screenshots and, ideally, a short external high-frame-rate video of HOLD and FG 2x at the same display refresh. If the lower stripes appear in HOLD, suspect procedural source/blit/orientation. If only FG shows them, inspect motion field confidence, interpolation and edge sampling. Native actualPresentTime intervals measure WSI presentation timing, not independent optical scanout. Preserve old static and FG profiles for regression.

No root, no EXP27 kernel, KGSL, Turnip or SurfaceFlinger modifications. FLASH_READY=false.
