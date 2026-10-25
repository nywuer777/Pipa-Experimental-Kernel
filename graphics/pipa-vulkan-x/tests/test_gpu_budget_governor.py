#!/usr/bin/env python3
"""EXP29.24: opt-in timestamp-based FrameGen GPU budget governor."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
native=(root/"lab-app/app/src/main/cpp/presenter.cpp").read_text()
ui=(root/"lab-app/app/src/main/java/dev/pipa/framegen/lab/PresenterActivity.java").read_text()
gradle=(root/"lab-app/app/build.gradle").read_text()
for tok in (
    "bool gpuBudgetRequested=false, gpuBudgetEnabled=false;",
    "gpuBudgetEnabled=enableGpuBudget && continuous && !holdInsteadOfFG &&",
    "gpuQueryPool!=VK_NULL_HANDLE;",
    "gpuBudgetMs=double(selectedPacingPeriodNs)*0.85e-6;",
    "if(gpuBudgetEnabled) {",
    "++gpuBudgetProbeFrames;",
    "if(ms>gpuBudgetMs) {",
    "++gpuBudgetOverruns;",
    "gpuBudgetHoldCountdown=2u;",
    "const bool budgetFallback=odd && gpuBudgetEnabled &&",
    "gpuBudgetHoldCountdown>0;",
    "--gpuBudgetHoldCountdown;",
    "++gpuBudgetHeld;",
    "const bool synthesized=odd && !holdInsteadOfFG && !budgetFallback;",
    "if(odd && (holdInsteadOfFG || budgetFallback))++sceneHeldSubmitted;",
    "jboolean gpuBudgetMode",
    "gpuBudgetMode==JNI_TRUE",
    '" | GPU BUDGET solicitado="',
    '" HOLD adaptativos="',
    '" probes FG="',
    "p.gpuTimingSummary()+p.cpuPacingSummary()+p.timingSummary()",
): assert tok in native,tok
for tok in (
    "private CheckBox syncDisplay, fastMotion, identity3d, gpuBudgetGuard;",
    "gpuBudgetGuard.setChecked(false);",
    "gpuBudgetGuard.isChecked();",
    "boolean gpuBudgetGuard);",
    "scene3d,preferIdentity3d,adaptiveGuard);",
    "scene3d && continuous && !holdInsteadOfFG &&",
    "GPU GUARD 85%",
    "scene3dHold.setOnClickListener(",
    "scene3dFg.setOnClickListener(",
): assert tok in ui,tok
assert "versionCode 314" in gradle and "29.24-lab" in gradle

# Pure behavioral model: over-budget probe triggers exactly two HOLD slots,
# then returns to a generated probe. A low-cost probe keeps FG active.
def control(measured_times, limit=5.90):
    cooldown=0; active=[]; idx=0
    for frame in range(12):
        if frame%2==0: active.append("real"); continue
        if cooldown:
            active.append("hold");cooldown-=1;continue
        active.append("fg")
        ms=measured_times[idx];idx+=1
        if ms>limit:cooldown=2
    return active
assert control([6.1,5.7,5.4])==[
 "real","fg","real","hold","real","hold","real","fg",
 "real","fg","real","fg"
]
# No generated frame is mislabeled as HOLD and real frame cadence remains intact.
print("EXP29_24_GPU_BUDGET_GOVERNOR_SOURCE=PASS; HARDWARE_AB_PENDING")
