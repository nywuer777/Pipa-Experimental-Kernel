#!/usr/bin/env python3
"""EXP29.13 - Vulkan WSI presentation-time instrumentation (source contract).
Does not replace hardware timestamp verification.
"""
from pathlib import Path
p=Path(__file__).resolve().parents[1]
cpp=(p/"lab-app/app/src/main/cpp/presenter.cpp").read_text()
java=(p/"lab-app/app/src/main/java/dev/pipa/framegen/lab/PresenterActivity.java").read_text()
gradle=(p/"lab-app/app/build.gradle").read_text()
for token in (
    "vkEnumerateDeviceExtensionProperties(",
    "VK_GOOGLE_DISPLAY_TIMING_EXTENSION_NAME",
    "displayTimingEnabled=true;",
    "getPastTiming=reinterpret_cast<PFN_vkGetPastPresentationTimingGOOGLE>",
    'vkGetDeviceProcAddr(device,"vkGetPastPresentationTimingGOOGLE")',
    "VK_STRUCTURE_TYPE_PRESENT_TIMES_INFO_GOOGLE",
    "presentStamp.presentID=uint32_t(frame+1)",
    "presentStamp.desiredPresentTime=0",
    "present.pNext=&presentTiming",
    "getPastTiming(device,swap,&count,nullptr)",
    "reportedActualNs[records[i].presentID]=records[i].actualPresentTime",
    "pair.first==previousId+1u",
    "intervals.size()*95u+99u",
    "collectTiming();",
    "VK_GOOGLE_display_timing indisponivel",
    "NAO sao FPS fisicos",
):
    assert token in cpp,token
assert "if(displayTimingEnabled)" in cpp
assert "std::map<uint32_t,uint64_t> reportedActualNs" in cpp
assert "VK_PRESENT_MODE_FIFO_KHR" in cpp
assert "std::to_string(reportedActualNs.size())" in cpp
assert "getDisplay().getRefreshRate()" in java
assert "dp(48)" in java
assert "versionCode 314" in gradle
assert "versionName '29.24-lab'" in gradle
print("EXP29_13_DISPLAY_TIMING_SOURCE_CONTRACT=PASS; ADRENO_EXTENSION_AVAILABILITY=UNTESTED")
