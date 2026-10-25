#!/usr/bin/env python3
"""EXP29.10: mathematical equivalence of tap-selection fast paths.
This is a CPU oracle plus static contract, not an assertion of GPU correctness.
"""
from pathlib import Path
from math import floor, isclose
root=Path(__file__).resolve().parents[1]
source=(root/"shaders/pipa_interpolate_adaptive.comp").read_text()
for clause in ("if (f.x == 0.0 && f.y == 0.0) return a;",
               "if (f.y == 0.0)", "if (f.x == 0.0)",
               "return mix(mix(a,b,f.x),mix(c,d,f.x),f.y);"):
    assert clause in source,clause

W,H=31,27
def pixel(x,y):
    return ((17*x+21*y+3)%256,(7*x+37*y+11)%256,(43*x+5*y+19)%256,255)
def sample_old(x,y):
    x=max(0.0,min(float(W-1),x))
    y=max(0.0,min(float(H-1),y))
    x0=int(floor(x));y0=int(floor(y))
    x1=min(W-1,x0+1);y1=min(H-1,y0+1)
    fx=x-x0;fy=y-y0
    a=pixel(x0,y0);b=pixel(x1,y0)
    c=pixel(x0,y1);d=pixel(x1,y1)
    return tuple(((a[i]*(1-fx)+b[i]*fx)*(1-fy)+
                 (c[i]*(1-fx)+d[i]*fx)*fy) for i in range(4))
def sample_adaptive(x,y):
    x=max(0.0,min(float(W-1),x))
    y=max(0.0,min(float(H-1),y))
    x0=int(floor(x));y0=int(floor(y))
    x1=min(W-1,x0+1);y1=min(H-1,y0+1)
    fx=x-x0;fy=y-y0
    a=pixel(x0,y0)
    if fx==0 and fy==0: return a
    if fy==0:
        b=pixel(x1,y0)
        return tuple(a[i]*(1-fx)+b[i]*fx for i in range(4))
    if fx==0:
        c=pixel(x0,y1)
        return tuple(a[i]*(1-fy)+c[i]*fy for i in range(4))
    return sample_old(x,y)

n=0
for phase in (0.0,0.25,0.5,0.75,1.0):
    for dx in range(-4,5):
        for dy in range(-4,5):
            for x,y in ((0,0),(1,2),(15,17),(W-1,H-1),(W-2,H-2)):
                for sign in (-1,1):
                    sx=x+sign*phase*dx
                    sy=y+sign*phase*dy
                    a=sample_old(sx,sy)
                    b=sample_adaptive(sx,sy)
                    assert all(isclose(i,j,abs_tol=1e-9) for i,j in zip(a,b)),(sx,sy,a,b)
                    n+=1
print(f"EXP29_10_ADAPTIVE_MATH_EQUIVALENCE=PASS ({n} CPU samples); DEVICE=UNTESTED")
