#!/usr/bin/env python3
"""EXP29.16: ensure the forensic baseline preserves Vulkan dispatch and scene ABI."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
diag=(root/"shaders/pipa_scene_diagnostic.comp").read_text()
source=(root/"shaders/pipa_scene.comp").read_text()
native=(root/"lab-app/app/src/main/cpp/presenter.cpp").read_text()
ui=(root/"lab-app/app/src/main/java/dev/pipa/framegen/lab/PresenterActivity.java").read_text()
gradle=(root/"lab-app/app/build.gradle").read_text()
abi=[
    "layout(local_size_x=16,local_size_y=16,local_size_z=1)",
    "layout(set=0,binding=0,rgba8) uniform writeonly image2D realImage",
    "ivec2 dimensions;", "int frameIndex;", "int reserved;",
    "imageStore(realImage,p,vec4(rgb,1.0));",
]
for tok in abi: assert tok in diag,tok
assert "imageStore(realImage,xy,vec4(rgb,1.0));" in source
assert "grain=" not in diag and "%29" not in diag
assert "p.x<70 && p.y<70" in diag
assert "scene.dimensions.y-70" in diag
assert "scene.dimensions.x-70" in diag
assert "p.x%80" in diag and "p.y%80" in diag
assert "scene.frameIndex%160" in diag
for tok in (
 "diagHold144=button(", "diagFg144=button(",
 "diagHold144.setOnClickListener(v->start(144,true,true,true))",
 "diagFg144.setOnClickListener(v->start(144,true,false,true))",
 '"pipa_scene_diagnostic.comp.spv":"pipa_scene.comp.spv"',
 "result=nativePresent(surface,motion,warp,scene,hz,stress?1440:240,",
 "FONTE=DIAGNOSTICA quadrantes solidos; sem ruido",
): assert tok in ui,tok
for tok in (
 "chosenTransform=sci.preTransform",
 "std::to_string(uint32_t(p.chosenTransform))",
 "std::to_string(p.useBlit?1:0)",
 "std::to_string(int(p.swapFormat))",
 "const bool synthesized=odd && !holdInsteadOfFG;",
 "if(continuous && !odd)",
 "recordSourceScene(command,uint32_t(frame/2))",
): assert tok in native,tok
assert "versionCode 310" in gradle
assert "versionName '29.20-lab'" in gradle
print("EXP29_16_FORENSIC_SHADERS_AND_PRESENT_ABI=PASS; DEVICE_VISUAL_DIAG=UNTESTED")
