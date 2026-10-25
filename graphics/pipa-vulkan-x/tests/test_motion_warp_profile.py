#!/usr/bin/env python3
"""EXP29.20 native GPU motion/warp split and explicit radius A/B contract."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
cpp=(root/"lab-app/app/src/main/cpp/presenter.cpp").read_text()
java=(root/"lab-app/app/src/main/java/dev/pipa/framegen/lab/PresenterActivity.java").read_text()
engine=(root/"src/pipa_framegen_vk.cpp").read_text()
gradle=(root/"lab-app/app/build.gradle").read_text()
for token in (
    "queryInfo.queryCount=5;",
    "vkCmdResetQueryPool(command,gpuQueryPool,0,5);",
    "vkCmdWriteTimestamp(command,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,",
    "vkCmdWriteTimestamp(command,VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,",
    "pipa_framegen_vk_record_profiled(engine,command,&images,kWidth,kHeight,",
    "0.5f,uint32_t(motionRadius),0.75f,gpuQueryPool,2",
    "pipa_framegen_vk_record(engine,command,&images,kWidth,kHeight,",
    "vkGetQueryPoolResults(device,gpuQueryPool,2,3,",
    "const uint64_t motionTicks=(parts[1]-parts[0])&mask;",
    "const uint64_t warpTicks=(parts[2]-parts[1])&mask;",
    "motionGpuMs.push_back(motionMs);",
    "warpGpuMs.push_back(warpMs);",
    "GPU Motion", "GPU Warp+barreira",
    "Motion raio=",
    "expect(motionRadius==3 || motionRadius==4",
    "jboolean alignWithDisplayMode,jint motionRadius",
    "alignWithDisplayMode==JNI_TRUE,int(motionRadius)",
    "const bool synthesized=odd && !holdInsteadOfFG;",
): assert token in cpp,token
for token in (
    "if(queryPool!=VK_NULL_HANDLE)",
    "firstQuery+1u", "firstQuery+2u",
    "vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,",
): assert token in engine,token
for token in (
    "private CheckBox syncDisplay, fastMotion;",
    "fastMotion.setChecked(false);",
    "fastMotion.isChecked()?3:4;",
    "continuous,holdInsteadOfFG,alignWithDisplay,motionRadius,scene3d);",
    "copyReport.setOnClickListener(v->",
    "stressFg144.setOnClickListener(",
): assert token in java,token
assert "versionCode 312" in gradle and "29.22-lab" in gradle
assert cpp.count('VkQueryPool gpuQueryPool=VK_NULL_HANDLE')==1
assert "queryInfo.queryCount=2;" not in cpp
print("EXP29_20_SPLIT_MOTION_WARP_RADIUS3_VS4=PASS; DEVICE_BENCHMARK_PENDING")
