# EXP29.17 — Procedural texture V2, visual closure candidate

## Xiaomi Pad 6 device evidence — EXP29.16, 25 Oct 2026

Both diagnostic source variants display a clean four-quadrant image (no vertical stripe/bottom green patch) while retaining the same FIFO WSI pipeline and blit path.

| 144Hz request | VK_GOOGLE_display_timing intervals | Mean ms | p95 ms | WSI inferred rate | Real / Generated / Held |
| --- | ---: | ---: | ---: | ---: | --- |
| Diagnostic FG 2x | 91 | 7.031704 | 6.976198 | 142.213031Hz | 120 / 120 / 0 |
| Diagnostic HOLD | 120 | 6.956000 | 6.973021 | 143.760773Hz | 120 / 0 / 120 |

240 accepted presentation calls each, no missed *CPU pacing* deadlines. Valid consecutive-ID timing coverage is partial and doesn't independently establish panel scanout or game FPS/latency.

**Scene transform**: native WSI reports preTransform=2 = VK_SURFACE_TRANSFORM_ROTATE_90_BIT_KHR; blit=1, swapFormat=37 (VK_FORMAT_R8G8B8A8_UNORM). Screenshot corners are rotated consistently with the transform: green/yellow at physical top edge, red/blue at physical bottom. The apparently bottom-edge stripe in the legacy source maps to the *x<source scroll* prefix after this rotation.

**Root-cause hypothesis strengthened by reading source shader**: EXP29.14's pipa_scene.comp uses `int x=max(0,xy.x-2*scene.frameIndex)`. Every new source frame pushes more pixels into the same x=0 source column. At real frameIndex 120, that is a 240-pixel-wide strip in a 1280px source. The grain function `(x*17+y*23+(x*y)%29)&63` then creates a conspicuous repeating, high-frequency pattern over the clamped region. A bit-HUD at y<42 explains the separate green/black block. Rotation plus nearest-neighbor blit makes that region appear as horizontal bottom band with vertical lines in landscape screenshot. This is strong causal evidence for a procedural scene artifact, not an interpolation defect. Actual chip/GPU per-pixel correctness remains to be tested with device captures.

## Code changes

- `shaders/pipa_scene_v2.comp`: new explicitly **periodic** x source `(p.x-shift+width)%width`, shift=2px/frame; background uses 128px tileable geometric blocks and smooth local shading, no high-frequency grain, no HUD bitmask.
- Scene ABI unchanged (rgba8 storage image, push constants vec2 dimensions/frameIndex/reserved, 16x16 dispatch). Native frame generation SPARSE + TILED shaders and Vulkan WSI frame presentation are unchanged.
- `PresenterActivity`: new 'V2 corrigida HOLD 72→144 (sem FG)' and 'V2 corrigida FrameGen 72→144'. All EXP29.16 diagnostic, legacy procedural and static profiles retained.
- Source contract `test_procedural_v2.py`: verifies zero use of max-clamp, all 1280 source x coordinates unique for every test frame, no old procedural grain, exact asset/button wiring, version 307.
- GitHub Actions builds/validates all SPIR-V, runs all regression contracts, assembles signed Android ARM64 APK.

## Hardware validation

1. Run V2 HOLD 72→144 and visually inspect the full rotated surface: no bottom streaks or green/black corner block expected.
2. Run V2 FrameGen 72→144 and compare same border, object trails and WSI intervals.
3. Confirm 120 real + 120 interpolated or held, respective modes, and record actualPresentTime consecutive samples plus p95. Short tests only.
4. Compare to legacy procedural HOLD as positive control: legacy stripe remains by design.
5. High-frequency motion, disocclusion and UI artifact testing remain open, as does physically independent scanout and input latency. Successful synthetic FG does not imply 2x gaming FPS.

**EXP27, Turnip, KGSL and SurfaceFlinger unchanged.** No root/flash. FLASH_READY=false.
