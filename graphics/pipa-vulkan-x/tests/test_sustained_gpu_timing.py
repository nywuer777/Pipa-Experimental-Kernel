#!/usr/bin/env python3
"""EXP29.18: sustained WSI and GPU timing source contract.
This is not an on-device performance result.
"""
from pathlib import Path
p=Path(__file__).resolve().parents[1]
cpp=(p/"lab-app/app/src/main/cpp/presenter.cpp").read_text()
ui=(p/"lab-app/app/src/main/java/dev/pipa/framegen/lab/PresenterActivity.java").read_text()
gradle=(p/"lab-app/app/build.gradle").read_text()
for token in (
    "VkQueryPool gpuQueryPool=VK_NULL_HANDLE;",
    "vkGetPhysicalDeviceQueueFamilyProperties(physical,&selectedFamilyCount",
    "selectedFamilies[family].timestampValidBits;",
    "timestampPeriodNs=gpuProps.limits.timestampPeriod;",
    "vkCreateQueryPool(device,&queryInfo,nullptr,&gpuQueryPool)",
    "vkDestroyQueryPool(device,gpuQueryPool,nullptr)",
    "vkCmdResetQueryPool(command,gpuQueryPool,0,2);",
    "vkCmdWriteTimestamp(command,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,",
    "vkCmdWriteTimestamp(command,VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,",
    "harvestGpuTimestamps();",
    "vkGetQueryPoolResults(device,gpuQueryPool,0,2,sizeof(values)",
    "VK_QUERY_RESULT_64_BIT",
    "if(timestampValidBits<64)",
    "realGpuMs.push_back(ms);",
    "generatedGpuMs.push_back(ms);",
    "GPU original+blit", "GPU gerado+blit",
    "cobertura WSI=", "intervalos >1.5 ciclos=",
    "p50=", "p95=", "p99=", "max=",
    "CPU vkQueuePresentKHR p95=",
    'frames<=2400,"Invalid frame count"',
    "NAO sao FPS fisicos exibidos",
    "const bool synthesized=odd && !holdInsteadOfFG;",
):
    assert token in cpp,token
for token in (
    "stressHold144=button(", "stressFg144=button(",
    "stressHold144.setOnClickListener(v->start(144,true,true,false,true,true));",
    "stressFg144.setOnClickListener(v->start(144,true,false,false,true,true));",
    "result=nativePresent(surface,motion,warp,scene,hz,stress?1440:240,",
    '"pipa_scene_v2.comp.spv"',
): assert token in ui,token
assert "versionCode 308" in gradle
assert "versionName '29.18-lab'" in gradle

for frames in (240,1440):
    real=sum(i%2==0 for i in range(frames))
    assert real==frames//2
    assert (frames-real)==frames//2
assert "FLASH_READY=true" not in cpp
print("EXP29_18_SUSTAINED_WSI_GPU_TIMING_SOURCE_CONTRACT=PASS; DEVICE_BENCHMARK_PENDING")
