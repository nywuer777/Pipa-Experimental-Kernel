# EXP29.29 — GPU Guard on real FrameGen workload

## Hardware evidence

Captures 31740 and 31741 used the Xiaomi Pad 6 (Adreno 650), **3D 10s FrameGen 72→144**, **SYNC experimental** off, **Motion FAST experimental** on at radius 3, and **3D IDENTITY WSI** on. The GPU Guard was the only changed option.

- Guard on (31740): 719 interpolated, 1 repeated; 4/719 measured pairs over the 11.805555 ms ceiling; 1,109 CPU starts over one period; 2/363 sampled WSI intervals over 1.5 cycles.
- Guard off (31741): 720 interpolated, 0 repeated; 0/1,440 CPU starts over one period; 1/424 sampled WSI intervals over 1.5 cycles.
- Reported WSI cadence was 142.952 Hz and 143.431 Hz respectively. The sampling windows differ, so one pair is evidence for follow-up, not proof of causation.

## Source finding

presenter.cpp added four diagnostic scene recomputes whenever the GPU Guard was enabled. The added work ran even in **3D 10s FrameGen 72→144**, so the Guard comparison changed both the guard and the GPU workload. That made the 31740 CPU lateness result unsuitable for judging the Guard on the normal scene.

## EXP29.29 change

- The standard 3D FrameGen path now measures the actual real-plus-generated pair without adding four hidden scene passes.
- The stress-pass count is carried explicitly into the native presenter and reported as passes stress cena=0 for the standard 3D test.
- The optional stress-pass mechanism remains gated by an explicit stress-mode argument.
- The visible controls, scene geometry, Vulkan identity transform, and swapchain behavior are unchanged.
- Android version is 29.29-real-load-gpu-guard (versionCode 319).

## Device validation

Install this APK and run **3D 10s FrameGen 72→144** with **GPU GUARD PAR 85%: HOLD após 3 pares GPU acima do teto** enabled, keeping **SYNC experimental** off and the other two checkboxes as in 31740. Confirm the report shows passes stress cena=0, then compare generated/repeated counts, CPU late starts, pair GPU timings, and WSI intervals with the guard unchecked. Repeat in reverse order. This is an app-only experiment; it does not modify or flash the kernel.