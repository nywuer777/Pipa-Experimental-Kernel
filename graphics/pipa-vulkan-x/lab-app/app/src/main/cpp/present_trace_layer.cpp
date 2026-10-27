#include <vulkan/vulkan.h>
#include <vulkan/vk_layer.h>

#include <atomic>
#include <cstdint>
#include <cstring>
#include <mutex>
#include <unordered_map>
#include <vector>

namespace {
constexpr char kLayerName[] = "VK_LAYER_PIPA_present_trace";

struct InstanceState {
    VkInstance instance = VK_NULL_HANDLE;
    PFN_vkGetInstanceProcAddr nextGipa = nullptr;
    PFN_vkDestroyInstance nextDestroyInstance = nullptr;
};

struct DeviceState {
    VkPhysicalDevice physicalDevice = VK_NULL_HANDLE;
    PFN_vkGetPhysicalDeviceSurfaceCapabilitiesKHR nextGetSurfaceCapabilities = nullptr;
    PFN_vkGetDeviceProcAddr nextGdpa = nullptr;
    PFN_vkDestroyDevice nextDestroyDevice = nullptr;
    PFN_vkGetDeviceQueue nextGetDeviceQueue = nullptr;
    PFN_vkGetDeviceQueue2 nextGetDeviceQueue2 = nullptr;
    PFN_vkQueuePresentKHR nextQueuePresent = nullptr;
    PFN_vkCreateSwapchainKHR nextCreateSwapchain = nullptr;
    PFN_vkDestroySwapchainKHR nextDestroySwapchain = nullptr;
    PFN_vkGetSwapchainImagesKHR nextGetSwapchainImages = nullptr;
    std::vector<void*> queueKeys;
};

std::mutex g_stateMutex;
std::unordered_map<void*, InstanceState> g_instances;
std::unordered_map<void*, DeviceState> g_devices;
std::unordered_map<void*, PFN_vkQueuePresentKHR> g_queues;
std::atomic<uint64_t> g_presentCalls{0};
std::atomic<uint64_t> g_presentSuccess{0};
std::atomic<uint64_t> g_presentSuboptimal{0};
std::atomic<uint64_t> g_presentErrors{0};
std::atomic<uint64_t> g_swapchainCreates{0};
std::atomic<uint64_t> g_swapchainDestroys{0};
std::atomic<uint64_t> g_swapchainImages{0};
std::atomic<uint32_t> g_lastSwapchainWidth{0};
std::atomic<uint32_t> g_lastSwapchainHeight{0};
std::atomic<uint32_t> g_lastSwapchainFormat{0};
std::atomic<uint32_t> g_lastSwapchainUsage{0};
std::atomic<uint32_t> g_lastSwapchainPresentMode{0};
std::atomic<uint32_t> g_lastSwapchainImageCount{0};
std::atomic<uint32_t> g_lastSurfaceSupportedUsage{0};
std::atomic<uint32_t> g_lastSurfaceCapsAvailable{0};

template <typename Handle>
void* dispatchKey(Handle handle) {
    return handle == VK_NULL_HANDLE ? nullptr :
        *reinterpret_cast<void* const*>(handle);
}

VkLayerInstanceCreateInfo* instanceLinkInfo(const VkInstanceCreateInfo* info) {
    auto* chain = const_cast<VkLayerInstanceCreateInfo*>(
        reinterpret_cast<const VkLayerInstanceCreateInfo*>(info->pNext));
    while (chain != nullptr) {
        if (chain->sType == VK_STRUCTURE_TYPE_LOADER_INSTANCE_CREATE_INFO &&
            chain->function == VK_LAYER_LINK_INFO) return chain;
        chain = const_cast<VkLayerInstanceCreateInfo*>(
            reinterpret_cast<const VkLayerInstanceCreateInfo*>(chain->pNext));
    }
    return nullptr;
}

VkLayerDeviceCreateInfo* deviceLinkInfo(const VkDeviceCreateInfo* info) {
    auto* chain = const_cast<VkLayerDeviceCreateInfo*>(
        reinterpret_cast<const VkLayerDeviceCreateInfo*>(info->pNext));
    while (chain != nullptr) {
        if (chain->sType == VK_STRUCTURE_TYPE_LOADER_DEVICE_CREATE_INFO &&
            chain->function == VK_LAYER_LINK_INFO) return chain;
        chain = const_cast<VkLayerDeviceCreateInfo*>(
            reinterpret_cast<const VkLayerDeviceCreateInfo*>(chain->pNext));
    }
    return nullptr;
}

bool layerProperty(VkLayerProperties* property) {
    if (property == nullptr) return false;
    *property = {};
    std::strncpy(property->layerName, kLayerName, sizeof(property->layerName) - 1);
    property->specVersion = VK_API_VERSION_1_1;
    property->implementationVersion = 1;
    std::strncpy(property->description, "Pipa opt-in Vulkan swapchain metadata and present trace",
                 sizeof(property->description) - 1);
    return true;
}

void registerQueue(VkDevice device, VkQueue queue, const DeviceState& state) {
    if (queue == VK_NULL_HANDLE || state.nextQueuePresent == nullptr) return;
    void* key = dispatchKey(queue);
    std::lock_guard<std::mutex> lock(g_stateMutex);
    g_queues[key] = state.nextQueuePresent;
    auto it = g_devices.find(dispatchKey(device));
    if (it != g_devices.end()) it->second.queueKeys.push_back(key);
}

}  // namespace

