#!/usr/bin/env python3
"""EXP29.21 build-time 3D perspective source and Android profile contract."""
from pathlib import Path
base=Path(__file__).resolve().parents[1]
scene=(base/"shaders/pipa_scene_3d.comp").read_text()
java=(base/"lab-app/app/src/main/java/dev/pipa/framegen/lab/PresenterActivity.java").read_text()
native=(base/"lab-app/app/src/main/cpp/presenter.cpp").read_text()
build=(base/"lab-app/app/build.gradle").read_text()
for name in (
    "#version 450",
    "layout(local_size_x=16,local_size_y=16,local_size_z=1) in;",
    "layout(set=0,binding=0,rgba8) uniform writeonly image2D realImage;",
    "ivec2 dimensions;", "int frameIndex;", "int reserved;",
    "sphereHit(", "vec3 camera=", "vec3 focus=",
    "vec3 ray=normalize(", "float nearest=farT;",
    "if(chosen<nearest)",
    "float plane=(-0.8-camera.y)/ray.y;",
    "time=float(scene.frameIndex)*0.025;",
    "imageStore(realImage,pix,vec4(clamp(color,0.0,1.0),1.0));",
): assert name in scene,name
assert "max(0,xy.x-2*scene.frameIndex)" not in scene
assert "float chosen=min(t0,min(t1,t2));" in scene
assert "GPU raytrace" not in scene # no implied hardware ray tracing
for name in (
    "scene3dHold=button(", "scene3dFg=button(",
    "scene3dHold.setOnClickListener(v->start(144,true,true,false,false,true,true));",
    "scene3dFg.setOnClickListener(v->start(144,true,false,false,false,true,true));",
    "legacyControls.setVisibility(View.GONE);",
    "scene3d?\"pipa_scene_3d.comp.spv\"",
    "FONTE=3D raycast perspectiva e oclusao",
    "fastMotion.isChecked()?3:4;",
    "alignWithDisplay,motionRadius",
    "copyReport.setOnClickListener(v->",
): assert name in java,name
for name in (
    "recordSourceScene(command,uint32_t(frame/2))",
    "const bool synthesized=odd && !holdInsteadOfFG && !budgetFallback;",
    "pipa_framegen_vk_record_profiled(",
    "cpuPacingSummary()",
    "gpuTimingSummary()",
): assert name in native,name
assert "versionCode 315" in build
assert "29.25-lab" in build
print("EXP29_21_3D_PERSPECTIVE_OCCLUSION_SOURCE_CONTRACT=PASS; HARDWARE_3D_PENDING")
