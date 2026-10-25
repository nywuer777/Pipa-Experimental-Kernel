#!/usr/bin/env python3
"""EXP29.6 timestamp source-level invariants (hardware timings need device tests)."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
lab=(root/"lab-app/app/src/main/cpp/lab.cpp").read_text()
engine=(root/"src/pipa_framegen_vk.cpp").read_text()
header=(root/"include/pipa_framegen_vk.h").read_text()
java=(root/"lab-app/app/src/main/java/dev/pipa/framegen/lab/MainActivity.java").read_text()
gradle=(root/"lab-app/app/build.gradle").read_text()

for token in ("jbyteArray motionShader,jbyteArray interpolateShader,jint repetitions",
              "repetitions==1 || repetitions==9 || repetitions==33",
              "const uint32_t timedSamples=uint32_t(repetitions==1 ? 1 : repetitions-1)",
              "timestampBits=props[i].timestampValidBits",
              "props.limits.timestampPeriod",
              "VkQueryPool timestampQueries",
              "vkCmdResetQueryPool(",
              "qi.queryCount=timedSamples*3u",
              "VK_QUERY_RESULT_64_BIT|VK_QUERY_RESULT_WAIT_BIT",
              "vkGetQueryPoolResults(",
              "vkDestroyQueryPool(",
              "if(sample>0)",
              "between.srcAccessMask=VK_ACCESS_SHADER_READ_BIT|VK_ACCESS_SHADER_WRITE_BIT",
              "between.dstAccessMask=VK_ACCESS_SHADER_READ_BIT|VK_ACCESS_SHADER_WRITE_BIT",
              "const bool measure=repetitions==1 || sample>0",
              "const uint64_t mask=lab.timestampBits>=64 ? UINT64_MAX",
              "pipa_framegen_vk_record_profiled(",
              "std::sort(numbers.begin(),numbers.end())"):
    assert token in lab,token
for token in ("pipa_framegen_vk_record_profiled(",
              "vkCmdWriteTimestamp(",
              "firstQuery+1u", "firstQuery+2u",
              "VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT"):
    assert token in engine,token
assert "pipa_framegen_vk_record_profiled(" in header
for token in ("runTest(1,false,256,128)",
              "runTest(33,false,256,128)",
              "runTest(33,true,256,128)",
              "runTest(9,true,640,360)",
              "pipa_motion_fast.comp.spv",
              "enableControls(false)",
              "EXP29.6"):
    assert token in java,token
assert "versionCode 296" in gradle
assert "versionName '29.6-lab'" in gradle
print("EXP29_6_SPLIT_GPU_TIMESTAMPS_AND_FAST_BENCH_CONTRACT=PASS")
