#include "pipa_framegen_vk.h"
#include <cmath>
#include <cstdint>
#include <new>

namespace {
struct Params { int32_t width, height, radius; float phase, cutoff; };
static_assert(sizeof(Params)==20, "GLSL push constant ABI differs");
bool formatIsStorage(VkPhysicalDevice gpu, VkFormat format) {
    VkFormatProperties p{};
    vkGetPhysicalDeviceFormatProperties(gpu,format,&p);
    return (p.optimalTilingFeatures & VK_FORMAT_FEATURE_STORAGE_IMAGE_BIT)!=0;
}
VkShaderModule loadShader(VkDevice d,const uint32_t* words,size_t bytes) {
    VkShaderModuleCreateInfo info{};
    info.sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO;
    info.codeSize=bytes;
    info.pCode=words;
    VkShaderModule module=VK_NULL_HANDLE;
    if(vkCreateShaderModule(d,&info,nullptr,&module)!=VK_SUCCESS) return VK_NULL_HANDLE;
    return module;
}
}
struct PipaFramegenVk {
    VkDevice device=VK_NULL_HANDLE;
    VkDescriptorSetLayout descriptors=VK_NULL_HANDLE;
    VkDescriptorPool pool=VK_NULL_HANDLE;
    VkDescriptorSet set=VK_NULL_HANDLE;
    VkPipelineLayout layout=VK_NULL_HANDLE;
    VkPipeline motion=VK_NULL_HANDLE;
    VkPipeline interpolate=VK_NULL_HANDLE;
    bool motionGroupPerTile=false;
    bool warp16x16=false;
};

extern "C" void pipa_framegen_vk_destroy(PipaFramegenVk* e) {
    if (!e) return;
    if (e->device) {
        if(e->motion) vkDestroyPipeline(e->device,e->motion,nullptr);
        if(e->interpolate) vkDestroyPipeline(e->device,e->interpolate,nullptr);
        if(e->layout) vkDestroyPipelineLayout(e->device,e->layout,nullptr);
        if(e->pool) vkDestroyDescriptorPool(e->device,e->pool,nullptr);
        if(e->descriptors) vkDestroyDescriptorSetLayout(e->device,e->descriptors,nullptr);
    }
    delete e;
}

