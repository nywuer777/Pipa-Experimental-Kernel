#!/usr/bin/env python3
"""EXP29.9 dispatch regression: verify pipeline/variant matches GLSL workgroup contract.
This test guards the verified bug from EXP29.8, not a GPU execution substitute.
"""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
lab = (root / "lab-app/app/src/main/cpp/lab.cpp").read_text()
engine = (root / "src/pipa_framegen_vk.cpp").read_text()
parallel = (root / "shaders/pipa_motion_parallel.comp").read_text()
sparse = (root / "shaders/pipa_motion_sparse.comp").read_text()
legacy = (root / "shaders/pipa_motion.comp").read_text()
fast = (root / "shaders/pipa_motion_fast.comp").read_text()

# CRITICAL: all three workgroup-per-tile modes must select matching motion dispatch.
assert "motionVariant==2 || motionVariant==3 || motionVariant==4" in lab
assert "if(e->motionGroupPerTile)" in engine
assert "vkCmdDispatch(cmd,tx,ty,1);" in engine
assert "vkCmdDispatch(cmd,(tx+7)/8,(ty+7)/8,1);" in engine
for shader in (parallel, sparse):
    assert "gl_WorkGroupID.xy" in shader
for shader in (legacy, fast):
    assert "gl_GlobalInvocationID.xy" in shader

for width,height in ((256,128), (640,360), (1280,720), (1920,1080)):
    tx=(width+15)//16
    ty=(height+15)//16
    correct_groups=tx*ty
    incorrect_groups=((tx+7)//8)*((ty+7)//8)
    assert correct_groups >= incorrect_groups
    assert correct_groups>incorrect_groups

# A CPU oracle for the 2-pixel displacement used in the APK test.
# SPARSE's 4px sample density must still identify the true motion vector.
def pixel(x,y,width=640,height=360):
    x=max(0,min(width-1,x))
    y=max(0,min(height-1,y))
    coarse=32 if ((x//16+y//16)&1)==0 else 46
    texture=(x*17+y*23+(x*y)%29)&63
    return (min(255,coarse+texture*2),min(255,coarse+texture),
            min(255,coarse+texture//2))

evaluated=0
for y in range(16,328,32):
    for x in range(16,608,32):
        scores=[]
        for dy in (-4,-2,0,2,4):
            for dx in (-4,-2,0,2,4):
                cost=0
                for yy in range(y,y+16,4):
                    for xx in range(x,x+16,4):
                        old=pixel(xx,yy)
                        now=pixel(xx+dx-2,yy+dy)
                        cost+=sum(abs(a-b) for a,b in zip(old,now))
                scores.append((cost,dx*dx+dy*dy,dx,dy))
        best=min(scores)
        assert best[0]==0 and (best[2],best[3])==(2,0),(x,y,best)
        evaluated+=1

print("EXP29_9_DISPATCH_REGRESSION=PASS")
print("SPARSE_CPU_REFERENCE_TILES="+str(evaluated))
print("SPARSE_GPU_CORRECTNESS=NOT_YET_TESTED")
