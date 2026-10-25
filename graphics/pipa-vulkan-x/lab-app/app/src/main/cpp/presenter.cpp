#define VK_USE_PLATFORM_ANDROID_KHR 1
#include <jni.h>
#include <android/native_window_jni.h>
#include <vulkan/vulkan.h>
#include "pipa_framegen_vk.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {
std::atomic<bool> g_stop{false};
std::atomic<bool> g_inUse{false};
constexpr uint32_t kWidth=1280, kHeight=720;

void check(VkResult r, const char* label) {
    if(r!=VK_SUCCESS) throw std::runtime_error(std::string(label)+
                                               " VkResult="+std::to_string(int(r)));
}
void expect(bool p,const char* reason) { if(!p) throw std::runtime_error(reason); }
struct Texture {
    VkImage image=VK_NULL_HANDLE;
    VkDeviceMemory allocation=VK_NULL_HANDLE;
    VkImageView view=VK_NULL_HANDLE;
};
VkImageMemoryBarrier imageBarrier(VkImage img,VkImageLayout oldLayout,VkImageLayout newLayout,
                                  VkAccessFlags src,VkAccessFlags dst) {
    VkImageMemoryBarrier b{};
    b.sType=VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
    b.srcAccessMask=src; b.dstAccessMask=dst;
    b.oldLayout=oldLayout; b.newLayout=newLayout;
    b.srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;
    b.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;
    b.image=img;
    b.subresourceRange.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;
    b.subresourceRange.levelCount=1;
    b.subresourceRange.layerCount=1;
    return b;
}
std::vector<uint32_t> shaderBytes(JNIEnv* env,jbyteArray array) {
    expect(array!=nullptr,"Missing SPIR-V shader asset");
    jsize n=env->GetArrayLength(array);
    expect(n>=20 && n<=8*1024*1024 && (n%4)==0,"Invalid SPIR-V asset length");
    std::vector<uint32_t> words(size_t(n)/4);
    env->GetByteArrayRegion(array,0,n,reinterpret_cast<jbyte*>(words.data()));
    expect(!env->ExceptionCheck() && words[0]==0x07230203U,"Bad SPIR-V asset");
    return words;
}
uint8_t channel(int x,int y,int c) {
    x=std::max(0,std::min(1279,x));
    y=std::max(0,std::min(719,y));
    int coarse=((x/16+y/16)&1)==0?32:46;
    int noise=(x*17+y*23+(x*y)%29)&63;
    int rgb[]={std::min(255,coarse+noise*2),std::min(255,coarse+noise),
               std::min(255,coarse+noise/2)};
    // A thin contrast stripe makes the motion visible on the native surface.
    if(x>=480 && x<495 && y>=130 && y<590)
        return c==0?240:c==1?212:48;
    return static_cast<uint8_t>(rgb[c]);
}
struct Presenter {
    ANativeWindow* window=nullptr;
    VkInstance instance=VK_NULL_HANDLE;
    VkSurfaceKHR surface=VK_NULL_HANDLE;
    VkPhysicalDevice physical=VK_NULL_HANDLE;
    VkDevice device=VK_NULL_HANDLE;
    VkSwapchainKHR swap=VK_NULL_HANDLE;
    VkQueue queue=VK_NULL_HANDLE;
    VkCommandPool pool=VK_NULL_HANDLE;
    VkCommandBuffer command=VK_NULL_HANDLE;
    VkFence fence=VK_NULL_HANDLE;
    VkSemaphore acquired=VK_NULL_HANDLE;
    std::vector<VkSemaphore> rendered;
    VkFormat swapFormat=VK_FORMAT_UNDEFINED;
    VkExtent2D extent{};
    std::vector<VkImage> swapImages;
    VkBuffer staging=VK_NULL_HANDLE;
    VkDeviceMemory stagingMemory=VK_NULL_HANDLE;
    Texture tex[4]{};
    PipaFramegenVk* engine=nullptr;
    VkPhysicalDeviceMemoryProperties memory{};
    std::string gpuName;
    bool useBlit=true;
    ~Presenter() {
        if(device) vkDeviceWaitIdle(device);
        if(engine) pipa_framegen_vk_destroy(engine);
        if(device) {
            for(auto semaphore:rendered)if(semaphore)vkDestroySemaphore(device,semaphore,nullptr);
            if(acquired)vkDestroySemaphore(device,acquired,nullptr);
            if(fence)vkDestroyFence(device,fence,nullptr);
            if(pool)vkDestroyCommandPool(device,pool,nullptr);
            if(staging)vkDestroyBuffer(device,staging,nullptr);
            if(stagingMemory)vkFreeMemory(device,stagingMemory,nullptr);
            for(auto& x:tex) {
                if(x.view)vkDestroyImageView(device,x.view,nullptr);
                if(x.image)vkDestroyImage(device,x.image,nullptr);
                if(x.allocation)vkFreeMemory(device,x.allocation,nullptr);
            }
            if(swap)vkDestroySwapchainKHR(device,swap,nullptr);
            vkDestroyDevice(device,nullptr);
        }
        if(surface && instance)vkDestroySurfaceKHR(instance,surface,nullptr);
        if(instance)vkDestroyInstance(instance,nullptr);
        if(window)ANativeWindow_release(window);
    }
    uint32_t selectMemory(uint32_t allowed,VkMemoryPropertyFlags flags) const {
        for(uint32_t i=0;i<memory.memoryTypeCount;++i) {
            if((allowed & (1u<<i)) &&
               (memory.memoryTypes[i].propertyFlags & flags)==flags)return i;
        }
        throw std::runtime_error("Required Vulkan memory flags unavailable");
    }
    void makeTexture(int index,uint32_t w,uint32_t h,VkFormat format,
                     VkImageUsageFlags extra) {
        auto& out=tex[index];
        VkImageCreateInfo c{};
        c.sType=VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO;
        c.imageType=VK_IMAGE_TYPE_2D;
        c.format=format;
        c.extent={w,h,1};
        c.mipLevels=1;c.arrayLayers=1;c.samples=VK_SAMPLE_COUNT_1_BIT;
        c.tiling=VK_IMAGE_TILING_OPTIMAL;
        c.sharingMode=VK_SHARING_MODE_EXCLUSIVE;
        c.usage=VK_IMAGE_USAGE_STORAGE_BIT|extra;
        c.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED;
        check(vkCreateImage(device,&c,nullptr,&out.image),"vkCreateImage");
        VkMemoryRequirements req{};
        vkGetImageMemoryRequirements(device,out.image,&req);
        VkMemoryAllocateInfo alloc{};
        alloc.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO;
        alloc.allocationSize=req.size;
        alloc.memoryTypeIndex=selectMemory(req.memoryTypeBits,VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);
        check(vkAllocateMemory(device,&alloc,nullptr,&out.allocation),"vkAllocateMemory texture");
        check(vkBindImageMemory(device,out.image,out.allocation,0),"vkBindImageMemory");
        VkImageViewCreateInfo view{};
        view.sType=VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO;
        view.image=out.image;
        view.viewType=VK_IMAGE_VIEW_TYPE_2D;
        view.format=format;
        view.subresourceRange.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;
        view.subresourceRange.levelCount=1;
        view.subresourceRange.layerCount=1;
        check(vkCreateImageView(device,&view,nullptr,&out.view),"vkCreateImageView");
    }
    void init(JNIEnv* env,jobject surfaceObject,
              const std::vector<uint32_t>& motion,const std::vector<uint32_t>& warp) {
        window=ANativeWindow_fromSurface(env,surfaceObject);
        expect(window!=nullptr,"No ANativeWindow from Android Surface");
        const char* instanceExts[]={VK_KHR_SURFACE_EXTENSION_NAME,VK_KHR_ANDROID_SURFACE_EXTENSION_NAME};
        VkApplicationInfo app{};
        app.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO;
        app.pApplicationName="Pipa FrameGen Presenter EXP29.12";
        app.apiVersion=VK_API_VERSION_1_1;
        VkInstanceCreateInfo ci{};
        ci.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;
        ci.pApplicationInfo=&app;
        ci.enabledExtensionCount=2;ci.ppEnabledExtensionNames=instanceExts;
        check(vkCreateInstance(&ci,nullptr,&instance),"vkCreateInstance");
        VkAndroidSurfaceCreateInfoKHR androidSurface{};
        androidSurface.sType=VK_STRUCTURE_TYPE_ANDROID_SURFACE_CREATE_INFO_KHR;
        androidSurface.window=window;
        check(vkCreateAndroidSurfaceKHR(instance,&androidSurface,nullptr,&surface),
              "vkCreateAndroidSurfaceKHR");

        uint32_t n=0;
        check(vkEnumeratePhysicalDevices(instance,&n,nullptr),"Enumerate GPUs count");
        expect(n!=0,"No Vulkan physical devices");
        std::vector<VkPhysicalDevice> gpus(n);
        check(vkEnumeratePhysicalDevices(instance,&n,gpus.data()),"Enumerate GPUs");
        uint32_t family=UINT32_MAX;
        for(VkPhysicalDevice gpu:gpus) {
            uint32_t families=0;
            vkGetPhysicalDeviceQueueFamilyProperties(gpu,&families,nullptr);
            std::vector<VkQueueFamilyProperties> props(families);
            vkGetPhysicalDeviceQueueFamilyProperties(gpu,&families,props.data());
            for(uint32_t i=0;i<families;++i) {
                VkBool32 supported=VK_FALSE;
                check(vkGetPhysicalDeviceSurfaceSupportKHR(gpu,i,surface,&supported),
                      "Surface support");
                if(props[i].queueCount && (props[i].queueFlags&VK_QUEUE_COMPUTE_BIT) &&
                   supported==VK_TRUE) {
                    physical=gpu;family=i;break;
                }
            }
            if(physical)break;
        }
        expect(physical!=VK_NULL_HANDLE,"No compute+present Vulkan queue family");
        VkPhysicalDeviceProperties gpuProps{};
        vkGetPhysicalDeviceProperties(physical,&gpuProps);
        gpuName=gpuProps.deviceName;
        vkGetPhysicalDeviceMemoryProperties(physical,&memory);
        VkPhysicalDeviceFeatures available{};
        vkGetPhysicalDeviceFeatures(physical,&available);
        expect(available.shaderStorageImageExtendedFormats==VK_TRUE,
               "RGBA16F storage images not supported");

        const float priority=1.0f;
        VkDeviceQueueCreateInfo qi{};
        qi.sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO;
        qi.queueFamilyIndex=family;
        qi.queueCount=1;qi.pQueuePriorities=&priority;
        VkPhysicalDeviceFeatures enabled{};
        enabled.shaderStorageImageExtendedFormats=VK_TRUE;
        const char* deviceExts[]={VK_KHR_SWAPCHAIN_EXTENSION_NAME};
        VkDeviceCreateInfo di{};
        di.sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO;
        di.queueCreateInfoCount=1;di.pQueueCreateInfos=&qi;
        di.enabledExtensionCount=1;di.ppEnabledExtensionNames=deviceExts;
        di.pEnabledFeatures=&enabled;
        check(vkCreateDevice(physical,&di,nullptr,&device),"vkCreateDevice swapchain");
        vkGetDeviceQueue(device,family,0,&queue);

        VkSurfaceCapabilitiesKHR caps{};
        check(vkGetPhysicalDeviceSurfaceCapabilitiesKHR(physical,surface,&caps),
              "Surface capabilities");
        expect((caps.supportedUsageFlags & VK_IMAGE_USAGE_TRANSFER_DST_BIT)!=0,
               "Swapchain does not support TRANSFER_DST (graphics path required)");
        if(caps.currentExtent.width!=UINT32_MAX) {
            extent=caps.currentExtent;
        } else {
            extent.width=std::max(caps.minImageExtent.width,
                                  std::min(caps.maxImageExtent.width,uint32_t(ANativeWindow_getWidth(window))));
            extent.height=std::max(caps.minImageExtent.height,
                                   std::min(caps.maxImageExtent.height,uint32_t(ANativeWindow_getHeight(window))));
        }
        expect(extent.width>0 && extent.height>0,"Invalid surface extent");
        uint32_t fmtCount=0;
        check(vkGetPhysicalDeviceSurfaceFormatsKHR(physical,surface,&fmtCount,nullptr),
              "Surface format count");
        expect(fmtCount>0,"No surface formats");
        std::vector<VkSurfaceFormatKHR> formats(fmtCount);
        check(vkGetPhysicalDeviceSurfaceFormatsKHR(physical,surface,&fmtCount,formats.data()),
              "Surface formats");
        VkSurfaceFormatKHR chosen=formats[0];
        for(auto f:formats) {
            if(f.format==VK_FORMAT_R8G8B8A8_UNORM ||
               f.format==VK_FORMAT_B8G8R8A8_UNORM) {
                chosen=f;break;
            }
        }
        if(chosen.format==VK_FORMAT_UNDEFINED) {
            chosen.format=VK_FORMAT_R8G8B8A8_UNORM;
            chosen.colorSpace=VK_COLOR_SPACE_SRGB_NONLINEAR_KHR;
        }
        swapFormat=chosen.format;
        useBlit=swapFormat!=VK_FORMAT_R8G8B8A8_UNORM ||
                extent.width!=kWidth || extent.height!=kHeight;
        if(useBlit) {
            VkFormatProperties src{},dst{};
            vkGetPhysicalDeviceFormatProperties(physical,VK_FORMAT_R8G8B8A8_UNORM,&src);
            vkGetPhysicalDeviceFormatProperties(physical,swapFormat,&dst);
            expect((src.optimalTilingFeatures&VK_FORMAT_FEATURE_BLIT_SRC_BIT) &&
                   (dst.optimalTilingFeatures&VK_FORMAT_FEATURE_BLIT_DST_BIT),
                   "Swapchain needs blit conversion but device blit not supported");
        }
        uint32_t imageCount=caps.minImageCount+1;
        if(caps.maxImageCount>0) imageCount=std::min(imageCount,caps.maxImageCount);
        VkSwapchainCreateInfoKHR sci{};
        sci.sType=VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR;
        sci.surface=surface;
        sci.minImageCount=imageCount;
        sci.imageFormat=swapFormat;
        sci.imageColorSpace=chosen.colorSpace;
        sci.imageExtent=extent;
        sci.imageArrayLayers=1;
        sci.imageUsage=VK_IMAGE_USAGE_TRANSFER_DST_BIT;
        sci.imageSharingMode=VK_SHARING_MODE_EXCLUSIVE;
        sci.preTransform=caps.currentTransform;
        sci.compositeAlpha=(caps.supportedCompositeAlpha&VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR) ?
            VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR : VK_COMPOSITE_ALPHA_INHERIT_BIT_KHR;
        if(!(caps.supportedCompositeAlpha&sci.compositeAlpha)) {
            for(auto bit:{VK_COMPOSITE_ALPHA_PRE_MULTIPLIED_BIT_KHR,
                          VK_COMPOSITE_ALPHA_POST_MULTIPLIED_BIT_KHR}) {
                if(caps.supportedCompositeAlpha&bit) {sci.compositeAlpha=bit;break;}
            }
        }
        sci.presentMode=VK_PRESENT_MODE_FIFO_KHR;
        sci.clipped=VK_TRUE;
        check(vkCreateSwapchainKHR(device,&sci,nullptr,&swap),"vkCreateSwapchainKHR");
        uint32_t actual=0;
        check(vkGetSwapchainImagesKHR(device,swap,&actual,nullptr),"Swapchain image count");
        swapImages.resize(actual);
        check(vkGetSwapchainImagesKHR(device,swap,&actual,swapImages.data()),"Swapchain images");

        VkCommandPoolCreateInfo cp{};
        cp.sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO;
        cp.queueFamilyIndex=family;
        cp.flags=VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;
        check(vkCreateCommandPool(device,&cp,nullptr,&pool),"vkCreateCommandPool");
        VkCommandBufferAllocateInfo ca{};
        ca.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
        ca.commandPool=pool;
        ca.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY;
        ca.commandBufferCount=1;
        check(vkAllocateCommandBuffers(device,&ca,&command),"vkAllocateCommandBuffers");
        VkFenceCreateInfo fi{};
        fi.sType=VK_STRUCTURE_TYPE_FENCE_CREATE_INFO;
        fi.flags=VK_FENCE_CREATE_SIGNALED_BIT;
        check(vkCreateFence(device,&fi,nullptr,&fence),"vkCreateFence");
        VkSemaphoreCreateInfo si{};
        si.sType=VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO;
        check(vkCreateSemaphore(device,&si,nullptr,&acquired),"Create acquire semaphore");
        rendered.resize(actual,VK_NULL_HANDLE);
        for(auto& sem:rendered)
            check(vkCreateSemaphore(device,&si,nullptr,&sem),"Create present semaphore");

        makeTexture(0,kWidth,kHeight,VK_FORMAT_R8G8B8A8_UNORM,
                    VK_IMAGE_USAGE_TRANSFER_DST_BIT|VK_IMAGE_USAGE_TRANSFER_SRC_BIT);
        makeTexture(1,kWidth,kHeight,VK_FORMAT_R8G8B8A8_UNORM,
                    VK_IMAGE_USAGE_TRANSFER_DST_BIT|VK_IMAGE_USAGE_TRANSFER_SRC_BIT);
        makeTexture(2,(kWidth+15)/16,(kHeight+15)/16,
                    VK_FORMAT_R16G16B16A16_SFLOAT,0);
        makeTexture(3,kWidth,kHeight,VK_FORMAT_R8G8B8A8_UNORM,
                    VK_IMAGE_USAGE_TRANSFER_SRC_BIT);
        int code=pipa_framegen_vk_create_ex(physical,device,
              motion.data(),motion.size()*sizeof(uint32_t),
              warp.data(),warp.size()*sizeof(uint32_t),
              PIPA_FRAMEGEN_VK_MOTION_GROUP_PER_TILE|PIPA_FRAMEGEN_VK_WARP_16X16,
              &engine);
        expect(code==0,"pipa_framegen_vk_create_ex failed");

        const VkDeviceSize one=VkDeviceSize(kWidth)*kHeight*4;
        VkBufferCreateInfo bi{};
        bi.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
        bi.size=one*2;
        bi.usage=VK_BUFFER_USAGE_TRANSFER_SRC_BIT;
        bi.sharingMode=VK_SHARING_MODE_EXCLUSIVE;
        check(vkCreateBuffer(device,&bi,nullptr,&staging),"Create staging buffer");
        VkMemoryRequirements req{};
        vkGetBufferMemoryRequirements(device,staging,&req);
        VkMemoryAllocateInfo ma{};
        ma.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO;
        ma.allocationSize=req.size;
        ma.memoryTypeIndex=selectMemory(req.memoryTypeBits,
              VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);
        check(vkAllocateMemory(device,&ma,nullptr,&stagingMemory),"Allocate staging");
        check(vkBindBufferMemory(device,staging,stagingMemory,0),"Bind staging");
        void* ptr=nullptr;
        check(vkMapMemory(device,stagingMemory,0,one*2,0,&ptr),"Map staging");
        auto* rgba=static_cast<uint8_t*>(ptr);
        for(int y=0;y<int(kHeight);++y)for(int x=0;x<int(kWidth);++x) {
            for(int frame=0;frame<2;++frame) {
                auto at=size_t(frame)*size_t(one)+(size_t(y)*kWidth+size_t(x))*4;
                for(int c=0;c<3;++c)rgba[at+c]=channel(x-frame*2,y,c);
                rgba[at+3]=255;
            }
        }
        vkUnmapMemory(device,stagingMemory);
        check(vkResetCommandPool(device,pool,0),"Reset upload pool");
        VkCommandBufferBeginInfo begin{};
        begin.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
        begin.flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
        check(vkBeginCommandBuffer(command,&begin),"Begin upload");
        VkImageMemoryBarrier initial[4]{};
        for(int i=0;i<4;++i) {
            initial[i]=imageBarrier(tex[i].image,VK_IMAGE_LAYOUT_UNDEFINED,
                i<2?VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL:VK_IMAGE_LAYOUT_GENERAL,
                0,i<2?VK_ACCESS_TRANSFER_WRITE_BIT:VK_ACCESS_SHADER_WRITE_BIT);
        }
        vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
              VK_PIPELINE_STAGE_TRANSFER_BIT|VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
              0,0,nullptr,0,nullptr,4,initial);
        for(int i=0;i<2;++i) {
            VkBufferImageCopy copy{};
            copy.bufferOffset=VkDeviceSize(i)*one;
            copy.imageSubresource.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;
            copy.imageSubresource.layerCount=1;
            copy.imageExtent={kWidth,kHeight,1};
            vkCmdCopyBufferToImage(command,staging,tex[i].image,
                                   VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,1,&copy);
        }
        VkImageMemoryBarrier ready[2]{};
        for(int i=0;i<2;++i)
            ready[i]=imageBarrier(tex[i].image,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
                         VK_IMAGE_LAYOUT_GENERAL,VK_ACCESS_TRANSFER_WRITE_BIT,
                         VK_ACCESS_SHADER_READ_BIT);
        vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_TRANSFER_BIT,
                             VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,0,0,nullptr,
                             0,nullptr,2,ready);
        check(vkEndCommandBuffer(command),"End upload");
        VkSubmitInfo submit{};
        submit.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO;
        submit.commandBufferCount=1;
        submit.pCommandBuffers=&command;
        check(vkResetFences(device,1,&fence),"Reset upload fence");
        check(vkQueueSubmit(queue,1,&submit,fence),"Submit upload");
        check(vkWaitForFences(device,1,&fence,VK_TRUE,10000000000ULL),"Wait upload fence");
    }
    int run(int targetHz,int requested) {
        const PipaFramegenVkImages images={
          tex[0].view,tex[1].view,tex[2].view,tex[3].view,tex[2].image
        };
        int queued=0;
        const auto start=std::chrono::steady_clock::now();
        const auto interval=std::chrono::nanoseconds(1000000000LL/targetHz);
        for(int frame=0;frame<requested && !g_stop.load();++frame) {
            auto deadline=start+interval*frame;
            std::this_thread::sleep_until(deadline);
            check(vkWaitForFences(device,1,&fence,VK_TRUE,10000000000ULL),
                  "Wait frame fence");
            uint32_t index=0;
            VkResult acquiredResult=vkAcquireNextImageKHR(device,swap,UINT64_MAX,
                                                         acquired,VK_NULL_HANDLE,&index);
            if(acquiredResult==VK_ERROR_OUT_OF_DATE_KHR)break;
            expect(acquiredResult==VK_SUCCESS || acquiredResult==VK_SUBOPTIMAL_KHR,
                   "Acquire swapchain image failed");
            check(vkResetFences(device,1,&fence),"Reset frame fence");
            check(vkResetCommandPool(device,pool,0),"Reset frame command pool");
            VkCommandBufferBeginInfo begin{};
            begin.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
            begin.flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
            check(vkBeginCommandBuffer(command,&begin),"Begin frame");
            // Real A, synthesized midpoint, real B, synthesized midpoint (loop).
            bool synthesized=(frame%2)==1;
            int source=(frame%4)==2?1:0;
            Texture& texSource=tex[synthesized?3:source];
            if(synthesized) {
                expect(pipa_framegen_vk_record(engine,command,&images,kWidth,kHeight,
                                               0.5f,4,0.75f)==0,"Record FrameGen failed");
            }
            auto fromLayout=VK_IMAGE_LAYOUT_GENERAL;
            auto sourceBarrier=imageBarrier(texSource.image,fromLayout,
                             VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,
                             synthesized?VK_ACCESS_SHADER_WRITE_BIT:VK_ACCESS_SHADER_READ_BIT,
                             VK_ACCESS_TRANSFER_READ_BIT);
            vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                 VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,nullptr,0,nullptr,1,&sourceBarrier);
            auto destination=imageBarrier(swapImages[index],VK_IMAGE_LAYOUT_UNDEFINED,
                             VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,0,
                             VK_ACCESS_TRANSFER_WRITE_BIT);
            vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
                 VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,nullptr,0,nullptr,1,&destination);

            if(useBlit) {
                VkImageBlit blit{};
                blit.srcSubresource.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;
                blit.srcSubresource.layerCount=1;
                blit.srcOffsets[1]={int32_t(kWidth),int32_t(kHeight),1};
                blit.dstSubresource.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;
                blit.dstSubresource.layerCount=1;
                blit.dstOffsets[1]={int32_t(extent.width),int32_t(extent.height),1};
                vkCmdBlitImage(command,texSource.image,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,
                               swapImages[index],VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
                               1,&blit,VK_FILTER_NEAREST);
            } else {
                VkImageCopy copy{};
                copy.srcSubresource.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;
                copy.srcSubresource.layerCount=1;
                copy.dstSubresource.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;
                copy.dstSubresource.layerCount=1;
                copy.extent={kWidth,kHeight,1};
                vkCmdCopyImage(command,texSource.image,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,
                               swapImages[index],VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
                               1,&copy);
            }
            auto back=imageBarrier(texSource.image,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,
                                   VK_IMAGE_LAYOUT_GENERAL,VK_ACCESS_TRANSFER_READ_BIT,
                                   VK_ACCESS_SHADER_READ_BIT|VK_ACCESS_SHADER_WRITE_BIT);
            auto presented=imageBarrier(swapImages[index],VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
                                     VK_IMAGE_LAYOUT_PRESENT_SRC_KHR,
                                     VK_ACCESS_TRANSFER_WRITE_BIT,0);
            vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_TRANSFER_BIT,
                 VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,0,0,nullptr,0,nullptr,1,&back);
            vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_TRANSFER_BIT,
                 VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,0,0,nullptr,0,nullptr,1,&presented);
            check(vkEndCommandBuffer(command),"End frame");
            VkPipelineStageFlags waitStage=VK_PIPELINE_STAGE_TRANSFER_BIT;
            VkSubmitInfo submit{};
            submit.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO;
            submit.waitSemaphoreCount=1;
            submit.pWaitSemaphores=&acquired;
            submit.pWaitDstStageMask=&waitStage;
            submit.commandBufferCount=1;
            submit.pCommandBuffers=&command;
            submit.signalSemaphoreCount=1;
            submit.pSignalSemaphores=&rendered[index];
            check(vkQueueSubmit(queue,1,&submit,fence),"Submit present frame");
            VkPresentInfoKHR present{};
            present.sType=VK_STRUCTURE_TYPE_PRESENT_INFO_KHR;
            present.waitSemaphoreCount=1;
            present.pWaitSemaphores=&rendered[index];
            present.swapchainCount=1;
            present.pSwapchains=&swap;
            present.pImageIndices=&index;
            VkResult pr=vkQueuePresentKHR(queue,&present);
            if(pr==VK_ERROR_OUT_OF_DATE_KHR)break;
            expect(pr==VK_SUCCESS || pr==VK_SUBOPTIMAL_KHR,"vkQueuePresentKHR failed");
            ++queued;
        }
        check(vkQueueWaitIdle(queue),"Wait present queue idle");
        return queued;
    }
};

} // namespace