extern "C" int pipa_framegen_vk_create_ex(VkPhysicalDevice gpu,VkDevice device,
    const uint32_t* motion_spv,size_t motion_bytes,
    const uint32_t* interpolate_spv,size_t interpolate_bytes,uint32_t flags,
    PipaFramegenVk** out) {
    if (!out) return -1;
    *out=nullptr;
    if (flags & ~(PIPA_FRAMEGEN_VK_MOTION_GROUP_PER_TILE | PIPA_FRAMEGEN_VK_WARP_16X16)) return -1;
    if (!gpu || !device || !motion_spv || !interpolate_spv ||
        motion_bytes<20 || interpolate_bytes<20 ||
        (motion_bytes%4)!=0 || (interpolate_bytes%4)!=0 ||
        motion_spv[0]!=0x07230203U || interpolate_spv[0]!=0x07230203U) return -1;
    if (!formatIsStorage(gpu,VK_FORMAT_R8G8B8A8_UNORM) ||
        !formatIsStorage(gpu,VK_FORMAT_R16G16B16A16_SFLOAT)) return -2;

    auto* e=new(std::nothrow) PipaFramegenVk();
    if(!e) return -3;
    e->device=device;
    e->motionGroupPerTile=(flags & PIPA_FRAMEGEN_VK_MOTION_GROUP_PER_TILE)!=0;
    e->warp16x16=(flags & PIPA_FRAMEGEN_VK_WARP_16X16)!=0;
    VkDescriptorSetLayoutBinding bindings[4]{};
    for(uint32_t i=0;i<4;++i) {
        bindings[i].binding=i;
        bindings[i].descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;
        bindings[i].descriptorCount=1;
        bindings[i].stageFlags=VK_SHADER_STAGE_COMPUTE_BIT;
    }
    VkDescriptorSetLayoutCreateInfo sl{};
    sl.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO;
    sl.bindingCount=4; sl.pBindings=bindings;
    if(vkCreateDescriptorSetLayout(device,&sl,nullptr,&e->descriptors)!=VK_SUCCESS) {
        pipa_framegen_vk_destroy(e); return -3;
    }
    VkPushConstantRange range{};
    range.stageFlags=VK_SHADER_STAGE_COMPUTE_BIT;
    range.offset=0; range.size=sizeof(Params);
    VkPipelineLayoutCreateInfo pl{};
    pl.sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO;
    pl.setLayoutCount=1; pl.pSetLayouts=&e->descriptors;
    pl.pushConstantRangeCount=1; pl.pPushConstantRanges=&range;
    if(vkCreatePipelineLayout(device,&pl,nullptr,&e->layout)!=VK_SUCCESS) {
        pipa_framegen_vk_destroy(e); return -3;
    }
    VkDescriptorPoolSize ps{};
    ps.type=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE; ps.descriptorCount=4;
    VkDescriptorPoolCreateInfo pool{};
    pool.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO;
    pool.maxSets=1; pool.poolSizeCount=1; pool.pPoolSizes=&ps;
    if(vkCreateDescriptorPool(device,&pool,nullptr,&e->pool)!=VK_SUCCESS) {
        pipa_framegen_vk_destroy(e); return -3;
    }
    VkDescriptorSetAllocateInfo ds{};
    ds.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO;
    ds.descriptorPool=e->pool;
    ds.descriptorSetCount=1; ds.pSetLayouts=&e->descriptors;
    if(vkAllocateDescriptorSets(device,&ds,&e->set)!=VK_SUCCESS) {
        pipa_framegen_vk_destroy(e); return -3;
    }
    VkShaderModule m=loadShader(device,motion_spv,motion_bytes);
    VkShaderModule w=loadShader(device,interpolate_spv,interpolate_bytes);
    if(!m || !w) {
        if(m) vkDestroyShaderModule(device,m,nullptr);
        if(w) vkDestroyShaderModule(device,w,nullptr);
        pipa_framegen_vk_destroy(e); return -3;
    }
    VkComputePipelineCreateInfo cp{};
    cp.sType=VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO;
    cp.layout=e->layout;
    cp.stage.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
    cp.stage.stage=VK_SHADER_STAGE_COMPUTE_BIT;
    cp.stage.pName="main";
    cp.stage.module=m;
    VkResult a=vkCreateComputePipelines(device,VK_NULL_HANDLE,1,&cp,nullptr,&e->motion);
    cp.stage.module=w;
    VkResult b=a==VK_SUCCESS ?
        vkCreateComputePipelines(device,VK_NULL_HANDLE,1,&cp,nullptr,&e->interpolate) :
        VK_ERROR_INITIALIZATION_FAILED;
    vkDestroyShaderModule(device,m,nullptr);
    vkDestroyShaderModule(device,w,nullptr);
    if(a!=VK_SUCCESS || b!=VK_SUCCESS) {
        pipa_framegen_vk_destroy(e); return -3;
    }
    *out=e; return 0;
}
extern "C" int pipa_framegen_vk_create(VkPhysicalDevice gpu,VkDevice device,
    const uint32_t* motion_spv,size_t motion_bytes,
    const uint32_t* interpolate_spv,size_t interpolate_bytes,
    PipaFramegenVk** out) {
    return pipa_framegen_vk_create_ex(gpu,device,motion_spv,motion_bytes,
                                      interpolate_spv,interpolate_bytes,0,out);
}

