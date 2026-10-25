#include <jni.h>
#include <vulkan/vulkan.h>
#include "pipa_framegen_vk.h"
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <mutex>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
std::mutex report_mutex;
std::string report="Aguardando teste";
void set_report(const std::string& s) {
    std::lock_guard<std::mutex> lock(report_mutex);
    report=s;
}
void require(VkResult code,const char* what) {
    if(code!=VK_SUCCESS) throw std::runtime_error(std::string(what)+" (VkResult "+std::to_string(int(code))+")");
}
void ensure(bool condition,const char* what) {
    if(!condition) throw std::runtime_error(what);
}
struct Image {
    VkImage image=VK_NULL_HANDLE;
    VkDeviceMemory memory=VK_NULL_HANDLE;
    VkImageView view=VK_NULL_HANDLE;
};
struct Lab {
    VkInstance instance=VK_NULL_HANDLE;
    VkPhysicalDevice physical=VK_NULL_HANDLE;
    VkDevice device=VK_NULL_HANDLE;
    VkQueue queue=VK_NULL_HANDLE;
    VkCommandPool commandPool=VK_NULL_HANDLE;
    VkFence fence=VK_NULL_HANDLE;
    VkQueryPool timestampQueries=VK_NULL_HANDLE;
    uint32_t timestampBits=0;
    double timestampPeriodNs=0.0;
    VkBuffer staging=VK_NULL_HANDLE;
    VkDeviceMemory stagingMemory=VK_NULL_HANDLE;
    Image images[4]{};
    PipaFramegenVk* engine=nullptr;
    VkPhysicalDeviceMemoryProperties mem{};
    std::string gpuName;

