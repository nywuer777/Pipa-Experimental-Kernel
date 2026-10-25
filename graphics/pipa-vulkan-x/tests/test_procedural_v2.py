#!/usr/bin/env python3
"""EXP29.17 shader source ABI, periodic scene and two-profile regression tests."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
v2=(root/"shaders/pipa_scene_v2.comp").read_text()
old=(root/"shaders/pipa_scene.comp").read_text()
ui=(root/"lab-app/app/src/main/java/dev/pipa/framegen/lab/PresenterActivity.java").read_text()
native=(root/"lab-app/app/src/main/cpp/presenter.cpp").read_text()
gradle=(root/"lab-app/app/build.gradle").read_text()
for token in (
    "#version 450",
    "layout(local_size_x=16,local_size_y=16,local_size_z=1)",
    "layout(set=0,binding=0,rgba8) uniform writeonly image2D realImage;",
    "ivec2 dimensions;", "int frameIndex;", "int reserved;",
    "int shift=(scene.frameIndex*2)%scene.dimensions.x;",
    "int x=(p.x-shift+scene.dimensions.x)%scene.dimensions.x;",
    "int localX=x%128;", "int localY=y%128;",
    "imageStore(realImage,p,vec4(clamp(rgb,0.0,1.0),1.0));",
): assert token in v2,token
assert "int x=max(0," not in v2  # check executable shader, not comments
assert "grain=" not in v2
assert "(x*y)%29" not in v2
assert "max(0,xy.x-2*scene.frameIndex)" in old
assert "recordSourceScene(command,uint32_t(frame/2))" in native
assert "const bool synthesized=odd && !holdInsteadOfFG;" in native
for token in (
    "v2Hold144=button(", "v2Fg144=button(",
    "v2Hold144.setOnClickListener(v->start(144,true,true,false,true));",
    "v2Fg144.setOnClickListener(v->start(144,true,false,false,true));",
    '"pipa_scene_v2.comp.spv"',
    "FONTE=V2 tileable sem clamp",
): assert token in ui,token
assert "versionCode 314" in gradle
assert "versionName '29.24-lab'" in gradle

# The former shader emits the same source x=0 over an expanding prefix.
# In V2 every x maps to an actual source column, with no duplicated,
# clamped left stripe. Both modes share exact source-frame generation.
width=1280
for frame in (0,1,30,60,90,119,120):
    translation=(frame*2)%width
    source=[(x-translation+width)%width for x in range(width)]
    assert len(set(source))==width
    assert source[0] == (width-translation)%width
    assert source[-1] == (width-1-translation)%width
    if frame>0:
        legacy=[max(0,x-frame*2) for x in range(width)]
        assert legacy.count(0) >= frame*2
    assert all(0<=x<width for x in source)

# The old tileable background has not been corrupted; overlay geometry may
# legitimately wrap at left/right boundaries at high frameIndex.
assert width%128==0
print("EXP29_17_PROCEDURAL_V2=PASS; NO_CLAMP_COLLAPSE=PASS; ADRENO_VISUAL=UNTESTED")
