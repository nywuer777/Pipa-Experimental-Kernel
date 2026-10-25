#!/usr/bin/env python3
"""Source-level EXP29.5 invariants, separate from NDK compile and GPU hardware evidence."""
from pathlib import Path
p=Path(__file__).resolve().parents[1]
native=(p/"lab-app/app/src/main/cpp/lab.cpp").read_text()
java=(p/"lab-app/app/src/main/java/dev/pipa/framegen/lab/MainActivity.java").read_text()
gradle=(p/"lab-app/app/build.gradle").read_text()

for token in ("jbyteArray motionShader,jbyteArray interpolateShader,jint repetitions",
              "repetitions==1 || repetitions==33",
              "const uint32_t timedSamples=repetitions==33 ? 32u : 1u",
              "timestampBits=props[i].timestampValidBits",
              "props.limits.timestampPeriod",
              "VkQueryPool timestampQueries",
              "vkCmdResetQueryPool(",
              "vkCmdWriteTimestamp(",
              "VK_QUERY_RESULT_64_BIT|VK_QUERY_RESULT_WAIT_BIT",
              "vkGetQueryPoolResults(",
              "vkDestroyQueryPool(",
              "if(sample>0)",
              "VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT",
              "between.srcAccessMask=VK_ACCESS_SHADER_READ_BIT|VK_ACCESS_SHADER_WRITE_BIT",
              "between.dstAccessMask=VK_ACCESS_SHADER_READ_BIT|VK_ACCESS_SHADER_WRITE_BIT",
              "const bool measure=repetitions==1 || sample>0",
              "const uint64_t mask=lab.timestampBits>=64 ? UINT64_MAX",
              "std::sort(milliseconds.begin(),milliseconds.end())"):
    assert token in native,token
for token in ("runTest(1)","runTest(33)","benchmark.setEnabled(false)",
              "benchmark.setEnabled(true)","int repetitions",
              "GPU: timestamps Vulkan", 'EXP29.5'):
    assert token in java,token
assert "versionCode 295" in gradle
assert "versionName '29.5-lab'" in gradle
print("EXP29_5_TIMESTAMP_CONTRACT=PASS; DEVICE_TIMING=NOT_YET_VERIFIED")
