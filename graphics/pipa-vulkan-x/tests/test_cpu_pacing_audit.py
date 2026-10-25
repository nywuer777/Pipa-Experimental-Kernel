#!/usr/bin/env python3
"""EXP29.19: CPU scheduling attribution and WSI-aligned comparator; no device results."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
cpp=(root/"lab-app/app/src/main/cpp/presenter.cpp").read_text()
ui=(root/"lab-app/app/src/main/java/dev/pipa/framegen/lab/PresenterActivity.java").read_text()
gradle=(root/"lab-app/app/build.gradle").read_text()
for token in (
    "bool alignWithDisplay",
    "refreshAligned=alignWithDisplay && targetHz==144 &&",
    "refreshPeriodNs>nominalNs*97u/100u",
    "refreshPeriodNs<nominalNs*103u/100u",
    "selectedPacingPeriodNs=refreshAligned?refreshPeriodNs:nominalNs;",
    "const bool inheritedLate=beforeSleep>deadline+interval;",
    "if(inheritedLate)++inheritedLateOnePeriod;",
    "if(!inheritedLate)++timerOversleepOnePeriod;",
    "lateBurstLongest=std::max(lateBurstLongest,lateBurstCurrent);",
    "fenceWaitMs.push_back(",
    "acquireWaitMs.push_back(",
    "submitCallMs.push_back(",
    "wakeLateMs.push_back(",
    "CPU pacing=",
    "CPU wake lateness",
    "CPU fence wait",
    "CPU acquire wait",
    "CPU submit call",
    "atraso herdado antes sleep=",
    "atraso novo apos sleep=",
    "maior sequencia atrasada=",
    "p.run(targetHz,frames,continuous,holdInsteadOfFG,",
    "jboolean holdInsteadOfFGMode,jboolean alignWithDisplayMode",
    "p.gpuTimingSummary()+p.cpuPacingSummary()+p.timingSummary()",
    "VK_GOOGLE_display_timing",
    "const bool synthesized=odd && !holdInsteadOfFG;",
): assert token in cpp,token
for token in (
    "private CheckBox syncDisplay, fastMotion, identity3d;",
    "syncDisplay.setChecked(false)",
    "final boolean alignWithDisplay=syncDisplay.isChecked();",
    "stressHold144.setOnClickListener(",
    "stressFg144.setOnClickListener(",
    "continuous,holdInsteadOfFG,alignWithDisplay,motionRadius,",
    "copyReport.setOnClickListener(v->",
    "ClipboardManager clipboard=",
): assert token in ui,token
assert ui.index("final boolean alignWithDisplay=syncDisplay.isChecked();") < ui.index('status.setText("MOTION raio="+motionRadius+')
assert "versionCode 313" in gradle and "29.23-lab" in gradle

# Deterministic demonstration: fixed 1/144 sec diverges over 10 seconds
# from WSI cycle of 6.9608ms as reported by the Xiaomi Pad 6.
fixed=1_000_000_000//144
reported=6_960_832
assert abs(reported-fixed)/fixed<0.03
drift=(reported-fixed)*1440/1e6
assert drift>20,drift
assert (reported*1440/1e9)>(fixed*1440/1e9)
# No physical missed-presentation claim is made by these purely CPU timers.
print(f"EXP29_19_PACING_CONTRACT=PASS; FIXED_vs_WSI_10S_DRIFT_MS={drift:.3f}; DEVICE_STRESS=UNTESTED")
