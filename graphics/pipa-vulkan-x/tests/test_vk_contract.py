#!/usr/bin/env python3
"""Static source contract only. SPIR-V compilation and validation are separate checks."""
import pathlib
import re

root=pathlib.Path(__file__).resolve().parents[1]
expected={
    "pipa_motion.comp":{0:("rgba8","readonly"),1:("rgba8","readonly"),2:("rgba16f","writeonly")},
    "pipa_interpolate.comp":{0:("rgba8","readonly"),1:("rgba8","readonly"),2:("rgba16f","readonly"),3:("rgba8","writeonly")},
}
for name, bindings in expected.items():
    source=(root/"shaders"/name).read_text()
    pattern=r"layout\(set=0,\s*binding=(\d+),\s*(\w+)\)\s+uniform\s+(readonly|writeonly)\s+image2D"
    found={int(idx):(fmt,access) for idx,fmt,access in re.findall(pattern,source)}
    assert found==bindings,(name,found)
    assert "layout(local_size_x=8, local_size_y=8, local_size_z=1)" in source
    assert "ivec2 frameSize;\n    int searchRadius;\n    float phase;\n    float errorCutoff;" in source
    assert "greaterThanEqual" in source

cpp=(root/"src/pipa_framegen_vk.cpp").read_text()
for token in ("static_assert(sizeof(Params)==20",
              "VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT",
              "VK_ACCESS_SHADER_WRITE_BIT",
              "VK_ACCESS_SHADER_READ_BIT",
              "VK_IMAGE_LAYOUT_GENERAL",
              "vkCmdDispatch(cmd,(tx+7)/8,(ty+7)/8,1)",
              "vkCmdDispatch(cmd,(width+7)/8,(height+7)/8,1)"):
    assert token in cpp,token

print("EXP29_3_STATIC_SHADER_CONTRACT=PASS (SPIR-V still requires glslangValidator + spirv-val)")
