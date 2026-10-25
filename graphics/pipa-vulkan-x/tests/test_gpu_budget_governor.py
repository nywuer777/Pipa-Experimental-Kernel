#!/usr/bin/env python3
"""EXP29.25: completed GPU pair budget, three-strike fallback, no frame inflation."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
native=(root/"lab-app/app/src/main/cpp/presenter.cpp").read_text()
ui=(root/"lab-app/app/src/main/java/dev/pipa/framegen/lab/PresenterActivity.java").read_text()
gradle=(root/"lab-app/app/build.gradle").read_text()
for tok in (
    "bool gpuBudgetRequested=false, gpuBudgetEnabled=false;",
    "gpuBudgetEnabled=enableGpuBudget && continuous && !holdInsteadOfFG &&",
    "gpuQueryPool!=VK_NULL_HANDLE;",
    "gpuBudgetMs=2.0*double(selectedPacingPeriodNs)*0.85e-6;",
    "pendingPairRealGpuMs=ms;",
    "pendingPairRealAvailable=true;",
    "if(!sampleValid || !pendingPairRealAvailable)",
    "pendingPairRealAvailable=false;",
    "const double pairMs=pendingPairRealGpuMs+ms;",
    "gpuPairMs.push_back(pairMs);",
    "++gpuBudgetProbeFrames;",
    "if(pairMs>gpuBudgetMs) {",
    "++gpuBudgetOverruns;",
    "++gpuBudgetOverrunStreak;",
    "if(gpuBudgetOverrunStreak>=3u) {",
    "gpuBudgetHoldCountdown=1u;",
    "++gpuBudgetGovernorTrips;",
    "gpuBudgetOverrunStreak=0u;",
    "gpuBudgetOverrunStreak=0u;",
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
    '" probes pares="',
    '" trips 3x="',
    'summary(gpuPairMs,"GPU par real+FG")',
    "p.gpuTimingSummary()+p.cpuPacingSummary()+p.timingSummary()",
): assert tok in native,tok
for tok in (
    "private CheckBox syncDisplay, fastMotion, identity3d, gpuBudgetGuard;",
    "gpuBudgetGuard.setChecked(false);",
    "gpuBudgetGuard.isChecked();",
    "boolean gpuBudgetGuard);",
    "scene3d,preferIdentity3d,adaptiveGuard);",
    "scene3d && continuous && !holdInsteadOfFG &&",
    "GPU GUARD PAR 85%",
    "scene3dHold.setOnClickListener(",
    "scene3dFg.setOnClickListener(",
): assert tok in ui,tok
assert "realGpuMs.back()+ms" not in native
assert "versionCode 315" in gradle and "29.25-lab" in gradle

# Pure deterministic policy model (not Android device timing).
def control(pair_costs, limit=11.83):
    streak=0
    cooldown=0
    result=[]
    sampled=0
    for i in range(len(pair_costs)):
        result.append("real")
        if cooldown:
            result.append("hold")
            cooldown-=1
            continue
        result.append("fg")
        pair_ms=pair_costs[sampled]
        sampled+=1
        if pair_ms>limit:
            streak+=1
            if streak>=3:
                cooldown=1
                streak=0
        else:
            streak=0
    return result
no_overload=control([7.1]*10)
assert no_overload.count("fg")==10 and no_overload.count("hold")==0
overload=control([12.5]*10)
assert overload[:8]==["real","fg","real","fg","real","fg","real","hold"]
assert overload.count("hold")==2 and overload.count("fg")==8
assert overload.count("real")==10
print("EXP29_25_TWO_PERIOD_GPU_GOVERNOR_SOURCE=PASS; HARDWARE_AB_PENDING")