    ~Lab() {
        if(device) vkDeviceWaitIdle(device);
        if(engine) pipa_framegen_vk_destroy(engine);
        if(device) {
            if(timestampQueries) vkDestroyQueryPool(device,timestampQueries,nullptr);
            if(fence) vkDestroyFence(device,fence,nullptr);
            if(commandPool) vkDestroyCommandPool(device,commandPool,nullptr);
            if(staging) vkDestroyBuffer(device,staging,nullptr);
            if(stagingMemory) vkFreeMemory(device,stagingMemory,nullptr);
            for(auto& im:images) {
                if(im.view) vkDestroyImageView(device,im.view,nullptr);
                if(im.image) vkDestroyImage(device,im.image,nullptr);
                if(im.memory) vkFreeMemory(device,im.memory,nullptr);
            }
            vkDestroyDevice(device,nullptr);
        }
        if(instance) vkDestroyInstance(instance,nullptr);
    }
    uint32_t memoryType(uint32_t bits,VkMemoryPropertyFlags wanted) const {
        for(uint32_t i=0;i<mem.memoryTypeCount;++i)
            if((bits&(1u<<i)) &&
              ((mem.memoryTypes[i].propertyFlags&wanted)==wanted)) return i;
        throw std::runtime_error("Sem tipo de memoria Vulkan compativel");
    }
    void initialize() {
        VkApplicationInfo app{};
        app.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO;
        app.pApplicationName="Pipa FrameGen Lab";
        app.apiVersion=VK_API_VERSION_1_1;
        VkInstanceCreateInfo ci{};
        ci.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;
        ci.pApplicationInfo=&app;
        require(vkCreateInstance(&ci,nullptr,&instance),"vkCreateInstance");
        uint32_t count=0;
        require(vkEnumeratePhysicalDevices(instance,&count,nullptr),"vkEnumeratePhysicalDevices");
        ensure(count>0,"Nenhuma GPU Vulkan foi encontrada");
        std::vector<VkPhysicalDevice> devices(count);
        require(vkEnumeratePhysicalDevices(instance,&count,devices.data()),"vkEnumeratePhysicalDevices list");
        uint32_t family=UINT32_MAX;
        for(auto deviceCandidate:devices) {
            uint32_t families=0;
            vkGetPhysicalDeviceQueueFamilyProperties(deviceCandidate,&families,nullptr);
            std::vector<VkQueueFamilyProperties> props(families);
            vkGetPhysicalDeviceQueueFamilyProperties(deviceCandidate,&families,props.data());
            for(uint32_t i=0;i<families;++i) {
                if(props[i].queueCount && (props[i].queueFlags&VK_QUEUE_COMPUTE_BIT)) {
                    physical=deviceCandidate;
                    family=i;
                    timestampBits=props[i].timestampValidBits;
                    break;
                }
            }
            if(physical) break;
        }
        ensure(physical!=VK_NULL_HANDLE,"GPU sem fila Vulkan Compute");
        VkPhysicalDeviceProperties props{};
        vkGetPhysicalDeviceProperties(physical,&props);
        gpuName=props.deviceName;
        timestampPeriodNs=static_cast<double>(props.limits.timestampPeriod);
        vkGetPhysicalDeviceMemoryProperties(physical,&mem);
        const float priority=1.f;
        VkDeviceQueueCreateInfo queueInfo{};
        queueInfo.sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO;
        queueInfo.queueFamilyIndex=family;
        queueInfo.queueCount=1;
        queueInfo.pQueuePriorities=&priority;
        VkPhysicalDeviceFeatures availableFeatures{};
        vkGetPhysicalDeviceFeatures(physical,&availableFeatures);
        ensure(availableFeatures.shaderStorageImageExtendedFormats==VK_TRUE,
               "GPU nao suporta shaderStorageImageExtendedFormats (RGBA16F)");
        VkPhysicalDeviceFeatures enabledFeatures{};
        enabledFeatures.shaderStorageImageExtendedFormats=VK_TRUE;
        VkDeviceCreateInfo deviceInfo{};
        deviceInfo.sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO;
        deviceInfo.pEnabledFeatures=&enabledFeatures;
        deviceInfo.queueCreateInfoCount=1;
        deviceInfo.pQueueCreateInfos=&queueInfo;
        require(vkCreateDevice(physical,&deviceInfo,nullptr,&device),"vkCreateDevice");
        vkGetDeviceQueue(device,family,0,&queue);
        VkCommandPoolCreateInfo poolInfo{};
        poolInfo.sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO;
        poolInfo.queueFamilyIndex=family;
        require(vkCreateCommandPool(device,&poolInfo,nullptr,&commandPool),"vkCreateCommandPool");
        VkFenceCreateInfo fenceInfo{};
        fenceInfo.sType=VK_STRUCTURE_TYPE_FENCE_CREATE_INFO;
        require(vkCreateFence(device,&fenceInfo,nullptr,&fence),"vkCreateFence");
    }
    void makeImage(int index,uint32_t w,uint32_t h,VkFormat format,VkImageUsageFlags usage) {
        Image& target=images[index];
        VkImageCreateInfo ci{};
        ci.sType=VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO;
        ci.imageType=VK_IMAGE_TYPE_2D;
        ci.extent={w,h,1};
        ci.mipLevels=1;
        ci.arrayLayers=1;
        ci.format=format;
        ci.tiling=VK_IMAGE_TILING_OPTIMAL;
        ci.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED;
        ci.usage=usage | VK_IMAGE_USAGE_STORAGE_BIT;
        ci.samples=VK_SAMPLE_COUNT_1_BIT;
        ci.sharingMode=VK_SHARING_MODE_EXCLUSIVE;
        require(vkCreateImage(device,&ci,nullptr,&target.image),"vkCreateImage");
        VkMemoryRequirements req{};
        vkGetImageMemoryRequirements(device,target.image,&req);
        VkMemoryAllocateInfo memInfo{};
        memInfo.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO;
        memInfo.allocationSize=req.size;
        try { memInfo.memoryTypeIndex=memoryType(req.memoryTypeBits,VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT); }
        catch(const std::exception&) { memInfo.memoryTypeIndex=memoryType(req.memoryTypeBits,0); }
        require(vkAllocateMemory(device,&memInfo,nullptr,&target.memory),"vkAllocateMemory image");
        require(vkBindImageMemory(device,target.image,target.memory,0),"vkBindImageMemory");
        VkImageViewCreateInfo view{};
        view.sType=VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO;
        view.image=target.image;
        view.viewType=VK_IMAGE_VIEW_TYPE_2D;
        view.format=format;
        view.subresourceRange.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;
        view.subresourceRange.levelCount=1;
        view.subresourceRange.layerCount=1;
        require(vkCreateImageView(device,&view,nullptr,&target.view),"vkCreateImageView");
    }
    void makeStaging(VkDeviceSize size) {
        VkBufferCreateInfo bi{};
        bi.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
        bi.size=size;
        bi.usage=VK_BUFFER_USAGE_TRANSFER_SRC_BIT|VK_BUFFER_USAGE_TRANSFER_DST_BIT;
        bi.sharingMode=VK_SHARING_MODE_EXCLUSIVE;
        require(vkCreateBuffer(device,&bi,nullptr,&staging),"vkCreateBuffer");
        VkMemoryRequirements req{};
        vkGetBufferMemoryRequirements(device,staging,&req);
        VkMemoryAllocateInfo mi{};
        mi.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO;
        mi.allocationSize=req.size;
        mi.memoryTypeIndex=memoryType(req.memoryTypeBits,
            VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);
        require(vkAllocateMemory(device,&mi,nullptr,&stagingMemory),"vkAllocateMemory staging");
        require(vkBindBufferMemory(device,staging,stagingMemory,0),"vkBindBufferMemory");
    }
};
std::vector<uint32_t> loadSpv(JNIEnv* env,jbyteArray bytes) {
    ensure(bytes!=nullptr,"Shader SPIR-V ausente");
    const jsize length=env->GetArrayLength(bytes);
    ensure(length>=20 && (length%4)==0 && length<=8*1024*1024,
           "Shader SPIR-V invalido");
    std::vector<uint32_t> shader(size_t(length)/4);
    env->GetByteArrayRegion(bytes,0,length,reinterpret_cast<jbyte*>(shader.data()));
    ensure(!env->ExceptionCheck(),"Falha lendo SPIR-V");
    return shader;
}
VkImageMemoryBarrier transition(VkImage image,VkImageLayout from,VkImageLayout to,
                                VkAccessFlags src,VkAccessFlags dst) {
    VkImageMemoryBarrier b{};
    b.sType=VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
    b.oldLayout=from; b.newLayout=to;
    b.srcAccessMask=src; b.dstAccessMask=dst;
    b.srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;
    b.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;
    b.image=image;
    b.subresourceRange.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;
    b.subresourceRange.levelCount=1;
    b.subresourceRange.layerCount=1;
    return b;
}
void rgbaFromArgb(const std::vector<jint>& argb,uint8_t* dest) {
    for(size_t i=0;i<argb.size();++i) {
        const uint32_t v=static_cast<uint32_t>(argb[i]);
        dest[4*i+0]=uint8_t(v>>16);
        dest[4*i+1]=uint8_t(v>>8);
        dest[4*i+2]=uint8_t(v);
        dest[4*i+3]=uint8_t(v>>24);
    }
}
}

