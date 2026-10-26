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
assert "versionCode 325" in GRADLE
assert "29.36-sustained-60s" in GRADLE
assert "dlopen(kPipaTraceLayerLibrary" in PRESENTER
assert "if(instanceResult!=VK_SUCCESS && traceLayerActive)" in PRESENTER
print("EXP29.31 explicit Vulkan swapchain probe contract: PASS")
