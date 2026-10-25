# EXP29.11 — Workgroup tuning (experimental; NO FLASH)

## EXP29.10 verified Xiaomi Pad 6 results (Adreno 650)

Four screenshots from the real Android ARM64 lab, Vulkan Compute offscreen, 1 warm-up + 8 timed pairs, synthetic +2 px shift.

| GPU timing | SPARSE 640x360 | SPARSE+ADAPTIVE 640x360 | SPARSE 1280x720 | SPARSE+ADAPTIVE 1280x720 |
| --- | ---: | ---: | ---: | ---: |
| Motion average | 1.101042 ms | 1.098756 ms | 3.654017 ms | 4.262220 ms |
| Warp+barrier average | 1.870729 ms | 0.951927 ms | 6.062552 ms | 3.956269 ms |
| GPU total average | 2.971771 ms | 2.050684 ms | 9.716569 ms | 8.218489 ms |
| GPU total p95 | 3.012865 ms | 2.089687 ms | 11.849114 ms | 8.272708 ms |
| Synthetic output MAE | 0 | 0 | 0 | 0 |

Total average reduction 31.0% (360p), 15.4% (720p) in these individual tests. Only the simple controlled synthetic translation has been validated. 720p total mean (8.22ms) exceeds 144Hz refresh interval (~6.94ms) **before** game rendering, upload, compositor and presentation. These are not physical display FPS and not FPS doubling.

## New controlled GPU tuning hypotheses

1. `pipa_motion_sparse32.comp` preserves all SPARSE motion candidate evaluation, 16 cached samples per tile and scoring/tie-breaking. It reduces workgroup size from 8x8 (64 threads) to 8x4 (32 threads). There are still at most 25 coarse candidates and 9 refinement candidates, so all candidate indices fit. This may reduce idle lanes/register pressure or may decrease throughput on Adreno.
2. `pipa_interpolate_tiled.comp` retains exact ADAPTIVE bilinear logic, but switches to a **16x16 pixel workgroup** and loads the RGBA16F motion vector once into `shared vec4 tileFlow` for the workgroup, rather than once per output pixel. All invocations reach the workgroup barrier before out-of-bounds edge lanes return. This may reduce image fetches or may be slower from larger workgroups/shared-memory synchronization.
3. **Critical ABI protection:** `PIPA_FRAMEGEN_VK_WARP_16X16` instructs C++ to issue `vkCmdDispatch(ceil(width/16),ceil(height/16),1)` for tiled warp. All old shaders retain the original `ceil(width/8),ceil(height/8)` dispatch. Motion group-per-tile remains enabled for variants 2/3/4. The EXP29.8 under-dispatch regression is guarded by source contracts.
4. Android lab version 29.11 (301) adds combinations at 720p and one 360p tiled comparison; original LEGACY/FAST/PARALLEL/SPARSE and SPARSE+ADAPTIVE benchmarks remain accessible.

## Test order on tablet

- Reference: **SPARSE+ADAPTIVE 1280x720**.
- New motion workgroup: **SPARSE32+ADAPTIVE 720p**. Compare Motion avg/p95 and total, MAE.
- New warp workgroup: **SPARSE+TILED 720p**. Compare Warp avg/p95 and total, MAE.
- Combined: **SPARSE32+TILED 720p**. Repeat in reverse order under similar thermal conditions.
- Sanity test: SPARSE+ADAPTIVE and SPARSE+TILED in **640x360**; compare total p95.

The new shaders are hypotheses. Do **not** claim either is faster before paired Adreno 650 measurements. Reject any profile with synthetic MAE drift or unstable p95; preserve EXP29.10 profile as fallback.

### Verification stages

GitHub Actions `.github/workflows/exp29.11-workgroup-tuning-apk.yml` compiles SPIR-V for Vulkan 1.1, validates descriptor/push-constant ABI, guards dispatch geometry and warp edge synchronization in `tests/test_workgroup_tuning.py`, and builds/signs arm64 APK using pinned NDK r27c/Gradle.

Successful APK compilation does not establish physical GPU performance. The next meaningful milestone remains a **developer-owned Vulkan swapchain/present loop** with controlled captures and per-present metrics; it is **not** part of this offscreen test build.

Kernel EXP27 untouched, no root, no KGSL/Turnip/SurfaceFlinger changes. `FLASH_READY=false`.
