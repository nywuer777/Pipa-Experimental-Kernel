# EXP29.27 — Adreno 650 hardware results

Device: Xiaomi Pad 6, Adreno 650, Android-reported 144 Hz. Evidence: two user-provided screenshots from the lab app.

## Pair-budget FrameGen run

- Present calls: 1,440; 720 real, 719 interpolated, 1 repeated.
- Pair budget: 11.827889 ms; 719 completed pairs, 5 above threshold, 1 three-strike trip, 1 adaptive HOLD, 0 unavailable pairs.
- Measured real+interpolated GPU pair: mean 9.516561 ms, p95 9.925104 ms; last pair 9.431146 ms.
- CPU starts more than one pacing period late: 2/1,440; both were inherited before sleep, with 0 new late periods after sleep.
- WSI intervals above 1.5 cycles: 2/362; reported cadence 142.965549 Hz.
- Explicit trace layer: available=1, active=1, 1,440 present calls, 0 VK_SUCCESS, 1,440 VK_SUBOPTIMAL_KHR, 0 errors.
- Controlled scene repeat passes: 4. Motion profile: FAST radius 3. Identity transform was requested and accepted.

## HOLD control

- Present calls: 1,440; 720 real, 0 interpolated, 720 repeated.
- CPU starts more than one pacing period late: 0/1,440.
- WSI intervals above 1.5 cycles: 0/545; reported cadence 143.724748 Hz.
- Explicit trace layer: available=1, active=1, 1,440 present calls, 0 VK_SUCCESS, 1,440 VK_SUBOPTIMAL_KHR, 0 errors.

## Interpretation

The paired budget now preserves 719 of 720 generated slots in the captured run, with only one adaptive HOLD. This is a substantial improvement over EXP29.24's single-cycle guard result (240 interpolated and 480 repeated in its reported comparison). The pair measurement averaged below the configured 11.827889 ms ceiling. The two screenshots are not a controlled normal-FrameGen-versus-HOLD A/B: the first enables the diagnostic scene load and pair guard; the second is a no-FrameGen HOLD control. Do not infer a causal pacing improvement from their different WSI sample counts.

The layer instrumentation is active and observed every queue-present call. VK_SUBOPTIMAL_KHR is a successful-but-nonoptimal presentation status, not a presentation error. Since it occurred on every call in both runs, the next diagnostic should record the surface capabilities and swapchain configuration at creation and after present, then determine whether a swapchain recreation is appropriate. Keep this diagnostic separate from changes to the validated UI geometry.

The screenshot heading still says EXP29.25 even though the trace layer counters are present. Treat the heading as stale experiment text; it does not establish the installed APK version.

Calls to vkQueuePresentKHR and driver-reported WSI timestamps do not prove physical scanout, displayed FPS, or touch-to-photon latency. No kernel change or flash was part of this experiment.
