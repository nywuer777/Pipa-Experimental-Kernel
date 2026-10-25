# EXP29.16 — Vulkan scene forensics and swapchain orientation audit

## EXP29.15 device evidence (2026-10-25, Xiaomi Pad 6 / Adreno 650)

Two screenshots, native Vulkan WSI FIFO, Android reports 144Hz, swapchain 2844x980. Both source HOLD (120 real + 120 repeated) and Vulkan FrameGen 2x (120 real + 120 generated) were observed.

| Profile | WSI actualPresentTime records | Consecutive intervals | Mean interval ms | p95 ms | WSI inferred cadence |
|---|---:|---:|---:|---:|---:|
| Continuous 72->144 FG | 121 | 91 | 7.034314 | 6.977136 | 142.160266 Hz |
| Continuous 72->144 HOLD no FG | 151 | 121 | 6.964507 | 6.975469 | 143.585186 Hz |

240 present calls accepted, missed CPU deadlines=0 in each. Evidence is only driver WSI timing for observed consecutive presentation IDs; not a measurement of photons, input latency or improvement in commercial games.

**Key finding:** the bottom-edge stripe of narrow vertical lines AND the small green/black block both visibly appear in the HOLD source without any Motion or Warp dispatch. This excludes FrameGen as the exclusive cause, but does not prove the cause of the artifact. Candidates: the original procedural pipa_scene.comp (the grain function and bit-HUD), the native blit/viewport, surface preTransform and/or compositor.

## New controlled experiments

The prior pipa_scene.comp and all legacy tests are intentionally left intact. Add pipa_scene_diagnostic.comp with the exact same Vulkan ABI: one rgba8 storage image at binding=0, ivec2 dimensions + int frameIndex + int reserved push constants, 16x16 compute workgroup. Unlike the old texture, it contains no noise and no animated HUD bitfields.

It generates four solid quadrants with a 80-pixel grid, 70x70 red/green/blue/yellow corner tags (texture-space top-left, top-right, bottom-left, bottom-right), a cyan 96x100 rectangle and a magenta 14x460 bar moving +2 pixels per source frame. All pixels are written in bounds with opaque alpha.

Two more controls are available on PresenterActivity:
1. DIAG sólido HOLD 72->144: GPU-native diagnostic frame generation, each original presented twice, without running interpolation (real=120, generated=0, repeated=120).
2. DIAG sólido FrameGen 72->144: same diagnostic shader but calls the unchanged SPARSE+TILED interpolation for odd presentations (real=120, generated=120, repeated=0).

The output string additionally reports actual Vulkan swapchain preTransform enum, swap format enum, and whether native blit was required. This may help interpret orientation of the diagnostic corner markers (surface rotation and physical orientation differ).

### Classification rules
- Original PROCEDURAL HOLD shows stripes; DIAG sólido HOLD clean: stripe is attributable to the old procedural pattern and/or its sampling, not to FrameGen.
- Both HOLD modes show stripe: image presentation/blit/transform or other source-independent pipeline is implicated; investigate Vulkan format transforms, image layouts, and image-copy boundaries.
- DIAG sólido HOLD clean, DIAG sólido FG stripes: Motion/Warp introduces an artifact even with solid geometry; inspect tile boundaries, occlusion/edge clamping, confidence mask.
- Both DIAG modes clean: proceed to natural 3D scenes, time-resolved quality metrics and latency; do not claim universal compatibility.

Capture screenshots separately for both DIAG modes and compare top-left/top-right and bottom-left/bottom-right colored tags against actual device display. The synthetic corner tag mapping may be flipped by configured Android/surface transforms.

No kernel/driver flash, no intervention in other games; EXP27, KGSL, Turnip and SurfaceFlinger remain unchanged. FLASH_READY=false.