extern "C" JNIEXPORT void JNICALL
Java_dev_pipa_framegen_lab_PresenterActivity_nativeStop(JNIEnv*,jobject) {
    g_stop.store(true);
}

extern "C" JNIEXPORT jstring JNICALL
Java_dev_pipa_framegen_lab_PresenterActivity_nativePresent(
    JNIEnv* env,jobject,jobject surface,jbyteArray motionShader,jbyteArray warpShader,
    jint targetHz,jint frames) {
    bool expected=false;
    if(!g_inUse.compare_exchange_strong(expected,true))
        return env->NewStringUTF("Uma sessão Vulkan já está ativa.");
    g_stop.store(false);
    std::string result;
    try {
        expect(targetHz==60 || targetHz==120 || targetHz==144,"Invalid targetHz");
        expect(frames>0 && frames<=1000,"Invalid frame count");
        auto motion=shaderBytes(env,motionShader);
        auto warp=shaderBytes(env,warpShader);
        Presenter p;
        auto t0=std::chrono::steady_clock::now();
        p.init(env,surface,motion,warp);
        auto t1=std::chrono::steady_clock::now();
        int queued=p.run(targetHz,frames);
        auto t2=std::chrono::steady_clock::now();
        double initializeMs=std::chrono::duration<double,std::milli>(t1-t0).count();
        double presentSeconds=std::chrono::duration<double>(t2-t1).count();
        double apiRate=queued/std::max(0.000001,presentSeconds);
        result="GPU "+p.gpuName+" | VkSwapchainKHR FIFO | "+
          std::to_string(p.extent.width)+"x"+std::to_string(p.extent.height)+
          " | Aceitos por vkQueuePresentKHR: "+std::to_string(queued)+
          " (real="+std::to_string((queued+1)/2)+
          ", interpolado="+std::to_string(queued/2)+")"+
          " | Frequencia solicitada="+std::to_string(targetHz)+" Hz"+
          " | chamadas apresentacao/s="+std::to_string(apiRate)+
          " | inicializacao="+std::to_string(initializeMs)+" ms"+
          " | NAO sao FPS fisicos exibidos.";
    } catch(const std::exception& e) {
        result=std::string("EXP29.12 Vulkan presenter: ")+e.what();
    }
    g_inUse.store(false);
    return env->NewStringUTF(result.c_str());
}