extern "C" {

VKAPI_ATTR VkResult VKAPI_CALL vkNegotiateLoaderLayerInterfaceVersion(
    VkNegotiateLayerInterface* version) {
    if (version == nullptr ||
        version->sType != LAYER_NEGOTIATE_INTERFACE_STRUCT) {
        return VK_ERROR_INITIALIZATION_FAILED;
    }
    if (version->loaderLayerInterfaceVersion < MIN_SUPPORTED_LOADER_LAYER_INTERFACE_VERSION) {
        return VK_ERROR_INITIALIZATION_FAILED;
    }
    if (version->loaderLayerInterfaceVersion > CURRENT_LOADER_LAYER_INTERFACE_VERSION) {
        version->loaderLayerInterfaceVersion = CURRENT_LOADER_LAYER_INTERFACE_VERSION;
    }
    version->pfnGetInstanceProcAddr = vkGetInstanceProcAddr;
    version->pfnGetDeviceProcAddr = vkGetDeviceProcAddr;
    version->pfnGetPhysicalDeviceProcAddr = nullptr;
    return VK_SUCCESS;
}

VKAPI_ATTR VkResult VKAPI_CALL vkEnumerateInstanceLayerProperties(
    uint32_t* propertyCount, VkLayerProperties* properties) {
    if (propertyCount == nullptr) return VK_ERROR_INITIALIZATION_FAILED;
    if (properties == nullptr) {
        *propertyCount = 1;
        return VK_SUCCESS;
    }
    if (*propertyCount == 0) return VK_INCOMPLETE;
    layerProperty(&properties[0]);
    *propertyCount = 1;
    return VK_SUCCESS;
}

VKAPI_ATTR VkResult VKAPI_CALL vkEnumerateDeviceLayerProperties(
    VkPhysicalDevice physicalDevice, uint32_t* propertyCount,
    VkLayerProperties* properties) {
    (void)physicalDevice;
    return vkEnumerateInstanceLayerProperties(propertyCount, properties);
}

VKAPI_ATTR VkResult VKAPI_CALL vkEnumerateInstanceExtensionProperties(
    const char* layerName, uint32_t* propertyCount,
    VkExtensionProperties* properties) {
    if (propertyCount == nullptr) return VK_ERROR_INITIALIZATION_FAILED;
    if (layerName != nullptr && std::strcmp(layerName, kLayerName) != 0) {
        return VK_ERROR_LAYER_NOT_PRESENT;
    }
    if (properties != nullptr && *propertyCount > 0) properties[0] = {};
    *propertyCount = 0;
    return VK_SUCCESS;
}

VKAPI_ATTR VkResult VKAPI_CALL vkCreateInstance(
    const VkInstanceCreateInfo* createInfo,
    const VkAllocationCallbacks* allocator, VkInstance* instance) {
    if (createInfo == nullptr || instance == nullptr) {
        return VK_ERROR_INITIALIZATION_FAILED;
    }
    VkLayerInstanceCreateInfo* chain = instanceLinkInfo(createInfo);
    if (chain == nullptr || chain->u.pLayerInfo == nullptr) {
        return VK_ERROR_INITIALIZATION_FAILED;
    }
    VkLayerInstanceLink* link = chain->u.pLayerInfo;
    PFN_vkGetInstanceProcAddr nextGipa = link->pfnNextGetInstanceProcAddr;
    chain->u.pLayerInfo = link->pNext;
    auto nextCreate = reinterpret_cast<PFN_vkCreateInstance>(
        nextGipa(VK_NULL_HANDLE, "vkCreateInstance"));
    if (nextCreate == nullptr) return VK_ERROR_INITIALIZATION_FAILED;
    VkResult result = nextCreate(createInfo, allocator, instance);
    if (result == VK_SUCCESS) {
        InstanceState state{};
        state.instance = *instance;
        state.nextGipa = nextGipa;
        state.nextDestroyInstance = reinterpret_cast<PFN_vkDestroyInstance>(
            nextGipa(*instance, "vkDestroyInstance"));
        std::lock_guard<std::mutex> lock(g_stateMutex);
        g_instances[dispatchKey(*instance)] = state;
    }
    return result;
}

VKAPI_ATTR void VKAPI_CALL vkDestroyInstance(
    VkInstance instance, const VkAllocationCallbacks* allocator) {
    InstanceState state{};
    {
        std::lock_guard<std::mutex> lock(g_stateMutex);
        auto it = g_instances.find(dispatchKey(instance));
        if (it == g_instances.end()) return;
        state = it->second;
    }
    if (state.nextDestroyInstance != nullptr) {
        state.nextDestroyInstance(instance, allocator);
    }
    std::lock_guard<std::mutex> lock(g_stateMutex);
    g_instances.erase(dispatchKey(instance));
}

VKAPI_ATTR VkResult VKAPI_CALL vkCreateDevice(
    VkPhysicalDevice physicalDevice, const VkDeviceCreateInfo* createInfo,
    const VkAllocationCallbacks* allocator, VkDevice* device) {
    if (createInfo == nullptr || device == nullptr) {
        return VK_ERROR_INITIALIZATION_FAILED;
    }
    VkLayerDeviceCreateInfo* chain = deviceLinkInfo(createInfo);
    if (chain == nullptr || chain->u.pLayerInfo == nullptr) {
        return VK_ERROR_INITIALIZATION_FAILED;
    }
    VkLayerDeviceLink* link = chain->u.pLayerInfo;
    PFN_vkGetInstanceProcAddr nextGipa = link->pfnNextGetInstanceProcAddr;
    PFN_vkGetDeviceProcAddr nextGdpa = link->pfnNextGetDeviceProcAddr;
    VkInstance parentInstance = VK_NULL_HANDLE;
    {
        std::lock_guard<std::mutex> lock(g_stateMutex);
        auto it = g_instances.find(dispatchKey(physicalDevice));
        if (it != g_instances.end()) parentInstance = it->second.instance;
    }
    if (parentInstance == VK_NULL_HANDLE) return VK_ERROR_INITIALIZATION_FAILED;
    chain->u.pLayerInfo = link->pNext;
    auto nextCreate = reinterpret_cast<PFN_vkCreateDevice>(
        nextGipa(parentInstance, "vkCreateDevice"));
    if (nextCreate == nullptr) return VK_ERROR_INITIALIZATION_FAILED;
    VkResult result = nextCreate(physicalDevice, createInfo, allocator, device);
    if (result == VK_SUCCESS) {
        DeviceState state{};
        state.physicalDevice = physicalDevice;
        state.nextGetSurfaceCapabilities =
            reinterpret_cast<PFN_vkGetPhysicalDeviceSurfaceCapabilitiesKHR>(
                nextGipa(parentInstance,"vkGetPhysicalDeviceSurfaceCapabilitiesKHR"));
        state.nextGdpa = nextGdpa;
        state.nextDestroyDevice = nextGdpa(*device, "vkDestroyDevice") == nullptr ?
            nullptr : reinterpret_cast<PFN_vkDestroyDevice>(
                nextGdpa(*device, "vkDestroyDevice"));
        state.nextGetDeviceQueue = reinterpret_cast<PFN_vkGetDeviceQueue>(
            nextGdpa(*device, "vkGetDeviceQueue"));
        state.nextGetDeviceQueue2 = reinterpret_cast<PFN_vkGetDeviceQueue2>(
            nextGdpa(*device, "vkGetDeviceQueue2"));
        state.nextQueuePresent = reinterpret_cast<PFN_vkQueuePresentKHR>(
            nextGdpa(*device, "vkQueuePresentKHR"));
        state.nextCreateSwapchain = reinterpret_cast<PFN_vkCreateSwapchainKHR>(
            nextGdpa(*device, "vkCreateSwapchainKHR"));
        state.nextDestroySwapchain = reinterpret_cast<PFN_vkDestroySwapchainKHR>(
            nextGdpa(*device, "vkDestroySwapchainKHR"));
        state.nextGetSwapchainImages = reinterpret_cast<PFN_vkGetSwapchainImagesKHR>(
            nextGdpa(*device, "vkGetSwapchainImagesKHR"));
        std::lock_guard<std::mutex> lock(g_stateMutex);
        g_devices[dispatchKey(*device)] = state;
    }
    return result;
}

VKAPI_ATTR VkResult VKAPI_CALL vkCreateSwapchainKHR(
    VkDevice device, const VkSwapchainCreateInfoKHR* createInfo,
    const VkAllocationCallbacks* allocator, VkSwapchainKHR* swapchain) {
    PFN_vkCreateSwapchainKHR nextCreate = nullptr;
    PFN_vkGetSwapchainImagesKHR nextGetImages = nullptr;
    PFN_vkGetPhysicalDeviceSurfaceCapabilitiesKHR nextGetSurfaceCaps = nullptr;
    VkPhysicalDevice physicalDevice = VK_NULL_HANDLE;
    {
        std::lock_guard<std::mutex> lock(g_stateMutex);
        auto it = g_devices.find(dispatchKey(device));
        if (it != g_devices.end()) {
            nextCreate = it->second.nextCreateSwapchain;
            nextGetImages = it->second.nextGetSwapchainImages;
            nextGetSurfaceCaps = it->second.nextGetSurfaceCapabilities;
            physicalDevice = it->second.physicalDevice;
        }
    }
    if (nextCreate == nullptr) return VK_ERROR_INITIALIZATION_FAILED;
    const VkResult result = nextCreate(device, createInfo, allocator, swapchain);
    if (result == VK_SUCCESS && swapchain != nullptr &&
        *swapchain != VK_NULL_HANDLE) {
        g_swapchainCreates.fetch_add(1, std::memory_order_relaxed);
        if (createInfo != nullptr) {
            g_lastSwapchainWidth.store(createInfo->imageExtent.width,
                                       std::memory_order_relaxed);
            g_lastSwapchainHeight.store(createInfo->imageExtent.height,
                                        std::memory_order_relaxed);
            g_lastSwapchainFormat.store(static_cast<uint32_t>(createInfo->imageFormat),
                                        std::memory_order_relaxed);
            g_lastSwapchainUsage.store(static_cast<uint32_t>(createInfo->imageUsage),
                                       std::memory_order_relaxed);
            g_lastSwapchainPresentMode.store(
                static_cast<uint32_t>(createInfo->presentMode),
                std::memory_order_relaxed);
            uint32_t supportedUsage = 0;
            if (nextGetSurfaceCaps != nullptr &&
                physicalDevice != VK_NULL_HANDLE &&
                createInfo->surface != VK_NULL_HANDLE) {
                VkSurfaceCapabilitiesKHR caps{};
                if (nextGetSurfaceCaps(physicalDevice,createInfo->surface,&caps) ==
                    VK_SUCCESS) {
                    supportedUsage = static_cast<uint32_t>(caps.supportedUsageFlags);
                    g_lastSurfaceCapsAvailable.store(1,std::memory_order_relaxed);
                }
            }
            g_lastSurfaceSupportedUsage.store(supportedUsage,
                                               std::memory_order_relaxed);
        }
        if (nextGetImages != nullptr) {
            uint32_t count = 0;
            const VkResult imageResult = nextGetImages(device, *swapchain, &count, nullptr);
            if ((imageResult == VK_SUCCESS || imageResult == VK_INCOMPLETE) && count > 0) {
                g_swapchainImages.fetch_add(count, std::memory_order_relaxed);
                g_lastSwapchainImageCount.store(count, std::memory_order_relaxed);
            }
        }
    }
    return result;
}

VKAPI_ATTR void VKAPI_CALL vkDestroySwapchainKHR(
    VkDevice device, VkSwapchainKHR swapchain,
    const VkAllocationCallbacks* allocator) {
    PFN_vkDestroySwapchainKHR nextDestroy = nullptr;
    {
        std::lock_guard<std::mutex> lock(g_stateMutex);
        auto it = g_devices.find(dispatchKey(device));
        if (it != g_devices.end()) nextDestroy = it->second.nextDestroySwapchain;
    }
    if (nextDestroy == nullptr) return;
    nextDestroy(device, swapchain, allocator);
    g_swapchainDestroys.fetch_add(1, std::memory_order_relaxed);
}

VKAPI_ATTR void VKAPI_CALL vkGetDeviceQueue(
    VkDevice device, uint32_t queueFamilyIndex, uint32_t queueIndex,
    VkQueue* queue) {
    DeviceState state{};
    {
        std::lock_guard<std::mutex> lock(g_stateMutex);
        auto it = g_devices.find(dispatchKey(device));
        if (it == g_devices.end()) return;
        state = it->second;
    }
    if (state.nextGetDeviceQueue == nullptr) return;
    state.nextGetDeviceQueue(device, queueFamilyIndex, queueIndex, queue);
    if (queue != nullptr) registerQueue(device, *queue, state);
}

VKAPI_ATTR void VKAPI_CALL vkGetDeviceQueue2(
    VkDevice device, const VkDeviceQueueInfo2* queueInfo, VkQueue* queue) {
    DeviceState state{};
    {
        std::lock_guard<std::mutex> lock(g_stateMutex);
        auto it = g_devices.find(dispatchKey(device));
        if (it == g_devices.end()) return;
        state = it->second;
    }
    if (state.nextGetDeviceQueue2 == nullptr) return;
    state.nextGetDeviceQueue2(device, queueInfo, queue);
    if (queue != nullptr) registerQueue(device, *queue, state);
}

VKAPI_ATTR VkResult VKAPI_CALL vkQueuePresentKHR(
    VkQueue queue, const VkPresentInfoKHR* presentInfo) {
    PFN_vkQueuePresentKHR nextPresent = nullptr;
    {
        std::lock_guard<std::mutex> lock(g_stateMutex);
        auto it = g_queues.find(dispatchKey(queue));
        if (it != g_queues.end()) nextPresent = it->second;
    }
    if (nextPresent == nullptr) return VK_ERROR_INITIALIZATION_FAILED;
    g_presentCalls.fetch_add(1, std::memory_order_relaxed);
    VkResult result = nextPresent(queue, presentInfo);
    if (result == VK_SUCCESS) {
        g_presentSuccess.fetch_add(1, std::memory_order_relaxed);
    } else if (result == VK_SUBOPTIMAL_KHR) {
        g_presentSuboptimal.fetch_add(1, std::memory_order_relaxed);
    } else {
        g_presentErrors.fetch_add(1, std::memory_order_relaxed);
    }
    return result;
}

VKAPI_ATTR void VKAPI_CALL vkDestroyDevice(
    VkDevice device, const VkAllocationCallbacks* allocator) {
    DeviceState state{};
    void* deviceKey = dispatchKey(device);
    {
        std::lock_guard<std::mutex> lock(g_stateMutex);
        auto it = g_devices.find(deviceKey);
        if (it == g_devices.end()) return;
        state = it->second;
    }
    if (state.nextDestroyDevice != nullptr) {
        state.nextDestroyDevice(device, allocator);
    }
    std::lock_guard<std::mutex> lock(g_stateMutex);
    for (void* queueKey : state.queueKeys) g_queues.erase(queueKey);
    g_devices.erase(deviceKey);
}

VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL vkGetDeviceProcAddr(
    VkDevice device, const char* name) {
    if (name == nullptr) return nullptr;
    if (std::strcmp(name, "vkGetDeviceProcAddr") == 0) {
        return reinterpret_cast<PFN_vkVoidFunction>(vkGetDeviceProcAddr);
    }
    if (std::strcmp(name, "vkDestroyDevice") == 0) {
        return reinterpret_cast<PFN_vkVoidFunction>(vkDestroyDevice);
    }
    if (std::strcmp(name, "vkGetDeviceQueue") == 0) {
        return reinterpret_cast<PFN_vkVoidFunction>(vkGetDeviceQueue);
    }
    if (std::strcmp(name, "vkGetDeviceQueue2") == 0) {
        return reinterpret_cast<PFN_vkVoidFunction>(vkGetDeviceQueue2);
    }
    if (std::strcmp(name, "vkQueuePresentKHR") == 0) {
        return reinterpret_cast<PFN_vkVoidFunction>(vkQueuePresentKHR);
    }
    if (std::strcmp(name, "vkCreateSwapchainKHR") == 0) {
        return reinterpret_cast<PFN_vkVoidFunction>(vkCreateSwapchainKHR);
    }
    if (std::strcmp(name, "vkDestroySwapchainKHR") == 0) {
        return reinterpret_cast<PFN_vkVoidFunction>(vkDestroySwapchainKHR);
    }
    PFN_vkGetDeviceProcAddr nextGdpa = nullptr;
    {
        std::lock_guard<std::mutex> lock(g_stateMutex);
        auto it = g_devices.find(dispatchKey(device));
        if (it != g_devices.end()) nextGdpa = it->second.nextGdpa;
    }
    return nextGdpa == nullptr ? nullptr : nextGdpa(device, name);
}

VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL vkGetInstanceProcAddr(
    VkInstance instance, const char* name) {
    if (name == nullptr) return nullptr;
    if (std::strcmp(name, "vkGetInstanceProcAddr") == 0) {
        return reinterpret_cast<PFN_vkVoidFunction>(vkGetInstanceProcAddr);
    }
    if (std::strcmp(name, "vkCreateInstance") == 0) {
        return reinterpret_cast<PFN_vkVoidFunction>(vkCreateInstance);
    }
    if (std::strcmp(name, "vkDestroyInstance") == 0) {
        return reinterpret_cast<PFN_vkVoidFunction>(vkDestroyInstance);
    }
    if (std::strcmp(name, "vkCreateDevice") == 0) {
        return reinterpret_cast<PFN_vkVoidFunction>(vkCreateDevice);
    }
    if (std::strcmp(name, "vkGetDeviceProcAddr") == 0) {
        return reinterpret_cast<PFN_vkVoidFunction>(vkGetDeviceProcAddr);
    }
    if (std::strcmp(name, "vkQueuePresentKHR") == 0) {
        return reinterpret_cast<PFN_vkVoidFunction>(vkQueuePresentKHR);
    }
    PFN_vkGetInstanceProcAddr nextGipa = nullptr;
    {
        std::lock_guard<std::mutex> lock(g_stateMutex);
        auto it = g_instances.find(dispatchKey(instance));
        if (it != g_instances.end()) nextGipa = it->second.nextGipa;
    }
    return nextGipa == nullptr ? nullptr : nextGipa(instance, name);
}

void pipa_vk_layer_reset_stats() {
    g_presentCalls.store(0, std::memory_order_relaxed);
    g_presentSuccess.store(0, std::memory_order_relaxed);
    g_presentSuboptimal.store(0, std::memory_order_relaxed);
    g_presentErrors.store(0, std::memory_order_relaxed);
    g_swapchainCreates.store(0, std::memory_order_relaxed);
    g_swapchainDestroys.store(0, std::memory_order_relaxed);
    g_swapchainImages.store(0, std::memory_order_relaxed);
    g_lastSwapchainWidth.store(0, std::memory_order_relaxed);
    g_lastSwapchainHeight.store(0, std::memory_order_relaxed);
    g_lastSwapchainFormat.store(0, std::memory_order_relaxed);
    g_lastSwapchainUsage.store(0, std::memory_order_relaxed);
    g_lastSwapchainPresentMode.store(0, std::memory_order_relaxed);
    g_lastSwapchainImageCount.store(0, std::memory_order_relaxed);
    g_lastSurfaceSupportedUsage.store(0, std::memory_order_relaxed);
    g_lastSurfaceCapsAvailable.store(0, std::memory_order_relaxed);
}

void pipa_vk_layer_get_swapchain_stats(uint64_t* creates, uint64_t* destroys,
                                       uint64_t* images) {
    if (creates != nullptr) *creates = g_swapchainCreates.load(std::memory_order_relaxed);
    if (destroys != nullptr) *destroys = g_swapchainDestroys.load(std::memory_order_relaxed);
    if (images != nullptr) *images = g_swapchainImages.load(std::memory_order_relaxed);
}

void pipa_vk_layer_get_last_swapchain_probe(uint32_t* width, uint32_t* height,
                                            uint32_t* format, uint32_t* usage,
                                            uint32_t* presentMode,
                                            uint32_t* imageCount,
                                            uint32_t* supportedUsage,
                                            uint32_t* surfaceCapsAvailable) {
    if (width != nullptr) *width = g_lastSwapchainWidth.load(std::memory_order_relaxed);
    if (height != nullptr) *height = g_lastSwapchainHeight.load(std::memory_order_relaxed);
    if (format != nullptr) *format = g_lastSwapchainFormat.load(std::memory_order_relaxed);
    if (usage != nullptr) *usage = g_lastSwapchainUsage.load(std::memory_order_relaxed);
    if (presentMode != nullptr)
        *presentMode = g_lastSwapchainPresentMode.load(std::memory_order_relaxed);
    if (imageCount != nullptr)
        *imageCount = g_lastSwapchainImageCount.load(std::memory_order_relaxed);
    if (supportedUsage != nullptr)
        *supportedUsage = g_lastSurfaceSupportedUsage.load(std::memory_order_relaxed);
    if (surfaceCapsAvailable != nullptr)
        *surfaceCapsAvailable = g_lastSurfaceCapsAvailable.load(std::memory_order_relaxed);
}

void pipa_vk_layer_get_stats(uint64_t* calls, uint64_t* success,
                             uint64_t* suboptimal, uint64_t* errors) {
    if (calls != nullptr) *calls = g_presentCalls.load(std::memory_order_relaxed);
    if (success != nullptr) *success = g_presentSuccess.load(std::memory_order_relaxed);
    if (suboptimal != nullptr) *suboptimal = g_presentSuboptimal.load(std::memory_order_relaxed);
    if (errors != nullptr) *errors = g_presentErrors.load(std::memory_order_relaxed);
}

}  // extern "C"
