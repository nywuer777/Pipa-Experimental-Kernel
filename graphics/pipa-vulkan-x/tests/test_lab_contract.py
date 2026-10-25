#!/usr/bin/env python3
"""EXP29.4 source contract preflight. Not a substitute for NDK/SPIR-V/device testing."""
from pathlib import Path

project=Path(__file__).resolve().parents[1]
app=project/"lab-app"
java=(app/"app/src/main/java/dev/pipa/framegen/lab/MainActivity.java").read_text()
native=(app/"app/src/main/cpp/lab.cpp").read_text()
cmake=(app/"app/src/main/cpp/CMakeLists.txt").read_text()
manifest=(app/"app/src/main/AndroidManifest.xml").read_text()
gradle=(app/"app/build.gradle").read_text()
for entry in ("nativeGenerate","nativeReport"):
    assert f"private native " in java
    assert f"Java_dev_pipa_framegen_lab_MainActivity_{entry}" in native,entry
for shader in ("pipa_motion.comp.spv","pipa_interpolate.comp.spv"):
    assert shader in java
for token in ("pipa_framegen_vk_create_ex(", "pipa_framegen_vk_record_profiled(",
              "vkCmdCopyBufferToImage(", "vkCmdCopyImageToBuffer(",
              "VK_PIPELINE_STAGE_HOST_BIT", "vkQueueSubmit(",
              "vkWaitForFences(", "vkMapMemory("):
    assert token in native,token
assert 'pipa_framegen_vk.cpp' in cmake
assert 'android.hardware.vulkan.level' in manifest
assert "abiFilters 'arm64-v8a'" in gradle
assert 'targetSdk 34' in gradle
print("EXP29_4_JAVA_NATIVE_BUILD_CONTRACT=PASS")
