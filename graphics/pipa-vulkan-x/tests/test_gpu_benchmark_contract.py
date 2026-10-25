#!/usr/bin/env python3
"""EXP29.11 source contract. Native/SPIR-V/on-device tests are separate."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
lab = (root / "lab-app/app/src/main/cpp/lab.cpp").read_text()
engine = (root / "src/pipa_framegen_vk.cpp").read_text()
header = (root / "include/pipa_framegen_vk.h").read_text()
java = (root / "lab-app/app/src/main/java/dev/pipa/framegen/lab/MainActivity.java").read_text()
gradle = (root / "lab-app/app/build.gradle").read_text()
shader = (root / "shaders/pipa_motion_parallel.comp").read_text()
sparse = (root / "shaders/pipa_motion_sparse.comp").read_text()
for token in (
    "jbyteArray motionShader,jbyteArray interpolateShader,jint repetitions,jint motionVariant",
    "motionVariant==2",
    "motionVariant>=0 && motionVariant<=4",
    "motionVariant==2 || motionVariant==3 || motionVariant==4",
    "PIPA_FRAMEGEN_VK_WARP_16X16",
    "PIPA_FRAMEGEN_VK_MOTION_GROUP_PER_TILE",
    "pipa_framegen_vk_create_ex(",
    "pipa_framegen_vk_record_profiled(",
    "qi.queryCount=timedSamples*3u",
    "vkGetQueryPoolResults(",
    "vkDestroyQueryPool(",
    "timestampBits=props[i].timestampValidBits",
    "VK_QUERY_RESULT_64_BIT|VK_QUERY_RESULT_WAIT_BIT",
    "if(sample>0)",
    "jboolean tiledWarp",
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
    "vkCmdDispatch(cmd,(width+15)/16,(height+15)/16,1);",
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
    "runTest(9,3,640,360)",
    "runTest(9,2,1280,720)",
    "runTest(9,3,1280,720)",
    "pipa_motion_parallel.comp.spv",
    "pipa_motion_sparse.comp.spv",
    "enableControls(false)",
    "EXP29.11",
    "runTest(9,4,1280,720,true,false)",
    "runTest(9,3,640,360,true,true)",
    "runTest(9,3,1280,720,true,true)",
    "runTest(9,4,1280,720,true,true)",
    "pipa_interpolate_tiled.comp.spv",
    "pipa_motion_sparse32.comp.spv",
    "pipa_interpolate_adaptive.comp.spv",
    "runTest(9,3,640,360,true)",
    "runTest(9,3,1280,720,true)",
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
assert "shared vec3 previousSample[16]" in sparse
assert "const int STEP=4;" in sparse
assert "if(lane<16u)" in sparse
assert "versionCode 302" in gradle
assert "versionName '29.12-lab'" in gradle
print("EXP29_11_TILED_WARP_CONTRACT=PASS; DEVICE_TIMING=UNTESTED")