extern "C" int pipa_framegen_vk_record_profiled(PipaFramegenVk* e,VkCommandBuffer cmd,
    const PipaFramegenVkImages* images,uint32_t width,uint32_t height,
    float phase,uint32_t radius,float cutoff,
    VkQueryPool queryPool,uint32_t firstQuery) {
    if (!e || !cmd || !images || !images->motion_image ||
        !images->previous_view || !images->current_view ||
        !images->motion_view || !images->output_view ||
        !width || !height || width>8192 || height>8192 || radius>4 ||
        !std::isfinite(phase) || phase<0.f || phase>1.f ||
        !std::isfinite(cutoff) || cutoff<0.f || cutoff>1.f) return -1;
    const VkImageView views[]={images->previous_view,images->current_view,
                               images->motion_view,images->output_view};
    VkDescriptorImageInfo infos[4]{};
    VkWriteDescriptorSet writes[4]{};
    for(uint32_t i=0;i<4;++i) {
        infos[i].imageView=views[i];
        infos[i].imageLayout=VK_IMAGE_LAYOUT_GENERAL;
        writes[i].sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
        writes[i].dstSet=e->set;
        writes[i].dstBinding=i;
        writes[i].descriptorCount=1;
        writes[i].descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;
        writes[i].pImageInfo=&infos[i];
    }
    vkUpdateDescriptorSets(e->device,4,writes,0,nullptr);
    const Params params{static_cast<int32_t>(width),static_cast<int32_t>(height),
                        static_cast<int32_t>(radius),phase,cutoff};
    vkCmdPushConstants(cmd,e->layout,VK_SHADER_STAGE_COMPUTE_BIT,0,sizeof(params),&params);
    vkCmdBindDescriptorSets(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,e->layout,
                            0,1,&e->set,0,nullptr);
    if(queryPool!=VK_NULL_HANDLE)
        vkCmdWriteTimestamp(cmd,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,queryPool,firstQuery);
    vkCmdBindPipeline(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,e->motion);
    const uint32_t tx=(width+15)/16,ty=(height+15)/16;
    if(e->motionGroupPerTile)
        vkCmdDispatch(cmd,tx,ty,1);
    else
        vkCmdDispatch(cmd,(tx+7)/8,(ty+7)/8,1);

    if(queryPool!=VK_NULL_HANDLE)
        vkCmdWriteTimestamp(cmd,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,queryPool,firstQuery+1u);

    VkImageMemoryBarrier barrier{};
    barrier.sType=VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
    barrier.srcAccessMask=VK_ACCESS_SHADER_WRITE_BIT;
    barrier.dstAccessMask=VK_ACCESS_SHADER_READ_BIT;
    barrier.oldLayout=VK_IMAGE_LAYOUT_GENERAL;
    barrier.newLayout=VK_IMAGE_LAYOUT_GENERAL;
    barrier.srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;
    barrier.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;
    barrier.image=images->motion_image;
    barrier.subresourceRange.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;
    barrier.subresourceRange.baseMipLevel=0;
    barrier.subresourceRange.levelCount=1;
    barrier.subresourceRange.baseArrayLayer=0;
    barrier.subresourceRange.layerCount=1;
    vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                         VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,0,0,nullptr,
                         0,nullptr,1,&barrier);
    vkCmdBindPipeline(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,e->interpolate);
    if(e->warp16x16)
        vkCmdDispatch(cmd,(width+15)/16,(height+15)/16,1);
    else
        vkCmdDispatch(cmd,(width+7)/8,(height+7)/8,1);
    if(queryPool!=VK_NULL_HANDLE)
        vkCmdWriteTimestamp(cmd,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,queryPool,firstQuery+2u);
    // Output stays GENERAL. App owns output visibility and presentation.
    return 0;
}
extern "C" int pipa_framegen_vk_record(PipaFramegenVk* e,VkCommandBuffer cmd,
    const PipaFramegenVkImages* images,uint32_t width,uint32_t height,
    float phase,uint32_t radius,float cutoff) {
    return pipa_framegen_vk_record_profiled(e,cmd,images,width,height,
                                            phase,radius,cutoff,VK_NULL_HANDLE,0);
}
