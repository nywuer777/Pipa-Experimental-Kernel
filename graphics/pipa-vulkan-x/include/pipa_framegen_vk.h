#ifndef PIPA_FRAMEGEN_VK_H
#define PIPA_FRAMEGEN_VK_H

#include <stddef.h>
#include <stdint.h>
#include <vulkan/vulkan.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct PipaFramegenVk PipaFramegenVk;

// All image views: 2D, single mip/layer, VK_IMAGE_LAYOUT_GENERAL.
// previous/current/output: R8G8B8A8_UNORM, size width x height.
// motion: R16G16B16A16_SFLOAT, size ceil(width/16) x ceil(height/16).
// Images must have VK_IMAGE_USAGE_STORAGE_BIT; caller owns transitions,
// allocations, command buffers, external sync, queue submit and presentation.
typedef struct PipaFramegenVkImages {
    VkImageView previous_view;
    VkImageView current_view;
    VkImageView motion_view;
    VkImageView output_view;
    VkImage motion_image;
} PipaFramegenVkImages;

// Shader words must be 4-byte-aligned valid SPIR-V; *_bytes multiples of 4.
// 0=ok, -1=invalid args, -2=unsupported storage image formats, -3=Vulkan failure.
int pipa_framegen_vk_create(VkPhysicalDevice gpu, VkDevice device,
                            const uint32_t* motion_spv, size_t motion_bytes,
                            const uint32_t* interpolate_spv, size_t interpolate_bytes,
                            PipaFramegenVk** out);
void pipa_framegen_vk_destroy(PipaFramegenVk* engine);

// App provides a RECORDING compute-capable command buffer and images already
// transitioned to GENERAL. Callers handle pre/post dispatch barriers.
// Serialise re-recording and descriptor updates: wait on previous submission
// that uses this instance, or keep one instance per in-flight frame.
// 0=recorded; -1=invalid arguments. No submission/presentation performed.
int pipa_framegen_vk_record(PipaFramegenVk* engine, VkCommandBuffer cmd,
                            const PipaFramegenVkImages* images,
                            uint32_t width, uint32_t height,
                            float phase, uint32_t search_radius,
                            float error_cutoff);
#ifdef __cplusplus
}
#endif
#endif
