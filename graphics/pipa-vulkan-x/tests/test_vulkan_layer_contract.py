from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
CPP = ROOT / "lab-app/app/src/main/cpp"
LAYER = (CPP / "present_trace_layer.cpp").read_text()
PRESENTER = (CPP / "presenter.cpp").read_text()
MANIFEST = json.loads((ROOT / "lab-app/app/src/main/assets/VkLayer_PIPA_present_trace.json").read_text())

assert MANIFEST["layer"]["name"] == "VK_LAYER_PIPA_present_trace"
assert MANIFEST["layer"]["library_path"] == "libVkLayer_PIPA_present_trace.so"
assert "vkQueuePresentKHR" in LAYER
assert "vkCreateSwapchainKHR" in LAYER
assert "vkDestroySwapchainKHR" in LAYER
assert "nextGetImages(device, *swapchain, &count, nullptr)" in LAYER
assert "pipa_vk_layer_get_stats" in LAYER
assert "pipa_vk_layer_get_swapchain_stats" in LAYER
assert "pipa_vk_layer_get_last_swapchain_probe" in LAYER
assert "createInfo->imageExtent.width" in LAYER
assert "createInfo->imageUsage" in LAYER
assert "createInfo->presentMode" in LAYER
assert "nextGetSurfaceCaps(physicalDevice,createInfo->surface,&caps)" in LAYER
assert "caps.supportedUsageFlags" in LAYER
assert "layerSwapchain extent=" in PRESENTER
assert "usageBits=" in PRESENTER
assert "surfaceUsageBits=" in PRESENTER
assert "surfaceCapsAvailable=" in PRESENTER
assert "supportsTransferSrc=" in PRESENTER
assert "supportsSampled=" in PRESENTER
assert 'dlsym(traceLayerLibrary,"pipa_vk_layer_get_last_swapchain_probe")' in PRESENTER
assert "pipa_vk_layer_reset_stats" in LAYER
assert "registerQueue(device, *queue, state);" in LAYER
assert "ci.enabledLayerCount=1;" in PRESENTER
assert "traceLayerSummary()" in PRESENTER
assert "swapchains created=" in PRESENTER
assert "releaseSwapchainForProbe();" in PRESENTER
assert "VK_LAYER_PIPA available=" in PRESENTER
assert "present.pResults=&perSwapchainResult;" in PRESENTER
assert "querySurfaceAfterSuboptimal()" in PRESENTER
assert "surfaceDiagnosticSummary()" in PRESENTER
GRADLE = (ROOT / "lab-app/app/build.gradle").read_text()
assert "versionCode 333" in GRADLE
assert "29.43-surface-usage-capabilities" in GRADLE
assert "dlopen(kPipaTraceLayerLibrary" in PRESENTER
assert "if(instanceResult!=VK_SUCCESS && traceLayerActive)" in PRESENTER
print("EXP29.43 Vulkan surface usage capability contract: PASS")
