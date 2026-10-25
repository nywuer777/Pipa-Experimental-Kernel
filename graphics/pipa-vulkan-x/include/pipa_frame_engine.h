#ifndef PIPA_FRAME_ENGINE_H
#define PIPA_FRAME_ENGINE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct PipaFrameEngine PipaFrameEngine;

typedef struct PipaFrameStats {
  uint32_t intervals;
  double fps_mean;
  double frame_ms_mean;
  double frame_ms_p50;
  double frame_ms_p95;
  double frame_ms_p99;
  double fps_1pct_low;
  double frame_ms_max;
  /* 0: cadence not identifiable. Nonzero: periodic cadence near this rate.
     Does NOT establish whether the limit originates in engine, GPU or OS. */
  uint32_t observed_cadence_hz;
} PipaFrameStats;

/* Timestamps MUST be monotonic nanoseconds, from the same clock. */
PipaFrameEngine *pipa_frame_engine_create(void);
void pipa_frame_engine_destroy(PipaFrameEngine *engine);
void pipa_frame_engine_reset(PipaFrameEngine *engine);
/* 1=accepted, 0=first frame (baseline), -1=invalid/out of order. */
int pipa_frame_engine_record(PipaFrameEngine *engine, uint64_t timestamp_ns);
/* 0 on success, -1 on null pointer/no intervals. */
int pipa_frame_engine_stats(const PipaFrameEngine *engine, PipaFrameStats *out);

/* Pure deadline calculator, not a hook and not a replacement for Android
   SurfaceFlinger vsync. A target > hardware refresh does NOT increase actual
   physical presentation frequency. 0 disables this pacer (uncapped). */
uint64_t pipa_frame_engine_next_deadline(uint64_t last_deadline_ns,
                                          uint64_t now_ns,
                                          uint32_t target_hz);

#ifdef __cplusplus
}
#endif
#endif
