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
#include <dlfcn.h>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {
std::atomic<bool> g_stop{false};
std::atomic<bool> g_inUse{false};
constexpr uint32_t kWidth=1280, kHeight=720;
// EXP29.26 diagnostic load: repeat the identical source scene only while the GPU Guard is active.
constexpr uint32_t kGpuBudgetValidationSceneRepeatPasses=4u;
constexpr char kPipaTraceLayerName[]="VK_LAYER_PIPA_present_trace";
constexpr char kPipaTraceLayerLibrary[]="libVkLayer_PIPA_present_trace.so";
using PipaTraceResetFn=void (*)();
using PipaTraceGetStatsFn=void (*)(uint64_t*,uint64_t*,uint64_t*,uint64_t*);

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

    VkDescriptorSetLayout sceneSetLayout=VK_NULL_HANDLE;
    VkPipelineLayout scenePipelineLayout=VK_NULL_HANDLE;
    VkPipeline scenePipeline=VK_NULL_HANDLE;
    VkDescriptorPool sceneDescriptorPool=VK_NULL_HANDLE;
    VkDescriptorSet sceneDescriptors[2]={VK_NULL_HANDLE,VK_NULL_HANDLE};
    uint32_t sceneRealSubmitted=0,sceneGeneratedSubmitted=0,sceneHeldSubmitted=0,deadlineMisses=0;
    void createScenePipeline(const std::vector<uint32_t>& spv) {
        VkDescriptorSetLayoutBinding binding{};
        binding.binding=0;binding.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;
        binding.descriptorCount=1;binding.stageFlags=VK_SHADER_STAGE_COMPUTE_BIT;
        VkDescriptorSetLayoutCreateInfo dl{};
        dl.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO;
        dl.bindingCount=1;dl.pBindings=&binding;
        check(vkCreateDescriptorSetLayout(device,&dl,nullptr,&sceneSetLayout),"Scene set layout");
        VkPushConstantRange push{};
        push.stageFlags=VK_SHADER_STAGE_COMPUTE_BIT;push.size=16;
        VkPipelineLayoutCreateInfo pl{};
        pl.sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO;
        pl.setLayoutCount=1;pl.pSetLayouts=&sceneSetLayout;
        pl.pushConstantRangeCount=1;pl.pPushConstantRanges=&push;
        check(vkCreatePipelineLayout(device,&pl,nullptr,&scenePipelineLayout),"Scene layout");
        VkShaderModuleCreateInfo sm{};
        sm.sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO;
        sm.codeSize=spv.size()*sizeof(uint32_t);sm.pCode=spv.data();
        VkShaderModule shader=VK_NULL_HANDLE;
        check(vkCreateShaderModule(device,&sm,nullptr,&shader),"Scene module");
        VkComputePipelineCreateInfo pi{};
        pi.sType=VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO;
        pi.layout=scenePipelineLayout;
        pi.stage.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
        pi.stage.stage=VK_SHADER_STAGE_COMPUTE_BIT;
        pi.stage.module=shader;pi.stage.pName="main";
        VkResult result=vkCreateComputePipelines(device,VK_NULL_HANDLE,1,&pi,
                                                   nullptr,&scenePipeline);
        vkDestroyShaderModule(device,shader,nullptr);
        check(result,"Scene pipeline");
        VkDescriptorPoolSize ps{};
        ps.type=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;ps.descriptorCount=2;
        VkDescriptorPoolCreateInfo pc{};
        pc.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO;
        pc.maxSets=2;pc.poolSizeCount=1;pc.pPoolSizes=&ps;
        check(vkCreateDescriptorPool(device,&pc,nullptr,&sceneDescriptorPool),"Scene pool");
        VkDescriptorSetLayout layouts[]={sceneSetLayout,sceneSetLayout};
        VkDescriptorSetAllocateInfo ai{};
        ai.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO;
        ai.descriptorPool=sceneDescriptorPool;
        ai.descriptorSetCount=2;ai.pSetLayouts=layouts;
        check(vkAllocateDescriptorSets(device,&ai,sceneDescriptors),"Scene sets");
        VkDescriptorImageInfo infos[2]{};
        VkWriteDescriptorSet writes[2]{};
        for(int i=0;i<2;++i) {
            infos[i].imageView=tex[i].view;
            infos[i].imageLayout=VK_IMAGE_LAYOUT_GENERAL;
            writes[i].sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
            writes[i].dstSet=sceneDescriptors[i];writes[i].descriptorCount=1;
            writes[i].descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;
            writes[i].pImageInfo=&infos[i];
        }
        vkUpdateDescriptorSets(device,2,writes,0,nullptr);
    }
    void recordSourceScene(VkCommandBuffer cmd,uint32_t pairIndex) {
        expect(scenePipeline!=VK_NULL_HANDLE,"Scene pipeline unavailable");
        VkImageMemoryBarrier start[2]{};
        for(int i=0;i<2;++i)
            start[i]=imageBarrier(tex[i].image,VK_IMAGE_LAYOUT_GENERAL,
                     VK_IMAGE_LAYOUT_GENERAL,
                     VK_ACCESS_SHADER_READ_BIT|VK_ACCESS_TRANSFER_READ_BIT,
                     VK_ACCESS_SHADER_WRITE_BIT);
        vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT|
             VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
             0,0,nullptr,0,nullptr,2,start);
        vkCmdBindPipeline(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,scenePipeline);
        struct Params {int32_t w,h,id,pad;};
        for(int i=0;i<2;++i) {
            Params push{int32_t(kWidth),int32_t(kHeight),int32_t(pairIndex+i),0};
            vkCmdBindDescriptorSets(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,
                 scenePipelineLayout,0,1,&sceneDescriptors[i],0,nullptr);
            vkCmdPushConstants(cmd,scenePipelineLayout,VK_SHADER_STAGE_COMPUTE_BIT,
                               0,sizeof(push),&push);
            vkCmdDispatch(cmd,(kWidth+15)/16,(kHeight+15)/16,1);
        }
        VkImageMemoryBarrier ready[2]{};
        for(int i=0;i<2;++i)
            ready[i]=imageBarrier(tex[i].image,VK_IMAGE_LAYOUT_GENERAL,
                     VK_IMAGE_LAYOUT_GENERAL,VK_ACCESS_SHADER_WRITE_BIT,
                     VK_ACCESS_SHADER_READ_BIT);
        vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
             VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,0,0,nullptr,0,nullptr,2,ready);
    }

    VkPhysicalDeviceMemoryProperties memory{};
    std::string gpuName;
    bool useBlit=true;
    bool fitAspect=false;
    uint32_t fitWidth=0,fitHeight=0;
    VkSurfaceTransformFlagBitsKHR chosenTransform=VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR;
    VkSurfaceTransformFlagBitsKHR currentTransform=VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR;
    VkSurfaceTransformFlagsKHR supportedTransforms=0;
    bool requestedIdentity3d=false;
    bool identity3dAccepted=false;
    bool displayTimingEnabled=false;
    PFN_vkGetPastPresentationTimingGOOGLE getPastTiming=nullptr;
    PFN_vkGetRefreshCycleDurationGOOGLE getRefreshDuration=nullptr;
    uint64_t refreshPeriodNs=0;
    std::map<uint32_t,uint64_t> reportedActualNs;
    std::vector<double> presentCallMs;
    uint32_t timingQueryFailures=0;
    VkQueryPool gpuQueryPool=VK_NULL_HANDLE;
    uint32_t timestampValidBits=0;
    float timestampPeriodNs=0.0f;
    int pendingGpuRole=-1;
    std::vector<double> realGpuMs;
    std::vector<double> generatedGpuMs;
    std::vector<double> motionGpuMs, warpGpuMs;
    uint32_t gpuTimingReadFailures=0;
    uint32_t splitTimingFailures=0;
    int recordedMotionRadius=4;
    // EXP29.25: the FG cadence consists of TWO presentation periods.
    // The prior single-slot 85% test dropped 480 of 720 interpolated frames
    // despite zero CPU late periods. Aggregate a *completed* original+FG pair
    // before making a conservative, three-strike decision. No single-frame
    // interpolation budget threshold is inferred from a WSI monitor cycle.
    void* traceLayerLibrary=nullptr;
    PipaTraceResetFn traceLayerReset=nullptr;
    PipaTraceGetStatsFn traceLayerGetStats=nullptr;
    bool traceLayerAvailable=false, traceLayerActive=false;
    uint32_t topLevelSuboptimal=0, perSwapchainSuboptimal=0, presentResultMismatches=0;
    VkResult lastTopLevelPresentResult=VK_SUCCESS;
    VkResult lastPerSwapchainPresentResult=VK_SUCCESS;
    bool surfaceCapsQueriedAfterSuboptimal=false;
    bool surfaceCapsAvailableAfterSuboptimal=false;
    uint32_t surfaceCapsQueryFailures=0;
    VkExtent2D surfaceCurrentExtentAfterSuboptimal{};
    VkSurfaceTransformFlagBitsKHR surfaceCurrentTransformAfterSuboptimal=
        VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR;
    bool gpuBudgetRequested=false, gpuBudgetEnabled=false;
    double gpuBudgetMs=0.0, lastPairGpuMs=0.0;
    double pendingPairRealGpuMs=0.0;
    bool pendingPairRealAvailable=false;
    uint32_t gpuBudgetOverruns=0, gpuBudgetHeld=0, gpuBudgetProbeFrames=0;
    uint32_t gpuBudgetHoldCountdown=0, gpuBudgetOverrunStreak=0;
    uint32_t gpuBudgetGovernorTrips=0, gpuBudgetMissingPairs=0;
    std::vector<double> gpuPairMs;
    std::string traceLayerSummary() const {
        if(!traceLayerAvailable)return " | VK_LAYER_PIPA available=0 active=0";
        if(!traceLayerActive || traceLayerGetStats==nullptr)
            return " | VK_LAYER_PIPA available=1 active=0";
        uint64_t calls=0,success=0,suboptimal=0,errors=0;
        traceLayerGetStats(&calls,&success,&suboptimal,&errors);
        return " | VK_LAYER_PIPA available=1 active=1 presents="+
            std::to_string(calls)+" success="+std::to_string(success)+
            " suboptimal="+std::to_string(suboptimal)+" errors="+std::to_string(errors);
    }
    void querySurfaceAfterSuboptimal() {
        if(surfaceCapsQueriedAfterSuboptimal)return;
        surfaceCapsQueriedAfterSuboptimal=true;
        VkSurfaceCapabilitiesKHR caps{};
        VkResult result=vkGetPhysicalDeviceSurfaceCapabilitiesKHR(physical,surface,&caps);
        if(result!=VK_SUCCESS) {
            ++surfaceCapsQueryFailures;
            return;
        }
        surfaceCapsAvailableAfterSuboptimal=true;
        surfaceCurrentExtentAfterSuboptimal=caps.currentExtent;
        surfaceCurrentTransformAfterSuboptimal=caps.currentTransform;
    }
    std::string surfaceDiagnosticSummary() const {
        if(!surfaceCapsQueriedAfterSuboptimal)
            return " | WSI suboptimal diagnostic: none";
        return " | WSI topSuboptimal="+std::to_string(topLevelSuboptimal)+
            " perSwapchainSuboptimal="+std::to_string(perSwapchainSuboptimal)+
            " resultMismatch="+std::to_string(presentResultMismatches)+
            " lastTop="+std::to_string(int(lastTopLevelPresentResult))+
            " lastPerSwapchain="+std::to_string(int(lastPerSwapchainPresentResult))+
            " surfaceCapsAfterSuboptimal="+
            std::to_string(surfaceCapsAvailableAfterSuboptimal?1:0)+
            " currentExtent="+std::to_string(surfaceCurrentExtentAfterSuboptimal.width)+
            "x"+std::to_string(surfaceCurrentExtentAfterSuboptimal.height)+
            " currentTransform="+std::to_string(uint32_t(surfaceCurrentTransformAfterSuboptimal))+
            " selectedPreTransform="+std::to_string(uint32_t(chosenTransform))+
            " queryFailures="+std::to_string(surfaceCapsQueryFailures);
    }

    // CPU measurements are deliberately separated from GPU timestamps and
    // driver WSI presentation times. Each metric has a different clock path.
    std::vector<double> wakeLateMs, fenceWaitMs, acquireWaitMs, submitCallMs;
    uint32_t inheritedLateOnePeriod=0, timerOversleepOnePeriod=0;
    uint32_t lateBurstCurrent=0, lateBurstLongest=0;
    bool refreshAligned=false;
    uint64_t selectedPacingPeriodNs=0;

    static std::string cpuDistribution(const std::vector<double>& values,
                                       const char* name) {
        if(values.empty())return std::string(" | ")+name+" indisponivel";
        std::vector<double> sorted=values;
        std::sort(sorted.begin(),sorted.end());
        const size_t p95=(sorted.size()*95u+99u)/100u-1u;
        const size_t p99=(sorted.size()*99u+99u)/100u-1u;
        double sum=0;
        for(double v:sorted)sum+=v;
        return std::string(" | ")+name+" media="+
               std::to_string(sum/sorted.size())+"ms p95="+
               std::to_string(sorted[p95])+"ms p99="+
               std::to_string(sorted[p99])+"ms max="+
               std::to_string(sorted.back())+"ms";
    }

    std::string cpuPacingSummary() const {
        const size_t n=wakeLateMs.size();
        return std::string(" | CPU pacing=")+(refreshAligned?"WSI_SYNC":"FIXED_REQUEST")+
          " periodo="+std::to_string(double(selectedPacingPeriodNs)/1.e6)+"ms"+
          " | inicios >1 periodo="+std::to_string(deadlineMisses)+
          "/"+std::to_string(n)+
          " | atraso herdado antes sleep="+std::to_string(inheritedLateOnePeriod)+
          " | atraso novo apos sleep="+std::to_string(timerOversleepOnePeriod)+
          " | maior sequencia atrasada="+std::to_string(lateBurstLongest)+
          cpuDistribution(wakeLateMs,"CPU wake lateness")+
          cpuDistribution(fenceWaitMs,"CPU fence wait")+
          cpuDistribution(acquireWaitMs,"CPU acquire wait")+
          cpuDistribution(submitCallMs,"CPU submit call");
    }


    // These GPU timestamps bracket scene compute, FG, image blit and
    // image-layout transitions; they do NOT measure compositor/scanout time.
    void harvestGpuTimestamps() {
        if(!gpuQueryPool || pendingGpuRole<0)return;
        const int role=pendingGpuRole;
        // Every new original starts a fresh pair. A failed query must never
        // reuse a successful timestamp from a previous pair.
        if(role==0 && gpuBudgetEnabled)pendingPairRealAvailable=false;
        uint64_t values[2]{};
        VkResult r=vkGetQueryPoolResults(device,gpuQueryPool,0,2,sizeof(values),
                    values,sizeof(uint64_t),VK_QUERY_RESULT_64_BIT);
        bool sampleValid=false;
        double ms=0.0;
        if(r==VK_SUCCESS) {
            uint64_t ticks=(values[1]-values[0]);
            if(timestampValidBits<64)
                ticks&=((uint64_t(1)<<timestampValidBits)-1u);
            ms=double(ticks)*double(timestampPeriodNs)*1.e-6;
            if(ms>=0.0 && std::isfinite(ms) && ms<10000.0) {
                sampleValid=true;
                if(role==1) generatedGpuMs.push_back(ms);
                else {
                    realGpuMs.push_back(ms);
                    if(gpuBudgetEnabled) {
                        pendingPairRealGpuMs=ms;
                        pendingPairRealAvailable=true;
                    }
                }
            } else ++gpuTimingReadFailures;
        } else ++gpuTimingReadFailures;
        if(gpuBudgetEnabled && role==1) {
            if(!sampleValid || !pendingPairRealAvailable) {
                ++gpuBudgetMissingPairs;
                gpuBudgetOverrunStreak=0;
            } else {
                const double pairMs=pendingPairRealGpuMs+ms;
                lastPairGpuMs=pairMs;
                gpuPairMs.push_back(pairMs);
                ++gpuBudgetProbeFrames;
                if(pairMs>gpuBudgetMs) {
                    ++gpuBudgetOverruns;
                    ++gpuBudgetOverrunStreak;
                    if(gpuBudgetOverrunStreak>=3u) {
                        // One held synthetic slot per three
                        // consecutive overloaded completed pairs.
                        gpuBudgetHoldCountdown=1u;
                        ++gpuBudgetGovernorTrips;
                        gpuBudgetOverrunStreak=0u;
                    }
                } else gpuBudgetOverrunStreak=0u;
            }
            pendingPairRealAvailable=false;
        }
        if(role==1) {
            uint64_t parts[3]{};
            VkResult split=vkGetQueryPoolResults(device,gpuQueryPool,2,3,
               sizeof(parts),parts,sizeof(uint64_t),VK_QUERY_RESULT_64_BIT);
            if(split==VK_SUCCESS) {
                const uint64_t mask=timestampValidBits<64?
                    ((uint64_t(1)<<timestampValidBits)-1u):~uint64_t(0);
                const uint64_t motionTicks=(parts[1]-parts[0])&mask;
                const uint64_t warpTicks=(parts[2]-parts[1])&mask;
                const double motionMs=double(motionTicks)*timestampPeriodNs*1.e-6;
                const double warpMs=double(warpTicks)*timestampPeriodNs*1.e-6;
                if(std::isfinite(motionMs) && std::isfinite(warpMs) &&
                   motionMs<10000.0 && warpMs<10000.0) {
                    motionGpuMs.push_back(motionMs);
                    warpGpuMs.push_back(warpMs);
                } else ++splitTimingFailures;
            } else ++splitTimingFailures;
        }
        pendingGpuRole=-1;
    }
    std::string gpuTimingSummary() const {
        if(!gpuQueryPool)return " | GPU timestamps: indisponiveis";
        auto summary=[](const std::vector<double>& values,const char* prefix) {
            if(values.empty())return std::string(" | ")+prefix+" sem amostras";
            std::vector<double> sorted=values;
            std::sort(sorted.begin(),sorted.end());
            double total=0;
            for(double v:sorted)total+=v;
            const size_t p95=(sorted.size()*95u+99u)/100u-1u;
            return std::string(" | ")+prefix+" n="+std::to_string(sorted.size())+
                " media="+std::to_string(total/sorted.size())+
                "ms p95="+std::to_string(sorted[p95])+"ms";
        };
        return summary(realGpuMs,"GPU original+blit")+
               summary(generatedGpuMs,"GPU gerado+blit")+
               summary(gpuPairMs,"GPU par real+FG")+
               summary(motionGpuMs,"GPU Motion")+
               summary(warpGpuMs,"GPU Warp+barreira")+
               " | Motion raio="+std::to_string(recordedMotionRadius)+
               " | falhas GPU query="+std::to_string(gpuTimingReadFailures)+
               " | falhas GPU split="+std::to_string(splitTimingFailures);
    }


    void collectTiming() {
        if(!displayTimingEnabled || !getPastTiming) return;
        uint32_t count=0;
        VkResult q=getPastTiming(device,swap,&count,nullptr);
        if(q!=VK_SUCCESS) { ++timingQueryFailures;return; }
        if(count==0) return;
        std::vector<VkPastPresentationTimingGOOGLE> records(count);
        q=getPastTiming(device,swap,&count,records.data());
        if(q!=VK_SUCCESS && q!=VK_INCOMPLETE) { ++timingQueryFailures;return; }
        for(uint32_t i=0;i<count;++i)
            if(records[i].actualPresentTime>0)
                reportedActualNs[records[i].presentID]=records[i].actualPresentTime;
    }
    std::string timingSummary() {
        if(!displayTimingEnabled || !getPastTiming)
            return " | timing WSI: VK_GOOGLE_display_timing indisponivel";
        collectTiming();
        const uint32_t accepted=sceneRealSubmitted+
                        sceneGeneratedSubmitted+sceneHeldSubmitted;
        std::string result=" | VK_GOOGLE_display_timing: "+
            std::to_string(reportedActualNs.size())+" amostras reais reportadas"+
            " | cobertura WSI="+
            (accepted?std::to_string(100.0*double(reportedActualNs.size())/accepted):
                       std::string("0"))+"% dos presents aceitos";
        if(refreshPeriodNs>0)
            result+=" | ciclo monitor reportado="+
                std::to_string(double(refreshPeriodNs)/1.e6)+"ms";
        if(reportedActualNs.size()<2) {
            result+=" | taxa fisica nao determinada";
        } else {
            std::vector<double> intervals;
            uint32_t previousId=0;
            uint64_t previousTime=0;
            for(const auto& pair:reportedActualNs) {
                if(previousTime>0 && pair.first==previousId+1u &&
                   pair.second>previousTime)
                    intervals.push_back(double(pair.second-previousTime)/1.e6);
                previousId=pair.first;
                previousTime=pair.second;
            }
            if(!intervals.empty()) {
                std::sort(intervals.begin(),intervals.end());
                double total=0.0;
                for(double v:intervals)total+=v;
                double avg=total/intervals.size();
                size_t p50=(intervals.size()*50u+99u)/100u-1u;
                size_t p95=(intervals.size()*95u+99u)/100u-1u;
                size_t p99=(intervals.size()*99u+99u)/100u-1u;
                result+=" | intervalos consecutivos n="+std::to_string(intervals.size())+
                    " media="+std::to_string(avg)+"ms"+
                    " p50="+std::to_string(intervals[p50])+"ms"+
                    " p95="+std::to_string(intervals[p95])+"ms"+
                    " p99="+std::to_string(intervals[p99])+"ms"+
                    " max="+std::to_string(intervals.back())+"ms"+
                    " cadencia reportada="+std::to_string(1000.0/avg)+"Hz";
                if(refreshPeriodNs>0) {
                    uint32_t longIntervals=0;
                    const double threshold=1.5*double(refreshPeriodNs)/1.e6;
                    for(double v:intervals)if(v>threshold)++longIntervals;
                    result+=" | intervalos >1.5 ciclos="+
                        std::to_string(longIntervals)+"/"+
                        std::to_string(intervals.size());
                }
            } else result+=" | sem pares consecutivos validos";
        }
        if(timingQueryFailures)
            result+=" | falhas consultas="+std::to_string(timingQueryFailures);
        if(!presentCallMs.empty()) {
            std::vector<double> sorted=presentCallMs;
            std::sort(sorted.begin(),sorted.end());
            size_t p95=(sorted.size()*95u+99u)/100u-1u;
            result+=" | CPU vkQueuePresentKHR p95="+
                    std::to_string(sorted[p95])+"ms";
        }
        return result;
    }
    ~Presenter() {
        if(device) vkDeviceWaitIdle(device);
        if(device && gpuQueryPool)vkDestroyQueryPool(device,gpuQueryPool,nullptr);
        if(engine) pipa_framegen_vk_destroy(engine);
        if(device) {
            if(scenePipeline)vkDestroyPipeline(device,scenePipeline,nullptr);
            if(sceneDescriptorPool)vkDestroyDescriptorPool(device,sceneDescriptorPool,nullptr);
            if(scenePipelineLayout)vkDestroyPipelineLayout(device,scenePipelineLayout,nullptr);
            if(sceneSetLayout)vkDestroyDescriptorSetLayout(device,sceneSetLayout,nullptr);
        }
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
        if(traceLayerLibrary)dlclose(traceLayerLibrary);
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
              const std::vector<uint32_t>& motion,const std::vector<uint32_t>& warp,
              const std::vector<uint32_t>& scene,bool continuous,
              bool preferIdentityFor3D) {
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
        traceLayerLibrary=dlopen(kPipaTraceLayerLibrary,RTLD_NOW|RTLD_LOCAL);
        if(traceLayerLibrary!=nullptr) {
            traceLayerReset=reinterpret_cast<PipaTraceResetFn>(
                dlsym(traceLayerLibrary,"pipa_vk_layer_reset_stats"));
            traceLayerGetStats=reinterpret_cast<PipaTraceGetStatsFn>(
                dlsym(traceLayerLibrary,"pipa_vk_layer_get_stats"));
            if(traceLayerReset!=nullptr)traceLayerReset();
        }
        uint32_t layerCount=0;
        VkResult layerEnum=vkEnumerateInstanceLayerProperties(&layerCount,nullptr);
        if(layerEnum==VK_SUCCESS && layerCount>0) {
            std::vector<VkLayerProperties> layerProperties(layerCount);
            layerEnum=vkEnumerateInstanceLayerProperties(&layerCount,layerProperties.data());
            if(layerEnum==VK_SUCCESS || layerEnum==VK_INCOMPLETE) {
                for(const auto& property:layerProperties) {
                    if(std::strcmp(property.layerName,kPipaTraceLayerName)==0) {
                        traceLayerAvailable=true;
                        break;
                    }
                }
            }
        }
        traceLayerActive=traceLayerAvailable && traceLayerLibrary!=nullptr &&
                         traceLayerReset!=nullptr && traceLayerGetStats!=nullptr;
        const char* enabledLayers[]={kPipaTraceLayerName};
        if(traceLayerActive) {
            ci.enabledLayerCount=1;
            ci.ppEnabledLayerNames=enabledLayers;
        }
        VkResult instanceResult=vkCreateInstance(&ci,nullptr,&instance);
        if(instanceResult!=VK_SUCCESS && traceLayerActive) {
            traceLayerActive=false;
            ci.enabledLayerCount=0;
            ci.ppEnabledLayerNames=nullptr;
            instanceResult=vkCreateInstance(&ci,nullptr,&instance);
        }
        check(instanceResult,"vkCreateInstance");
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
        timestampPeriodNs=gpuProps.limits.timestampPeriod;
        uint32_t selectedFamilyCount=0;
        vkGetPhysicalDeviceQueueFamilyProperties(physical,&selectedFamilyCount,nullptr);
        std::vector<VkQueueFamilyProperties> selectedFamilies(selectedFamilyCount);
        vkGetPhysicalDeviceQueueFamilyProperties(physical,&selectedFamilyCount,
                                                   selectedFamilies.data());
        timestampValidBits=selectedFamilies[family].timestampValidBits;
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
        uint32_t extCount=0;
        check(vkEnumerateDeviceExtensionProperties(physical,nullptr,&extCount,nullptr),
              "Enumerate device extension count");
        std::vector<VkExtensionProperties> extensions(extCount);
        check(vkEnumerateDeviceExtensionProperties(physical,nullptr,&extCount,
              extensions.data()),"Enumerate device extensions");
        for(const auto& ext:extensions) {
            if(std::strcmp(ext.extensionName,VK_GOOGLE_DISPLAY_TIMING_EXTENSION_NAME)==0)
                displayTimingEnabled=true;
        }
        std::vector<const char*> deviceExts{VK_KHR_SWAPCHAIN_EXTENSION_NAME};
        if(displayTimingEnabled)
            deviceExts.push_back(VK_GOOGLE_DISPLAY_TIMING_EXTENSION_NAME);
        VkDeviceCreateInfo di{};
        di.sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO;
        di.queueCreateInfoCount=1;di.pQueueCreateInfos=&qi;
        di.enabledExtensionCount=static_cast<uint32_t>(deviceExts.size());
        di.ppEnabledExtensionNames=deviceExts.data();
        di.pEnabledFeatures=&enabled;
        check(vkCreateDevice(physical,&di,nullptr,&device),"vkCreateDevice swapchain");
        vkGetDeviceQueue(device,family,0,&queue);
        if(displayTimingEnabled) {
            getPastTiming=reinterpret_cast<PFN_vkGetPastPresentationTimingGOOGLE>(
                vkGetDeviceProcAddr(device,"vkGetPastPresentationTimingGOOGLE"));
            getRefreshDuration=reinterpret_cast<PFN_vkGetRefreshCycleDurationGOOGLE>(
                vkGetDeviceProcAddr(device,"vkGetRefreshCycleDurationGOOGLE"));
            if(!getPastTiming || !getRefreshDuration) displayTimingEnabled=false;
        }

        VkSurfaceCapabilitiesKHR caps{};
        check(vkGetPhysicalDeviceSurfaceCapabilitiesKHR(physical,surface,&caps),
              "Surface capabilities");
        currentTransform=caps.currentTransform;
        supportedTransforms=caps.supportedTransforms;
        requestedIdentity3d=preferIdentityFor3D;
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
        // EXP29.23: the EXP29.22 16:9 rectangle was letterboxed in
        // 2844x790 swapchain coordinates but appeared as horizontal bars on
        // the Android screen. currentTransform=ROTATE_90 (bit 2) means the
        // current path has an explicit surface orientation to consider.
        // Compare IDENTITY presentation with the historical CURRENT path;
        // enable only when advertised in supportedTransforms.
        const bool canIdentity=(caps.supportedTransforms &
            VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR)!=0;
        sci.preTransform=(preferIdentityFor3D && canIdentity)?
            VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR:caps.currentTransform;
        chosenTransform=sci.preTransform;
        identity3dAccepted=preferIdentityFor3D && canIdentity;
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
        if(displayTimingEnabled) {
            VkRefreshCycleDurationGOOGLE cycle{};
            if(getRefreshDuration(device,swap,&cycle)==VK_SUCCESS)
                refreshPeriodNs=cycle.refreshDuration;
        }
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
        if(timestampValidBits>0 && timestampPeriodNs>0.0f) {
            VkQueryPoolCreateInfo queryInfo{};
            queryInfo.sType=VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO;
            queryInfo.queryType=VK_QUERY_TYPE_TIMESTAMP;
            queryInfo.queryCount=5;
            // Unsupported GPU query path is optional, never block presentation.
            if(vkCreateQueryPool(device,&queryInfo,nullptr,&gpuQueryPool)!=VK_SUCCESS)
                gpuQueryPool=VK_NULL_HANDLE;
        }
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
        if(continuous)createScenePipeline(scene);

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
    int run(int targetHz,int requested,bool continuous,bool holdInsteadOfFG,
            bool alignWithDisplay,int motionRadius,bool fit3dAspect,
            bool enableGpuBudget) {
        recordedMotionRadius=motionRadius;
        fitAspect=fit3dAspect;
        const double fitScale=std::min(double(extent.width)/double(kWidth),
                                       double(extent.height)/double(kHeight));
        fitWidth=std::min(extent.width,std::max(1u,uint32_t(std::lround(kWidth*fitScale))));
        fitHeight=std::min(extent.height,std::max(1u,uint32_t(std::lround(kHeight*fitScale))));
        const PipaFramegenVkImages images={
          tex[0].view,tex[1].view,tex[2].view,tex[3].view,tex[2].image
        };
        int queued=0;
        const auto start=std::chrono::steady_clock::now();
        const uint64_t nominalNs=1000000000ULL/uint64_t(targetHz);
        // WSI reports a *measured* cycle (~6.96ms on this 144Hz panel)
        // rather than ideal 1/144s (6.944ms). Use it only when near the
        // requested 144Hz mode. Never turn a 60/120 request into 144Hz.
        refreshAligned=alignWithDisplay && targetHz==144 &&
           refreshPeriodNs>nominalNs*97u/100u &&
           refreshPeriodNs<nominalNs*103u/100u;
        selectedPacingPeriodNs=refreshAligned?refreshPeriodNs:nominalNs;
        gpuBudgetRequested=enableGpuBudget;
        gpuBudgetEnabled=enableGpuBudget && continuous && !holdInsteadOfFG &&
                          gpuQueryPool!=VK_NULL_HANDLE;
        // Two refresh periods contain one genuine frame plus one synthetic.
        // Reserve 15% margin for other GPU work before shedding FG slots.
        gpuBudgetMs=2.0*double(selectedPacingPeriodNs)*0.85e-6;
        const auto interval=std::chrono::nanoseconds(selectedPacingPeriodNs);
        for(int frame=0;frame<requested && !g_stop.load();++frame) {
            auto deadline=start+interval*frame;
            const auto beforeSleep=std::chrono::steady_clock::now();
            const bool inheritedLate=beforeSleep>deadline+interval;
            if(inheritedLate)++inheritedLateOnePeriod;
            std::this_thread::sleep_until(deadline);
            const auto afterWake=std::chrono::steady_clock::now();
            const bool late=afterWake>deadline+interval;
            if(late) {
                ++deadlineMisses;
                if(!inheritedLate)++timerOversleepOnePeriod;
                ++lateBurstCurrent;
                lateBurstLongest=std::max(lateBurstLongest,lateBurstCurrent);
            } else lateBurstCurrent=0;
            wakeLateMs.push_back(std::max(0.0,
                 std::chrono::duration<double,std::milli>(afterWake-deadline).count()));
            const auto beforeFence=std::chrono::steady_clock::now();
            check(vkWaitForFences(device,1,&fence,VK_TRUE,10000000000ULL),
                  "Wait frame fence");
            fenceWaitMs.push_back(std::chrono::duration<double,std::milli>(
                 std::chrono::steady_clock::now()-beforeFence).count());
            harvestGpuTimestamps();
            uint32_t index=0;
            const auto beforeAcquire=std::chrono::steady_clock::now();
            VkResult acquiredResult=vkAcquireNextImageKHR(device,swap,UINT64_MAX,
                                                         acquired,VK_NULL_HANDLE,&index);
            acquireWaitMs.push_back(std::chrono::duration<double,std::milli>(
                 std::chrono::steady_clock::now()-beforeAcquire).count());
            if(acquiredResult==VK_ERROR_OUT_OF_DATE_KHR)break;
            expect(acquiredResult==VK_SUCCESS || acquiredResult==VK_SUBOPTIMAL_KHR,
                   "Acquire swapchain image failed");
            check(vkResetFences(device,1,&fence),"Reset frame fence");
            check(vkResetCommandPool(device,pool,0),"Reset frame command pool");
            VkCommandBufferBeginInfo begin{};
            begin.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
            begin.flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
            check(vkBeginCommandBuffer(command,&begin),"Begin frame");
            if(gpuQueryPool) {
                vkCmdResetQueryPool(command,gpuQueryPool,0,5);
                vkCmdWriteTimestamp(command,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
                                    gpuQueryPool,0);
            }
            // A/B legacy remains unchanged. Continuous modes regenerate two
            // unique input images per pair; baseline HOLD reuses A on odd slots
            // rather than synthesizing any frame.
            const bool odd=(frame%2)==1;
            // Guard may replace *only* the intermediate synthetic frame with
            // an intentional repetition of the last real frame. It never
            // drops, shifts or rewrites the real source frame.
            const bool budgetFallback=odd && gpuBudgetEnabled &&
                                      gpuBudgetHoldCountdown>0;
            if(budgetFallback) {
                --gpuBudgetHoldCountdown;
                ++gpuBudgetHeld;
            }
            const bool synthesized=odd && !holdInsteadOfFG && !budgetFallback;
            int source=continuous?0:((frame%4)==2?1:0);
            Texture& texSource=tex[synthesized?3:source];
            if(continuous && !odd) {
                const uint32_t sourcePair=uint32_t(frame/2);
                recordSourceScene(command,sourcePair);
                if(gpuBudgetEnabled) {
                    // Diagnostic-only extra compute work. It renders the same
                    // pair again, leaving the visible geometry and final images unchanged.
                    for(uint32_t stressPass=0;
                        stressPass<kGpuBudgetValidationSceneRepeatPasses;++stressPass)
                        recordSourceScene(command,sourcePair);
                }
            }
            if(synthesized) {
                // Reusing motionField between generated frames requires a read-to-
                // write dependency after the preceding warp sampled the field.
                auto motionBarrier=imageBarrier(tex[2].image,
                    VK_IMAGE_LAYOUT_GENERAL,VK_IMAGE_LAYOUT_GENERAL,
                    VK_ACCESS_SHADER_READ_BIT,VK_ACCESS_SHADER_WRITE_BIT);
                vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                    VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,0,0,nullptr,0,nullptr,
                    1,&motionBarrier);
                // EXP29.20 A/B: radius=4 preserves baseline; radius=3 is an
                // explicitly selected speed-quality experiment for this scene.
                const int code=gpuQueryPool?
                    pipa_framegen_vk_record_profiled(engine,command,&images,kWidth,kHeight,
                          0.5f,uint32_t(motionRadius),0.75f,gpuQueryPool,2):
                    pipa_framegen_vk_record(engine,command,&images,kWidth,kHeight,
                          0.5f,uint32_t(motionRadius),0.75f);
                expect(code==0,"Record FrameGen failed");
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
                // Preserve 16:9 geometry, even when SurfaceView is very wide.
                // Black bars are explicit and the clear is transfer-ordered.
                if(fitAspect) {
                    VkClearColorValue black{};
                    black.float32[3]=1.0f;
                    VkImageSubresourceRange range{};
                    range.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;
                    range.levelCount=1;range.layerCount=1;
                    vkCmdClearColorImage(command,swapImages[index],
                        VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,&black,1,&range);
                    VkMemoryBarrier clearToBlit{};
                    clearToBlit.sType=VK_STRUCTURE_TYPE_MEMORY_BARRIER;
                    clearToBlit.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;
                    clearToBlit.dstAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;
                    vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_TRANSFER_BIT,
                        VK_PIPELINE_STAGE_TRANSFER_BIT,0,1,&clearToBlit,0,nullptr,0,nullptr);
                }
                VkImageBlit blit{};
                blit.srcSubresource.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;
                blit.srcSubresource.layerCount=1;
                blit.srcOffsets[1]={int32_t(kWidth),int32_t(kHeight),1};
                blit.dstSubresource.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT;
                blit.dstSubresource.layerCount=1;
                const int32_t left=fitAspect?int32_t((extent.width-fitWidth)/2):0;
                const int32_t top=fitAspect?int32_t((extent.height-fitHeight)/2):0;
                const int32_t width=fitAspect?int32_t(fitWidth):int32_t(extent.width);
                const int32_t height=fitAspect?int32_t(fitHeight):int32_t(extent.height);
                blit.dstOffsets[0]={left,top,0};
                blit.dstOffsets[1]={left+width,top+height,1};
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
            if(gpuQueryPool)
                vkCmdWriteTimestamp(command,VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,
                                    gpuQueryPool,1);
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
            const auto beforeSubmit=std::chrono::steady_clock::now();
            check(vkQueueSubmit(queue,1,&submit,fence),"Submit present frame");
            submitCallMs.push_back(std::chrono::duration<double,std::milli>(
                 std::chrono::steady_clock::now()-beforeSubmit).count());
            VkPresentInfoKHR present{};
            present.sType=VK_STRUCTURE_TYPE_PRESENT_INFO_KHR;
            present.waitSemaphoreCount=1;
            present.pWaitSemaphores=&rendered[index];
            present.swapchainCount=1;
            present.pSwapchains=&swap;
            present.pImageIndices=&index;
            VkResult perSwapchainResult=VK_NOT_READY;
            present.pResults=&perSwapchainResult;
            VkPresentTimeGOOGLE presentStamp{};
            VkPresentTimesInfoGOOGLE presentTiming{};
            if(displayTimingEnabled) {
                presentStamp.presentID=uint32_t(frame+1);
                // A nonzero desired timestamp would affect scheduling; use ID-only.
                presentStamp.desiredPresentTime=0;
                presentTiming.sType=VK_STRUCTURE_TYPE_PRESENT_TIMES_INFO_GOOGLE;
                presentTiming.swapchainCount=1;
                presentTiming.pTimes=&presentStamp;
                present.pNext=&presentTiming;
            }
            const auto submitTime=std::chrono::steady_clock::now();
            VkResult pr=vkQueuePresentKHR(queue,&present);
            lastTopLevelPresentResult=pr;
            lastPerSwapchainPresentResult=perSwapchainResult;
            if(pr!=perSwapchainResult)++presentResultMismatches;
            if(pr==VK_SUBOPTIMAL_KHR) {
                ++topLevelSuboptimal;
                if(perSwapchainResult==VK_SUBOPTIMAL_KHR)++perSwapchainSuboptimal;
                querySurfaceAfterSuboptimal();
            }
            const auto completeTime=std::chrono::steady_clock::now();
            presentCallMs.push_back(
                std::chrono::duration<double,std::milli>(completeTime-submitTime).count());
            if(pr==VK_ERROR_OUT_OF_DATE_KHR)break;
            expect(pr==VK_SUCCESS || pr==VK_SUBOPTIMAL_KHR,"vkQueuePresentKHR failed");
            ++queued;
            if(gpuQueryPool)pendingGpuRole=synthesized?1:0;
            if(odd && (holdInsteadOfFG || budgetFallback))++sceneHeldSubmitted;
            else if(synthesized)++sceneGeneratedSubmitted;
            else ++sceneRealSubmitted;
            if((frame%8)==7) collectTiming();
        }
        check(vkQueueWaitIdle(queue),"Wait present queue idle");
        harvestGpuTimestamps();
        collectTiming();
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
    jbyteArray sceneShader,jint targetHz,jint frames,jboolean continuousMode,
    jboolean holdInsteadOfFGMode,jboolean alignWithDisplayMode,jint motionRadius,
    jboolean fit3dAspectMode,jboolean preferIdentity3dMode,
    jboolean gpuBudgetMode) {
    bool expected=false;
    if(!g_inUse.compare_exchange_strong(expected,true))
        return env->NewStringUTF("Uma sessão Vulkan já está ativa.");
    g_stop.store(false);
    std::string result;
    try {
        expect(targetHz==60 || targetHz==120 || targetHz==144,"Invalid targetHz");
        expect(frames>0 && frames<=2400,"Invalid frame count");
        expect(motionRadius==3 || motionRadius==4,"Invalid Motion radius");
        auto motion=shaderBytes(env,motionShader);
        auto warp=shaderBytes(env,warpShader);
        const bool continuous=continuousMode==JNI_TRUE;
        const bool holdInsteadOfFG=continuous && holdInsteadOfFGMode==JNI_TRUE;
        std::vector<uint32_t> scene;
        if(continuous) scene=shaderBytes(env,sceneShader);
        Presenter p;
        auto t0=std::chrono::steady_clock::now();
        p.init(env,surface,motion,warp,scene,continuous,
               fit3dAspectMode==JNI_TRUE && preferIdentity3dMode==JNI_TRUE);
        auto t1=std::chrono::steady_clock::now();
        int queued=p.run(targetHz,frames,continuous,holdInsteadOfFG,
                         alignWithDisplayMode==JNI_TRUE,int(motionRadius),
                         fit3dAspectMode==JNI_TRUE,
                         gpuBudgetMode==JNI_TRUE);
        auto t2=std::chrono::steady_clock::now();
        double initializeMs=std::chrono::duration<double,std::milli>(t1-t0).count();
        double presentSeconds=std::chrono::duration<double>(t2-t1).count();
        double apiRate=queued/std::max(0.000001,presentSeconds);
        result="GPU "+p.gpuName+" | VkSwapchainKHR FIFO | "+
          std::to_string(p.extent.width)+"x"+std::to_string(p.extent.height)+
          " | Aceitos por vkQueuePresentKHR: "+std::to_string(queued)+
          " (real="+std::to_string(p.sceneRealSubmitted)+
          ", interpolado="+std::to_string(p.sceneGeneratedSubmitted)+
          ", repetido="+std::to_string(p.sceneHeldSubmitted)+")"+
          " | cena="+(holdInsteadOfFG?std::string("continua GPU HOLD sem FG"):
              continuous?std::string("continua GPU 2x"):
                         std::string("A/B estatica"))+
          " | deadlines perdidos="+std::to_string(p.deadlineMisses)+
          " | GPU BUDGET solicitado="+std::to_string(p.gpuBudgetRequested?1:0)+
          " ativo="+std::to_string(p.gpuBudgetEnabled?1:0)+
          " passes stress cena="+std::to_string(p.gpuBudgetEnabled?
              kGpuBudgetValidationSceneRepeatPasses:0u)+
          " teto="+std::to_string(p.gpuBudgetMs)+"ms"+
          " probes pares="+std::to_string(p.gpuBudgetProbeFrames)+
          " acima teto par="+std::to_string(p.gpuBudgetOverruns)+
          " trips 3x="+std::to_string(p.gpuBudgetGovernorTrips)+
          " pares indisponiveis="+std::to_string(p.gpuBudgetMissingPairs)+
          " ultimo par="+std::to_string(p.lastPairGpuMs)+"ms"+
          " HOLD adaptativos="+std::to_string(p.gpuBudgetHeld)+
          " | preTransform="+std::to_string(uint32_t(p.chosenTransform))+
          " | currentTransform="+std::to_string(uint32_t(p.currentTransform))+
          " | supportedTransforms="+std::to_string(uint32_t(p.supportedTransforms))+
          " | IDENTITY solicitada="+std::to_string(p.requestedIdentity3d?1:0)+
          " | IDENTITY ativa="+std::to_string(p.identity3dAccepted?1:0)+
          " | blit="+std::to_string(p.useBlit?1:0)+
          " | FIT 16:9="+std::to_string(p.fitAspect?1:0)+
          " | viewport destino="+std::to_string(p.fitAspect?p.fitWidth:p.extent.width)+
          "x"+std::to_string(p.fitAspect?p.fitHeight:p.extent.height)+
          " | swapFormat="+std::to_string(int(p.swapFormat))+
          " | Frequencia solicitada="+std::to_string(targetHz)+" Hz"+
          " | chamadas apresentacao/s="+std::to_string(apiRate)+
          " | inicializacao="+std::to_string(initializeMs)+" ms"+
          p.gpuTimingSummary()+p.cpuPacingSummary()+p.timingSummary()+
          p.surfaceDiagnosticSummary()+
          p.traceLayerSummary()+
          " | chamadas/s NAO sao FPS fisicos exibidos; timing WSI e reportado pelo driver.";
    } catch(const std::exception& e) {
        result=std::string("EXP29.27 Vulkan presenter: ")+e.what();
    }
    g_inUse.store(false);
    return env->NewStringUTF(result.c_str());
}
