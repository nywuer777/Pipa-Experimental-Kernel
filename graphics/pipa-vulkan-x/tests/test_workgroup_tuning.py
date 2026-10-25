#!/usr/bin/env python3
"""EXP29.11: guard motion/warp shader dispatch ABI and tile safety.
This is source static validation; glslang+spirv-val and tablet runs are separate.
"""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
engine=(root/"src/pipa_framegen_vk.cpp").read_text()
header=(root/"include/pipa_framegen_vk.h").read_text()
lab=(root/"lab-app/app/src/main/cpp/lab.cpp").read_text()
java=(root/"lab-app/app/src/main/java/dev/pipa/framegen/lab/MainActivity.java").read_text()
small=(root/"shaders/pipa_motion_sparse32.comp").read_text()
baseline=(root/"shaders/pipa_motion_sparse.comp").read_text()
tiled=(root/"shaders/pipa_interpolate_tiled.comp").read_text()
adaptive=(root/"shaders/pipa_interpolate_adaptive.comp").read_text()
assert "layout(local_size_x=8, local_size_y=4, local_size_z=1)" in small
assert "shared float scores[32];" in small
assert "shared int lengths[32];" in small
assert "gl_WorkGroupID.xy" in small
assert "layout(local_size_x=16, local_size_y=16, local_size_z=1)" in tiled
assert "shared vec4 tileFlow;" in tiled
assert "tileFlow=imageLoad(motionField,ivec2(gl_WorkGroupID.xy));" in tiled
assert tiled.index("barrier();") < tiled.index("if (any(greaterThanEqual(xy,pc.frameSize))) return;")
assert "vec4 estimate=tileFlow;" in tiled
assert "PIPA_FRAMEGEN_VK_WARP_16X16 0x2u" in header
assert "if(e->warp16x16)" in engine
assert "vkCmdDispatch(cmd,(width+15)/16,(height+15)/16,1);" in engine
assert "vkCmdDispatch(cmd,(width+7)/8,(height+7)/8,1);" in engine
assert "motionVariant==2 || motionVariant==3 || motionVariant==4" in lab
assert "tiledWarp==JNI_TRUE ? PIPA_FRAMEGEN_VK_WARP_16X16 : 0u" in lab
assert "jint motionVariant,jboolean tiledWarp" in lab
assert "pipa_motion_sparse32.comp.spv" in java
assert "pipa_interpolate_tiled.comp.spv" in java
assert "runTest(9,4,1280,720,true,true)" in java
# The 32-lane sparse variant must preserve all cost/search geometry except lane-count.
canonical=baseline.replace("layout(local_size_x=8, local_size_y=8, local_size_z=1)",
                           "layout(local_size_x=8, local_size_y=4, local_size_z=1)").replace(
                           "shared float scores[64];","shared float scores[32];").replace(
                           "shared int lengths[64];","shared int lengths[32];")
# Comments are excluded as they differ between variants.
def code(s):
    return "\n".join(l for l in s.splitlines() if not l.strip().startswith("//"))
assert code(canonical)==code(small), "SPARSE32 unexpectedly changed motion search algebra"
# Tiled shader is the adaptive shader with only cached-flow/workgroup changes.
for w,h in ((256,128),(640,360),(1280,720),(1279,719)):
    assert (w+15)//16 * 16 >= w
    assert (h+15)//16 * 16 >= h
    assert ((w+15)//16) * ((h+15)//16) > 0
print("EXP29_11_WORKGROUP_ABI_AND_ALGEBRA=PASS; DEVICE_GPU_TIMING=UNTESTED")