extern "C" JNIEXPORT jintArray JNICALL
Java_dev_pipa_framegen_lab_MainActivity_nativeGenerate(
    JNIEnv* env,jobject,jintArray past,jintArray now,jint width,jint height,
    jbyteArray motionShader,jbyteArray interpolateShader,jint repetitions,jint motionVariant) {
    try {
        ensure(past && now && width>0 && height>0 && width<=1920 && height<=1080,
               "Dimensoes/arrays invalidos");
        ensure(motionVariant>=0 && motionVariant<=3,"Unknown motion variant");
        ensure(repetitions==1 || repetitions==9 || repetitions==33,
               "Repeticoes validas: 1, 9 (1+8) ou 33 (1+32)");
        const size_t count=size_t(width)*size_t(height);
        ensure(size_t(env->GetArrayLength(past))==count &&
               size_t(env->GetArrayLength(now))==count,"Tamanhos ARGB incorretos");
        std::vector<jint> previous(count), current(count);
        env->GetIntArrayRegion(past,0,jsize(count),previous.data());
        env->GetIntArrayRegion(now,0,jsize(count),current.data());
        ensure(!env->ExceptionCheck(),"Falha lendo pixels");
        auto motion=loadSpv(env,motionShader);
        auto interp=loadSpv(env,interpolateShader);
        Lab lab;
        lab.initialize();
        const uint32_t w=uint32_t(width),h=uint32_t(height);
        const size_t nbytes=count*4;
        lab.makeImage(0,w,h,VK_FORMAT_R8G8B8A8_UNORM,VK_IMAGE_USAGE_TRANSFER_DST_BIT);
        lab.makeImage(1,w,h,VK_FORMAT_R8G8B8A8_UNORM,VK_IMAGE_USAGE_TRANSFER_DST_BIT);
        lab.makeImage(2,(w+15)/16,(h+15)/16,VK_FORMAT_R16G16B16A16_SFLOAT,0);
        lab.makeImage(3,w,h,VK_FORMAT_R8G8B8A8_UNORM,VK_IMAGE_USAGE_TRANSFER_SRC_BIT);
        lab.makeStaging(VkDeviceSize(nbytes*3));
        void* mapped=nullptr;
        require(vkMapMemory(lab.device,lab.stagingMemory,0,nbytes*3,0,&mapped),"vkMapMemory");
        uint8_t* data=static_cast<uint8_t*>(mapped);
        rgbaFromArgb(previous,data);
        rgbaFromArgb(current,data+nbytes);
        vkUnmapMemory(lab.device,lab.stagingMemory);
        const uint32_t flags=motionVariant==2 ?
            PIPA_FRAMEGEN_VK_MOTION_GROUP_PER_TILE : 0u;
        const int create=pipa_framegen_vk_create_ex(lab.physical,lab.device,
            motion.data(),motion.size()*4,interp.data(),interp.size()*4,flags,&lab.engine);
        ensure(create==0,("Nao foi possivel criar pipeline FrameGen Vulkan (ret="+std::to_string(create)+")").c_str());

        VkCommandBufferAllocateInfo alloc{};
        alloc.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
        alloc.commandPool=lab.commandPool;
        alloc.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY;
        alloc.commandBufferCount=1;
        VkCommandBuffer cmd=VK_NULL_HANDLE;
        require(vkAllocateCommandBuffers(lab.device,&alloc,&cmd),"vkAllocateCommandBuffers");
        VkCommandBufferBeginInfo begin{};
        begin.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
        begin.flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
        require(vkBeginCommandBuffer(cmd,&begin),"vkBeginCommandBuffer");
        const bool canTimestamp = lab.timestampBits>0 && lab.timestampPeriodNs>0.0;
        const uint32_t timedSamples=uint32_t(repetitions==1 ? 1 : repetitions-1);
        if(canTimestamp) {
            VkQueryPoolCreateInfo qi{};
            qi.sType=VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO;
            qi.queryType=VK_QUERY_TYPE_TIMESTAMP;
            qi.queryCount=timedSamples*3u;
            if(vkCreateQueryPool(lab.device,&qi,nullptr,&lab.timestampQueries)==VK_SUCCESS)
                vkCmdResetQueryPool(cmd,lab.timestampQueries,0,qi.queryCount);
        }
        VkImageMemoryBarrier barriers[4]{};
        for(int i=0;i<4;++i) {
            if(i<2) barriers[i]=transition(lab.images[i].image,
                VK_IMAGE_LAYOUT_UNDEFINED,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,0,VK_ACCESS_TRANSFER_WRITE_BIT);
            else barriers[i]=transition(lab.images[i].image,
                VK_IMAGE_LAYOUT_UNDEFINED,VK_IMAGE_LAYOUT_GENERAL,0,
                VK_ACCESS_SHADER_READ_BIT|VK_ACCESS_SHADER_WRITE_BIT);
        }
        vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
            VK_PIPELINE_STAGE_TRANSFER_BIT|VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
            0,0,nullptr,0,nullptr,4,barriers);
        VkBufferImageCopy region{};
        region.imageSubresource.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;
        region.imageSubresource.layerCount=1;
        region.imageExtent={w,h,1};
        for(int i=0;i<2;++i) {
            region.bufferOffset=VkDeviceSize(size_t(i)*nbytes);
            vkCmdCopyBufferToImage(cmd,lab.staging,lab.images[i].image,
                VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,1,&region);
        }
        VkImageMemoryBarrier ready[2]{};
        for(int i=0;i<2;++i)ready[i]=transition(lab.images[i].image,
            VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,VK_IMAGE_LAYOUT_GENERAL,
            VK_ACCESS_TRANSFER_WRITE_BIT,VK_ACCESS_SHADER_READ_BIT);
        vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_TRANSFER_BIT,
                             VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,0,0,nullptr,
                             0,nullptr,2,ready);
        const PipaFramegenVkImages inputs{
            lab.images[0].view,lab.images[1].view,lab.images[2].view,
            lab.images[3].view,lab.images[2].image};
        for(int sample=0;sample<repetitions;++sample) {
            // Reuse the initialized pipelines/images. Warmup is not included in stats.
            // Barriers make repeat writes to flow/output visible and ordered.
            if(sample>0) {
                VkMemoryBarrier between{};
                between.sType=VK_STRUCTURE_TYPE_MEMORY_BARRIER;
                between.srcAccessMask=VK_ACCESS_SHADER_READ_BIT|VK_ACCESS_SHADER_WRITE_BIT;
                between.dstAccessMask=VK_ACCESS_SHADER_READ_BIT|VK_ACCESS_SHADER_WRITE_BIT;
                vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                                     VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                                     0,1,&between,0,nullptr,0,nullptr);
            }
            const bool measure=repetitions==1 || sample>0;
            const uint32_t queryBase=uint32_t(repetitions==1 ? 0 : sample-1)*3u;
            const int recorded=pipa_framegen_vk_record_profiled(lab.engine,cmd,&inputs,w,h,
                0.5f,4,0.75f,measure ? lab.timestampQueries : VK_NULL_HANDLE,queryBase);
            ensure(recorded==0,"Falha ao gravar dispatch de interpolacao");
        }
        VkImageMemoryBarrier outputBarrier=transition(lab.images[3].image,
            VK_IMAGE_LAYOUT_GENERAL,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,
            VK_ACCESS_SHADER_WRITE_BIT,VK_ACCESS_TRANSFER_READ_BIT);
        vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                             VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,nullptr,
                             0,nullptr,1,&outputBarrier);
        region.bufferOffset=VkDeviceSize(nbytes*2);
        vkCmdCopyImageToBuffer(cmd,lab.images[3].image,
            VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,lab.staging,1,&region);
        VkBufferMemoryBarrier hostBarrier{};
        hostBarrier.sType=VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER;
        hostBarrier.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;
        hostBarrier.dstAccessMask=VK_ACCESS_HOST_READ_BIT;
        hostBarrier.srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;
        hostBarrier.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;
        hostBarrier.buffer=lab.staging;
        hostBarrier.offset=VkDeviceSize(2*nbytes);
        hostBarrier.size=VkDeviceSize(nbytes);
        vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_TRANSFER_BIT,
            VK_PIPELINE_STAGE_HOST_BIT,0,0,nullptr,1,&hostBarrier,0,nullptr);
        require(vkEndCommandBuffer(cmd),"vkEndCommandBuffer");
        VkSubmitInfo submit{};
        submit.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO;
        submit.commandBufferCount=1;
        submit.pCommandBuffers=&cmd;
        const auto t0=std::chrono::steady_clock::now();
        require(vkQueueSubmit(lab.queue,1,&submit,lab.fence),"vkQueueSubmit");
        require(vkWaitForFences(lab.device,1,&lab.fence,VK_TRUE,UINT64_C(10000000000)),
                "vkWaitForFences timeout/erro");
        const auto t1=std::chrono::steady_clock::now();
        double wallMs=std::chrono::duration<double,std::milli>(t1-t0).count();
        std::string gpuTime=" | GPU timestamps: indisponiveis";
        if(lab.timestampQueries) {
            std::vector<uint64_t> ticks(size_t(timedSamples)*3u,0);
            VkResult q=vkGetQueryPoolResults(lab.device,lab.timestampQueries,0,
                    timedSamples*3u,ticks.size()*sizeof(uint64_t),ticks.data(),
                    sizeof(uint64_t),VK_QUERY_RESULT_64_BIT|VK_QUERY_RESULT_WAIT_BIT);
            if(q==VK_SUCCESS) {
                std::vector<double> motionMs,warpMs,totalMs;
                motionMs.reserve(timedSamples);warpMs.reserve(timedSamples);
                totalMs.reserve(timedSamples);
                const uint64_t mask=lab.timestampBits>=64 ? UINT64_MAX :
                                   (uint64_t(1)<<lab.timestampBits)-1u;
                for(uint32_t i=0;i<timedSamples;++i) {
                    const size_t offset=size_t(i)*3u;
                    const uint64_t a=(ticks[offset+1]-ticks[offset])&mask;
                    const uint64_t b=(ticks[offset+2]-ticks[offset+1])&mask;
                    motionMs.push_back(double(a)*lab.timestampPeriodNs/1.0e6);
                    warpMs.push_back(double(b)*lab.timestampPeriodNs/1.0e6);
                    totalMs.push_back(double((a+b)&mask)*lab.timestampPeriodNs/1.0e6);
                }
                const auto format=[](std::vector<double>& numbers) -> std::string {
                    std::sort(numbers.begin(),numbers.end());
                    double sum=0.0;
                    for(double value:numbers) sum+=value;
                    const size_t p50=(numbers.size()-1u)/2u;
                    const size_t p95=(numbers.size()*95u+99u)/100u-1u;
                    return "avg="+std::to_string(sum/numbers.size())+
                        ",p50="+std::to_string(numbers[p50])+
                        ",p95="+std::to_string(numbers[p95])+"ms";
                };
                gpuTime=" | GPU n="+std::to_string(timedSamples)+
                        " | Motion "+format(motionMs)+
                        " | Warp+barreira "+format(warpMs)+
                        " | Total "+format(totalMs);
            } else {
                gpuTime=" | GPU timestamps erro "+std::to_string(int(q));
            }
        }
        require(vkMapMemory(lab.device,lab.stagingMemory,0,nbytes*3,0,&mapped),"vkMapMemory read");
        const uint8_t* rgba=static_cast<const uint8_t*>(mapped)+nbytes*2;
        std::vector<jint> pixels(count);
        for(size_t i=0;i<count;++i) {
            const uint32_t a=rgba[4*i+3],r=rgba[4*i+0],
                           g=rgba[4*i+1],b=rgba[4*i+2];
            pixels[i]=jint((a<<24)|(r<<16)|(g<<8)|b);
        }
        vkUnmapMemory(lab.device,lab.stagingMemory);
        jintArray result=env->NewIntArray(jsize(count));
        ensure(result!=nullptr,"Sem memoria para resultado JNI");
        env->SetIntArrayRegion(result,0,jsize(count),pixels.data());
        set_report(lab.gpuName+" | "+std::to_string(repetitions)+
                   " passagens | submissao+espera="+
                   std::to_string(wallMs)+" ms (CPU wall-clock)"+gpuTime);
        return result;
    } catch(const std::exception& ex) {
        set_report(std::string("ERROR: ")+ex.what());
        return nullptr;
    }
}

extern "C" JNIEXPORT jstring JNICALL
Java_dev_pipa_framegen_lab_MainActivity_nativeReport(JNIEnv* env,jobject) {
    std::lock_guard<std::mutex> lock(report_mutex);
    return env->NewStringUTF(report.c_str());
}
