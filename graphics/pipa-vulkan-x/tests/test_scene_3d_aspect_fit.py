#!/usr/bin/env python3
"""EXP29.22 aspect-fit presentation guard, not a hardware imaging result."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
native=(root/"lab-app/app/src/main/cpp/presenter.cpp").read_text()
java=(root/"lab-app/app/src/main/java/dev/pipa/framegen/lab/PresenterActivity.java").read_text()
gradle=(root/"lab-app/app/build.gradle").read_text()
for token in (
    "bool fitAspect=false;",
    "bool fit3dAspect",
    "fitAspect=fit3dAspect;",
    "const double fitScale=std::min(",
    "fitWidth=std::min(extent.width,",
    "fitHeight=std::min(extent.height,",
    "if(fitAspect) {",
    "vkCmdClearColorImage(command,swapImages[index],",
    "clearToBlit.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;",
    "clearToBlit.dstAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;",
    "vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_TRANSFER_BIT,",
    "blit.dstOffsets[0]={left,top,0};",
    "blit.dstOffsets[1]={left+width,top+height,1};",
    "jboolean fit3dAspectMode",
    "fit3dAspectMode==JNI_TRUE",
    '" | FIT 16:9="',
    '" | viewport destino="',
    "result+=p.gpuTimingSummary();",
    "result+=p.cpuPacingSummary();",
    "result+=p.timingSummary();",
): assert token in native,token
for token in (
    "EXP29.25 - PAIR BUDGET GOVERNOR",
    "boolean alignWithDisplay, int motionRadius, boolean fit3dAspect,",
    "continuous,holdInsteadOfFG,alignWithDisplay,motionRadius,",
    "scene3dHold.setOnClickListener(",
    "scene3dFg.setOnClickListener(",
    "copyReport.setOnClickListener(",
    "fastMotion.setChecked(false);",
): assert token in java,token
assert "versionCode 316" in gradle
assert "29.26-governor-overload" in gradle
# Reference algebra for source 1280x720; FIT rect always fits and
# keeps a source-equivalent aspect ratio to within pixel rounding.
for w,h in ((1280,720),(2844,790),(2048,1280),(1920,1080),(790,2844),(512,512)):
    scale=min(w/1280,h/720)
    dw=min(w,max(1,round(1280*scale)))
    dh=min(h,max(1,round(720*scale)))
    x=(w-dw)//2;y=(h-dh)//2
    assert 0<=x<x+dw<=w
    assert 0<=y<y+dh<=h
    assert abs(dw/dh - 1280/720)<0.005,(w,h,dw,dh)
print("EXP29_22_ASPECT_FIT_SOURCE_CONTRACT=PASS; PIXEL_VALIDATION_ON_ADRENO=PENDING")
