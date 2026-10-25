#!/usr/bin/env python3
"""EXP29.7 source contract. Native/SPIR-V/on-device tests are separate."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
lab = (root / "lab-app/app/src/main/cpp/lab.cpp").read_text()
engine = (root / "src/pipa_framegen_vk.cpp").read_text()
header = (root / "include/pipa_framegen_vk.h").read_text()
java = (root / "lab-app/app/src/main/java/dev/pipa/framegen/lab/MainActivity.java").read_text()
gradle = (root / "lab-app/app/build.gradle").read_text()
shader = (root / "shaders/pipa_motion_parallel.comp").read_text()
for token in (
    "jbyteArray motionShader,jbyteArray interpolateShader,jint repetitions,jint motionVariant",
    "motionVariant==2",
    "PIPA_FRAMEGEN_VK_MOTION_GROUP_PER_TILE",
    "pipa_framegen_vk_create_ex(",
    "pipa_framegen_vk_record_profiled(",
    "qi.queryCount=timedSamples*3u",
    "vkGetQueryPoolResults(",
    "vkDestroyQueryPool(",
    "timestampBits=props[i].timestampValidBits",
    "VK_QUERY_RESULT_64_BIT|VK_QUERY_RESULT_WAIT_BIT",
    "if(sample>0)",
):
    assert token in lab, token
for token in (
    "pipa_framegen_vk_create_ex(",
    "pipa_framegen_vk_create(",
    "PIPA_FRAMEGEN_VK_MOTION_GROUP_PER_TILE",
    "vkCmdDispatch(cmd,tx,ty,1);",
    "vkCmdDispatch(cmd,(tx+7)/8,(ty+7)/8,1);",
    "pipa_framegen_vk_record_profiled(",
    "vkCmdWriteTimestamp(",
):
    assert token in engine, token
assert "PIPA_FRAMEGEN_VK_MOTION_GROUP_PER_TILE" in header
for token in (
    "runTest(1,0,256,128)",
    "runTest(33,0,256,128)",
    "runTest(33,1,256,128)",
    "runTest(9,1,640,360)",
    "runTest(33,2,256,128)",
    "runTest(9,2,640,360)",
    "pipa_motion_parallel.comp.spv",
    "enableControls(false)",
    "EXP29.7",
):
    assert token in java, token
for token in (
    "gl_WorkGroupID.xy",
    "gl_LocalInvocationIndex",
    "shared vec3 previousSample[64]",
    "barrier();",
    "candidateError(",
):
    assert token in shader, token
assert "versionCode 297" in gradle
assert "versionName '29.7-lab'" in gradle
print("EXP29_7_PARALLEL_VULKAN_CONTRACT=PASS; DEVICE_TIMING=UNTESTED")
