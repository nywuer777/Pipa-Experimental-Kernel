#!/usr/bin/env python3
"""EXP29.14 controlled 2x Vulkan generator contract; timing still requires tablet."""
from pathlib import Path
p=Path(__file__).resolve().parents[1]
cpp=(p/"lab-app/app/src/main/cpp/presenter.cpp").read_text()
java=(p/"lab-app/app/src/main/java/dev/pipa/framegen/lab/PresenterActivity.java").read_text()
shader=(p/"shaders/pipa_scene.comp").read_text()
gradle=(p/"lab-app/app/build.gradle").read_text()
for token in (
    "recordSourceScene(command,uint32_t(frame/2));",
    "const bool odd=(frame%2)==1;",
    "const bool synthesized=odd && !holdInsteadOfFG && !budgetFallback;",
    "int source=continuous?0:",
    "VkDescriptorSet sceneDescriptors[2]",
    "vkCreateComputePipelines(",
    "vkCreateDescriptorPool(",
    "vkUpdateDescriptorSets(",
    "vkCmdPushConstants(cmd,scenePipelineLayout,",
    "vkCmdDispatch(cmd,(kWidth+15)/16,(kHeight+15)/16,1);",
    "VK_ACCESS_SHADER_WRITE_BIT,",
    "VK_ACCESS_SHADER_READ_BIT",
    "if(continuous)createScenePipeline(scene);",
    "if(continuous) scene=shaderBytes(env,sceneShader);",
    "PIPA_FRAMEGEN_VK_WARP_16X16",
    "jboolean continuousMode",
    "sceneRealSubmitted",
    "sceneGeneratedSubmitted",
    "deadlineMisses",
    "VK_GOOGLE_display_timing",
    "reportedActualNs[records[i].presentID]=",
    "NAO sao FPS fisicos exibidos",
):
    assert token in cpp, token
for token in (
    "animate120=button(", "animate144=button(",
    "start(120,true)", "start(144,true)",
    '"pipa_scene.comp.spv"',
    "result=nativePresent(surface,motion,warp,scene,hz,stress?1440:240,", "framegen", "nativeStop()",
):
    assert token in java, token
for token in (
    "layout(local_size_x=16,local_size_y=16,local_size_z=1)",
    "layout(set=0,binding=0,rgba8) uniform writeonly image2D",
    "int frameIndex;", "xy.x-2*scene.frameIndex",
    "imageStore(realImage,xy,vec4(rgb,1.0));",
):
    assert token in shader, token
assert "versionCode 314" in gradle
assert "versionName '29.24-lab'" in gradle
for frames in (120,240):
    produced=[]
    for frame in range(frames):
        if frame%2==0:
            pair=frame//2
            produced.append((pair, "real", pair))
        else:
            pair=frame//2
            produced.append((pair, "interpolated", pair+0.5))
    assert len(produced)==frames
    assert sum(x[1]=="real" for x in produced)==frames//2
    assert sum(x[1]=="interpolated" for x in produced)==frames//2
    assert all(produced[i][2] < produced[i+1][2] for i in range(frames-1))
print("EXP29_14_CONTINUOUS_GPU_SCENE_SOURCE_CONTRACT=PASS; DEVICE_PRESENT=UNTESTED")
