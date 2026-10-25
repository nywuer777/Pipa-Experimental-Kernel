#ifndef PIPA_FRAMEGEN_REFERENCE_H
#define PIPA_FRAMEGEN_REFERENCE_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/*
 * EXP29.2 CPU correctness reference, NOT real-time Vulkan frame generation.
 * Inputs are two temporal RGBA8 frames owned by the calling application.
 * stride_bytes applies to all three buffers. Buffers MUST NOT overlap.
 * phase in [0,1] (0=previous, 1=current). search_radius in [0,4].
 * Returns: 0 success, -1 invalid arguments, -2 memory unavailable.
 * Not safe to call concurrently on overlapping output buffers.
 */
int pipa_framegen_reference_rgba8(const uint8_t *previous,
                                  const uint8_t *current,
                                  uint8_t *output,
                                  uint32_t width,
                                  uint32_t height,
                                  uint32_t stride_bytes,
                                  float phase,
                                  uint32_t search_radius);
#ifdef __cplusplus
}
#endif
#endif
