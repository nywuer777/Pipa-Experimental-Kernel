#include "pipa_framegen_reference.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <new>
#include <vector>

namespace {
constexpr int kBlock = 16;
constexpr int kSampleStep = 2;
struct Motion { int dx = 0; int dy = 0; };

static unsigned sample_error(const uint8_t* a, const uint8_t* b) {
  return static_cast<unsigned>(std::abs(int(a[0]) - int(b[0])) +
                               std::abs(int(a[1]) - int(b[1])) +
                               std::abs(int(a[2]) - int(b[2])));
}

static float pixel_channel(const uint8_t* data, uint32_t stride,
                           uint32_t width, uint32_t height,
                           float x, float y, unsigned channel) {
  x = std::max(0.0f, std::min(x, static_cast<float>(width - 1)));
  y = std::max(0.0f, std::min(y, static_cast<float>(height - 1)));
  const auto x0 = static_cast<uint32_t>(x);
  const auto y0 = static_cast<uint32_t>(y);
  const auto x1 = std::min(x0 + 1, width - 1);
  const auto y1 = std::min(y0 + 1, height - 1);
  const float fx = x - static_cast<float>(x0);
  const float fy = y - static_cast<float>(y0);
  const auto at = [=](uint32_t xx, uint32_t yy) -> float {
    return static_cast<float>(data[size_t(yy) * stride + size_t(xx) * 4 + channel]);
  };
  const float top = at(x0,y0) * (1.0f - fx) + at(x1,y0) * fx;
  const float bot = at(x0,y1) * (1.0f - fx) + at(x1,y1) * fx;
  return top * (1.0f - fy) + bot * fy;
}
}

extern "C" int pipa_framegen_reference_rgba8(
    const uint8_t* previous, const uint8_t* current, uint8_t* output,
    uint32_t width, uint32_t height, uint32_t stride_bytes,
    float phase, uint32_t search_radius) {
  if (!previous || !current || !output || !width || !height ||
      width > 8192 || height > 8192 || stride_bytes < uint64_t(width) * 4 ||
      search_radius > 4 || !std::isfinite(phase) || phase < 0.f || phase > 1.f)
    return -1;

  const size_t size = size_t(stride_bytes) * height;
  const uintptr_t p = reinterpret_cast<uintptr_t>(previous);
  const uintptr_t c = reinterpret_cast<uintptr_t>(current);
  const uintptr_t o = reinterpret_cast<uintptr_t>(output);
  // The reference implementation intentionally disallows any buffer aliasing.
  const auto intersects = [size](uintptr_t a, uintptr_t b) -> bool {
    return a <= b ? (b - a < size) : (a - b < size);
  };
  if (intersects(p, o) || intersects(c, o) ||
      size > std::numeric_limits<uintptr_t>::max() - std::max({p,c,o})) return -1;

  if (phase == 0.f || phase == 1.f) {
    const uint8_t* source = phase == 0.f ? previous : current;
    for (uint32_t y = 0; y < height; ++y)
      std::memcpy(output + size_t(y)*stride_bytes,
                  source + size_t(y)*stride_bytes, size_t(width)*4);
    return 0;
  }

  const uint32_t grid_w = (width + kBlock - 1) / kBlock;
  const uint32_t grid_h = (height + kBlock - 1) / kBlock;
  std::vector<Motion> flow;
  try { flow.resize(size_t(grid_w) * grid_h); }
  catch (const std::bad_alloc&) { return -2; }

  if (search_radius != 0) {
    for (uint32_t by = 0; by < grid_h; ++by) {
      for (uint32_t bx = 0; bx < grid_w; ++bx) {
        const int left = int(bx) * kBlock;
        const int top = int(by) * kBlock;
        const int right = std::min(left + kBlock, int(width));
        const int bottom = std::min(top + kBlock, int(height));
        uint64_t best_score = UINT64_MAX;
        unsigned best_len2 = UINT32_MAX;
        Motion best{};
        for (int dy = -int(search_radius); dy <= int(search_radius); ++dy) {
          for (int dx = -int(search_radius); dx <= int(search_radius); ++dx) {
            if (left + dx < 0 || top + dy < 0 ||
                right + dx > int(width) || bottom + dy > int(height)) continue;
            uint64_t score = 0;
            for (int y = top; y < bottom; y += kSampleStep) {
              for (int x = left; x < right; x += kSampleStep) {
                const uint8_t* a = previous + size_t(y)*stride_bytes + size_t(x)*4;
                const uint8_t* b = current + size_t(y+dy)*stride_bytes + size_t(x+dx)*4;
                score += sample_error(a,b);
              }
            }
            const unsigned len2 = unsigned(dx*dx + dy*dy);
            if (score < best_score || (score == best_score && len2 < best_len2)) {
              best_score = score;
              best_len2 = len2;
              best = {dx,dy};
            }
          }
        }
        flow[size_t(by)*grid_w + bx] = best;
      }
    }
  }

  for (uint32_t y = 0; y < height; ++y) {
    for (uint32_t x = 0; x < width; ++x) {
      const Motion m = flow[size_t(y/kBlock)*grid_w + x/kBlock];
      const float fx = static_cast<float>(x);
      const float fy = static_cast<float>(y);
      const float ax = fx - phase*static_cast<float>(m.dx);
      const float ay = fy - phase*static_cast<float>(m.dy);
      const float bx = fx + (1.f-phase)*static_cast<float>(m.dx);
      const float by = fy + (1.f-phase)*static_cast<float>(m.dy);
      uint8_t* dst = output + size_t(y)*stride_bytes + size_t(x)*4;
      for (unsigned channel = 0; channel < 4; ++channel) {
        const float a = pixel_channel(previous,stride_bytes,width,height,ax,ay,channel);
        const float b = pixel_channel(current,stride_bytes,width,height,bx,by,channel);
        dst[channel] = static_cast<uint8_t>(std::lround((1.f-phase)*a + phase*b));
      }
    }
  }
  return 0;
}
