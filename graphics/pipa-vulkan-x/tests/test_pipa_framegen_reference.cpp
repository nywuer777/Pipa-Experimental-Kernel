#include "pipa_framegen_reference.h"
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <vector>
#define CHECK(x) do { if(!(x)) { std::fprintf(stderr,"FAIL %s:%d %s\n",__FILE__,__LINE__,#x); std::exit(1); } } while(0)
int main() {
  constexpr int w=64, h=48, stride=w*4;
  std::vector<uint8_t> a(stride*h), b(stride*h), out(stride*h);
  CHECK(pipa_framegen_reference_rgba8(a.data(), b.data(), out.data(), w, h, stride, -0.1f, 2) == -1);
  CHECK(pipa_framegen_reference_rgba8(a.data(), b.data(), out.data(), w, h, stride, NAN, 2) == -1);
  CHECK(pipa_framegen_reference_rgba8(a.data(), b.data(), out.data(), w, h, stride, 0.5f, 5) == -1);
  CHECK(pipa_framegen_reference_rgba8(a.data(), b.data(), a.data(), w, h, stride, 0.5f, 2) == -1);
  CHECK(pipa_framegen_reference_rgba8(a.data(), b.data(), out.data(), w, h, stride-1, 0.5f, 2) == -1);
  for(size_t i=0;i<a.size();i+=4){ a[i]=a[i+1]=a[i+2]=32; a[i+3]=255; b[i]=b[i+1]=b[i+2]=96; b[i+3]=255; }
  CHECK(pipa_framegen_reference_rgba8(a.data(),b.data(),out.data(),w,h,stride,0.5f,0)==0);
  for(size_t i=0;i<out.size();i+=4){ CHECK(out[i]==64 && out[i+1]==64 && out[i+2]==64 && out[i+3]==255); }
  CHECK(pipa_framegen_reference_rgba8(a.data(),b.data(),out.data(),w,h,stride,0.f,2)==0);
  CHECK(out[0]==32);
  CHECK(pipa_framegen_reference_rgba8(a.data(),b.data(),out.data(),w,h,stride,1.f,2)==0);
  CHECK(out[0]==96);
  // Uniform horizontal motion of a deterministic textured frame: exact +2px shift.
  for(int y=0;y<h;y++) for(int x=0;x<w;x++){
    const size_t i=size_t(y)*stride+x*4;
    const uint8_t v=uint8_t((x*17+y*23+(x*y)%29)%256);
    a[i]=v; a[i+1]=uint8_t(v^0x4b); a[i+2]=uint8_t(v^0xe7); a[i+3]=255;
  }
  for(int y=0;y<h;y++) for(int x=0;x<w;x++){
    const size_t dst=size_t(y)*stride+x*4;
    const size_t src=size_t(y)*stride+size_t(x>1?x-2:0)*4;
    for(int k=0;k<4;k++) b[dst+k]=a[src+k];
  }
  CHECK(pipa_framegen_reference_rgba8(a.data(),b.data(),out.data(),w,h,stride,0.5f,4)==0);
  for(int y=16;y<32;y+=3) for(int x=18;x<30;x+=3){
    const size_t i=size_t(y)*stride+x*4;
    const size_t expected=size_t(y)*stride+(x-1)*4;
    for(int k=0;k<3;k++) CHECK(std::abs(int(out[i+k])-int(a[expected+k]))<=1);
  }
  std::puts("PIPA_FRAMEGEN_REFERENCE_TESTS=PASS");
}
