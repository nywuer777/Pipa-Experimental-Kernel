#!/usr/bin/env python3
"""EXP29.13 build-time presenter integration checks; device rendering NOT verified."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
lab=root/"lab-app"
cpp=(lab/"app/src/main/cpp/presenter.cpp").read_text()
java=(lab/"app/src/main/java/dev/pipa/framegen/lab/PresenterActivity.java").read_text()
main=(lab/"app/src/main/java/dev/pipa/framegen/lab/MainActivity.java").read_text()
manifest=(lab/"app/src/main/AndroidManifest.xml").read_text()
cmake=(lab/"app/src/main/cpp/CMakeLists.txt").read_text()
gradle=(lab/"app/build.gradle").read_text()

for token in (
    "ANativeWindow_fromSurface","vkCreateAndroidSurfaceKHR(",
    "VK_KHR_ANDROID_SURFACE_EXTENSION_NAME","VK_KHR_SWAPCHAIN_EXTENSION_NAME",
    "vkGetPhysicalDeviceSurfaceSupportKHR(","VK_IMAGE_USAGE_TRANSFER_DST_BIT",
    "vkCreateSwapchainKHR(","VK_PRESENT_MODE_FIFO_KHR","vkAcquireNextImageKHR(",
    "vkQueuePresentKHR(","vkQueueSubmit(","vkWaitForFences(",
    "vkDestroySwapchainKHR(","vkQueueWaitIdle(","vkCmdBlitImage(",
    "vkCmdCopyImage(","pipa_framegen_vk_create_ex(",
    "PIPA_FRAMEGEN_VK_MOTION_GROUP_PER_TILE|PIPA_FRAMEGEN_VK_WARP_16X16",
    "pipa_framegen_vk_record(","g_stop.load()",
    "VK_IMAGE_LAYOUT_PRESENT_SRC_KHR",
    "rendered[index]","acquired", "std::this_thread::sleep_until",
    "NAO sao FPS fisicos exibidos",
    "Java_dev_pipa_framegen_lab_PresenterActivity_nativePresent",
    "Java_dev_pipa_framegen_lab_PresenterActivity_nativeStop",
):
    assert token in cpp,token

for token in ("SurfaceView","SurfaceHolder.Callback",
              "nativePresent(","nativeStop(","surfaceDestroyed(",
              "pipa_motion_sparse.comp.spv","pipa_interpolate_tiled.comp.spv",
              "VkSwapchainKHR","não provam FPS exibidos"):
    assert token in java,token
assert "new Intent(this,PresenterActivity.class)" in main
assert 'android:name=".PresenterActivity"' in manifest
assert "presenter.cpp" in cmake and "${ANDROID_LIBRARY}" in cmake
assert "versionCode 306" in gradle and "29.16-lab" in gradle
assert "input latency" not in java.lower()
print("EXP29_13_SWAPCHAIN_PRESENTER_SOURCE_CONTRACT=PASS; DEVICE_VULKAN_PRESENT=UNTESTED")
