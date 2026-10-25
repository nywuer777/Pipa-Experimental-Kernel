#include "pipa_frame_engine.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <new>
#include <vector>

namespace {
constexpr size_t kCapacity = 1024;
constexpr uint64_t kMinFrameNs = 100000;        // 0.1 ms
constexpr uint64_t kMaxFrameNs = 10000000000ULL; // 10 s
constexpr uint32_t kCadenceRates[] = {24, 30, 40, 45, 60, 72, 90, 120, 144, 165, 240};

double percentile(const std::vector<double> &sorted, double fraction) {
  if (sorted.size() == 1) return sorted.front();
  const double pos = fraction * (sorted.size() - 1);
  const size_t lo = static_cast<size_t>(pos);
  const size_t hi = std::min(lo + 1, sorted.size() - 1);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}
} // namespace

struct PipaFrameEngine {
  uint64_t last_timestamp_ns = 0;
  bool has_baseline = false;
  uint64_t durations[kCapacity] = {};
  size_t count = 0;
  size_t next = 0;
};

extern "C" PipaFrameEngine *pipa_frame_engine_create(void) {
  return new (std::nothrow) PipaFrameEngine();
}
extern "C" void pipa_frame_engine_destroy(PipaFrameEngine *engine) {
  delete engine;
}
extern "C" void pipa_frame_engine_reset(PipaFrameEngine *engine) {
  if (engine) *engine = PipaFrameEngine{};
}
extern "C" int pipa_frame_engine_record(PipaFrameEngine *engine, uint64_t stamp) {
  if (!engine || stamp == 0) return -1;
  if (!engine->has_baseline) {
    engine->last_timestamp_ns = stamp;
    engine->has_baseline = true;
    return 0;
  }
  if (stamp <= engine->last_timestamp_ns) return -1;
  uint64_t delta = stamp - engine->last_timestamp_ns;
  engine->last_timestamp_ns = stamp;
  if (delta < kMinFrameNs || delta > kMaxFrameNs) return -1;
  engine->durations[engine->next] = delta;
  engine->next = (engine->next + 1) % kCapacity;
  engine->count = std::min(engine->count + 1, kCapacity);
  return 1;
}
extern "C" int pipa_frame_engine_stats(const PipaFrameEngine *engine,
                                          PipaFrameStats *out) {
  if (!engine || !out || !engine->count) return -1;
  std::vector<double> sorted;
  sorted.reserve(engine->count);
  double total = 0.0;
  for (size_t i = 0; i < engine->count; ++i) {
    const double ms = static_cast<double>(engine->durations[i]) / 1000000.0;
    sorted.push_back(ms);
    total += ms;
  }
  std::sort(sorted.begin(), sorted.end());
  const double avg = total / engine->count;
  const size_t slowest = std::max<size_t>(1, (engine->count + 99) / 100);
  double worst_sum = 0.0;
  for (size_t i = 0; i < slowest; ++i) {
    worst_sum += sorted[sorted.size() - 1 - i];
  }
  PipaFrameStats s{};
  s.intervals = static_cast<uint32_t>(engine->count);
  s.fps_mean = 1000.0 / avg;
  s.frame_ms_mean = avg;
  s.frame_ms_p50 = percentile(sorted, 0.50);
  s.frame_ms_p95 = percentile(sorted, 0.95);
  s.frame_ms_p99 = percentile(sorted, 0.99);
  s.fps_1pct_low = 1000.0 / (worst_sum / slowest);
  s.frame_ms_max = sorted.back();

  // An observed 60 Hz cadence is NOT proof of a game cap: display vsync,
  // frame pacing, workload, and app loops can all produce the same cadence.
  if (engine->count >= 45) {
    const double median = s.frame_ms_p50;
    const double iqr = percentile(sorted, 0.75) - percentile(sorted, 0.25);
    if (iqr <= median * 0.07) {
      for (uint32_t hz : kCadenceRates) {
        const double target_ms = 1000.0 / hz;
        if (std::abs(median - target_ms) <= target_ms * 0.035) {
          s.observed_cadence_hz = hz;
          break;
        }
      }
    }
  }
  *out = s;
  return 0;
}
extern "C" uint64_t pipa_frame_engine_next_deadline(
    uint64_t last_deadline_ns, uint64_t now_ns, uint32_t target_hz) {
  if (target_hz == 0) return now_ns;
  if (target_hz > 1000) return now_ns; // invalid, fail open
  const uint64_t period = (1000000000ULL + target_hz / 2) / target_hz;
  if (last_deadline_ns == 0 || last_deadline_ns > now_ns) {
    return now_ns <= UINT64_MAX - period ? now_ns + period : UINT64_MAX;
  }
  const uint64_t missed = (now_ns - last_deadline_ns) / period + 1;
  const uint64_t remaining = UINT64_MAX - last_deadline_ns;
  if (missed > remaining / period) return UINT64_MAX;
  return last_deadline_ns + missed * period;
}
