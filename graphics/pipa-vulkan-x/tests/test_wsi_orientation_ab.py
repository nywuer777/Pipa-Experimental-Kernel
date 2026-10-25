#!/usr/bin/env python3
"""EXP29.23: Vulkan WSI preTransform identity/current A/B source safety."""
from pathlib import Path
base=Path(__file__).resolve().parents[1]
c=(base/"lab-app/app/src/main/cpp/presenter.cpp").read_text()
j=(base/"lab-app/app/src/main/java/dev/pipa/framegen/lab/PresenterActivity.java").read_text()
gradle=(base/"lab-app/app/build.gradle").read_text()
for token in (
 "VkSurfaceTransformFlagBitsKHR currentTransform=VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR;",
 "VkSurfaceTransformFlagsKHR supportedTransforms=0;",
 "requestedIdentity3d=preferIdentityFor3D;",
 "currentTransform=caps.currentTransform;",
 "supportedTransforms=caps.supportedTransforms;",
 "VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR)!=0;",
 "sci.preTransform=(preferIdentityFor3D && canIdentity)?",
 "VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR:caps.currentTransform;",
 "chosenTransform=sci.preTransform;",
 "identity3dAccepted=preferIdentityFor3D && canIdentity;",
 "fit3dAspectMode==JNI_TRUE && preferIdentity3dMode==JNI_TRUE",
 "p.init(env,surface,motion,warp,scene,continuous,",
 "fit3dAspectMode==JNI_TRUE,",
 '" | supportedTransforms="',
 '" | currentTransform="',
 '" | IDENTITY solicitada="',
 '" | IDENTITY ativa="',
 "vkCmdBlitImage(command,texSource.image,",
): assert token in c,token
for token in (
 "identity3d.setChecked(true);",
 "scene3d && identity3d.isChecked();",
 "boolean preferIdentity3d, boolean gpuBudgetGuard);",
 "scene3d,preferIdentity3d,adaptiveGuard);",
 "scene3dHold.setOnClickListener(",
 "scene3dFg.setOnClickListener(",
 "Motion FAST",
 "SYNC experimental",
): assert token in j,token
assert "versionCode 314" in gradle and "29.24-lab" in gradle
# The fallback to currentTransform is mandatory on a surface that does
# not support identity. Do not attempt unsupported swapchain transforms.
assert "sci.preTransform=caps.currentTransform;" not in c
print("EXP29_23_WSI_ORIENTATION_AB_SOURCE=PASS; HARDWARE_VALIDATION=PENDING")
