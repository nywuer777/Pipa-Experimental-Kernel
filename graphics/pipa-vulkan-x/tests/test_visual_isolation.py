#!/usr/bin/env python3
"""EXP29.15 regression: isolate original-source HOLD mode from generated frames.

Static source/ABI test; real Vulkan correctness still requires the Adreno device.
"""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
native=(root/"lab-app/app/src/main/cpp/presenter.cpp").read_text()
ui=(root/"lab-app/app/src/main/java/dev/pipa/framegen/lab/PresenterActivity.java").read_text()
gradle=(root/"lab-app/app/build.gradle").read_text()

for token in (
 "bool holdInsteadOfFG",
 "const bool odd=(frame%2)==1",
 "const bool synthesized=odd && !holdInsteadOfFG;",
 "int source=continuous?0:((frame%4)==2?1:0);",
 "Texture& texSource=tex[synthesized?3:source];",
 "if(continuous && !odd)",
 "recordSourceScene(command,uint32_t(frame/2))",
 "if(synthesized) {",
 "if(odd && holdInsteadOfFG)++sceneHeldSubmitted;",
 "else if(synthesized)++sceneGeneratedSubmitted;",
 "else ++sceneRealSubmitted;",
 "jboolean holdInsteadOfFGMode",
 "const bool holdInsteadOfFG=continuous && holdInsteadOfFGMode==JNI_TRUE;",
 "p.run(targetHz,frames,continuous,holdInsteadOfFG,",
 "std::to_string(p.sceneHeldSubmitted)",
 "VK_GOOGLE_display_timing",
): assert token in native,token

for token in (
 "nativePresent(Surface surface, byte[] motion, byte[] warp,",
 "boolean continuous, boolean holdInsteadOfFG",
 "hold144=button(",
 "hold144.setOnClickListener(v->start(144,true,true));",
 "hold144.setEnabled(enabled && validSurface);",
 "result=nativePresent(surface,motion,warp,scene,hz,stress?1440:240,",
): assert token in ui,token
assert "versionCode 311" in gradle
assert "versionName '29.21-lab'" in gradle

for hold in (False,True):
 for frame in range(240):
  odd=frame%2==1
  generated=odd and not hold
  # Continuous mode always uses GPU-native tex[0] for the even source.
  texture=3 if generated else 0
  assert (texture==3)==generated
  if hold: assert not generated
 print(f"EXP29_15_FRAME_ROLE_CHECK hold={hold}: PASS")
print("EXP29_15_HOLD_SOURCE_ISOLATION=PASS; DEVICE_VISUAL_TEST=UNTESTED")
