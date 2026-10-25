# EXP29.28 — Identity transform A/B on Adreno 650

Evidence: four user-provided Xiaomi Pad 6 screenshots captured at 18:33–18:34, with battery at 7–8%. The layer is active in all captures.

## Results

| Profile | IDENTITY | Reported presentation result | Visual output | Other observations |
|---|---:|---|---|---|
| HOLD control | On | 1,440 top-level and per-swapchain VK_SUBOPTIMAL_KHR; 0 errors | Preserves the validated scene geometry | 0 CPU late starts; WSI long intervals 1/741 |
| HOLD control | Off | 1,440 VK_SUCCESS; 0 VK_SUBOPTIMAL_KHR; 0 errors | Captured output is visibly flattened | 0 CPU late starts; WSI long intervals 0/663 |
| Pair-budget FrameGen | On | 1,440 top-level and per-swapchain VK_SUBOPTIMAL_KHR; 0 mismatches; 0 errors | Preserves the validated scene geometry | 719 interpolated, 1 repeated; 6/719 pairs above budget; 1 trip and 1 HOLD; 763/1,440 CPU late starts; WSI long intervals 1/363 |
| Pair-budget FrameGen | Off | 1,440 VK_SUCCESS; 0 VK_SUBOPTIMAL_KHR; 0 errors | Captured output is visibly flattened | 719 interpolated, 1 repeated; 4/719 pairs above budget; 1 trip and 1 HOLD; 180/1,440 CPU late starts; WSI long intervals 2/363 |

For IDENTITY-on, the diagnostic query succeeded and reported current surface extent 2844x646, current transform 2, and selected preTransform 1. The top-level and per-swapchain results matched on every call. For the unambiguous IDENTITY-off FrameGen capture, preTransform was 2 and currentTransform was 2.

## Decision

The transform choice controls the status: IDENTITY-on preserves the validated output but consistently produces VK_SUBOPTIMAL_KHR; the current-transform path returns VK_SUCCESS but visibly flattens the scene. Keep IDENTITY enabled for the validated geometry. Do not select the current-transform path solely to clear the status.

The pair governor behaves similarly in both FrameGen captures: 719 of 720 synthetic slots are generated and one slot is held. The large difference in CPU late-start counts (763 versus 180) is not reflected in the WSI long-interval counts or reported cadence. The device was at 7–8% battery during both runs, so treat that CPU difference as confounded and repeat the A/B after charging, with the same scene, settings, and run order reversed.

VK_SUBOPTIMAL_KHR indicates presentation still occurred while the swapchain was not optimally configured for its surface. It is not an error here: all 1,440 calls were accounted for, and the trace layer reported zero errors. The captured WSI cadence is driver-reported and does not prove physical scanout or displayed FPS.

The screenshot heading remains EXP29.25; it is stale experiment text. No UI geometry or kernel state was changed.
