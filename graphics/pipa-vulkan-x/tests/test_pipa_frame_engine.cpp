#include "pipa_frame_engine.h"
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>

#define CHECK(expr) do { if (!(expr)) { \
  std::fprintf(stderr, "FAIL %s:%d: %s\\n", __FILE__, __LINE__, #expr); \
  std::exit(1); \
} } while (0)

static void almost(double actual, double want, double tolerance) {
  CHECK(std::fabs(actual - want) < tolerance);
}

int main() {
  PipaFrameStats s{};
  CHECK(pipa_frame_engine_stats(nullptr, &s) == -1);
  CHECK(pipa_frame_engine_record(nullptr, 1000000000ULL) == -1);
  PipaFrameEngine *e = pipa_frame_engine_create();
  CHECK(e);
  CHECK(pipa_frame_engine_record(e, 1000000000ULL) == 0);
  CHECK(pipa_frame_engine_record(e, 1000000000ULL) == -1);
  uint64_t t = 1000000000ULL;
  for (int i = 0; i < 120; ++i) {
    t += 16666667;
    CHECK(pipa_frame_engine_record(e, t) == 1);
  }
  CHECK(pipa_frame_engine_stats(e, &s) == 0);
  CHECK(s.intervals == 120);
  almost(s.fps_mean, 60.0, 0.001);
  almost(s.frame_ms_p99, 16.666667, 0.00001);
  almost(s.fps_1pct_low, 60.0, 0.001);
  CHECK(s.observed_cadence_hz == 60);
  // One long frame drops 1% low but not enough to change the median cadence.
  t += 33333334;
  CHECK(pipa_frame_engine_record(e, t) == 1);
  CHECK(pipa_frame_engine_stats(e, &s) == 0);
  CHECK(s.fps_1pct_low < 60.0);
  CHECK(s.observed_cadence_hz == 60);
  CHECK(pipa_frame_engine_record(e, t - 10) == -1);

  pipa_frame_engine_reset(e);
  CHECK(pipa_frame_engine_stats(e, &s) == -1);
  t = 1000000000ULL;
  CHECK(pipa_frame_engine_record(e, t) == 0);
  for (int i = 0; i < 1100; ++i) {
    t += 8333333;
    CHECK(pipa_frame_engine_record(e, t) == 1);
  }
  CHECK(pipa_frame_engine_stats(e, &s) == 0);
  CHECK(s.intervals == 1024);
  CHECK(s.observed_cadence_hz == 120);
  pipa_frame_engine_destroy(e);

  CHECK(pipa_frame_engine_next_deadline(0, 1000000000ULL, 0) == 1000000000ULL);
  CHECK(pipa_frame_engine_next_deadline(0, 1000000000ULL, 60) == 1016666667ULL);
  CHECK(pipa_frame_engine_next_deadline(1000000000ULL, 1030000000ULL, 60)
         == 1033333334ULL);
  CHECK(pipa_frame_engine_next_deadline(0, 1000000000ULL, 9999) == 1000000000ULL);
  CHECK(pipa_frame_engine_next_deadline(UINT64_MAX - 2, UINT64_MAX - 1, 60)
         == UINT64_MAX);
  puts("PIPA_FRAME_ENGINE_TESTS=PASS");
  return 0;
}
