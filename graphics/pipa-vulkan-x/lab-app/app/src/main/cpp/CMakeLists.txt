cmake_minimum_required(VERSION 3.22.1)
project(pipa_framegen_lab LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
get_filename_component(PIPA_VULKAN_X "${CMAKE_CURRENT_LIST_DIR}/../../../../.." ABSOLUTE)
add_library(pipa_lab SHARED
    lab.cpp
    presenter.cpp
    "${PIPA_VULKAN_X}/src/pipa_framegen_vk.cpp")
target_include_directories(pipa_lab PRIVATE "${PIPA_VULKAN_X}/include")
find_library(VULKAN_LIBRARY vulkan REQUIRED)
find_library(LOG_LIBRARY log REQUIRED)
find_library(ANDROID_LIBRARY android REQUIRED)
target_link_libraries(pipa_lab PRIVATE ${VULKAN_LIBRARY} ${LOG_LIBRARY} ${ANDROID_LIBRARY})
target_compile_options(pipa_lab PRIVATE -Wall -Wextra -Werror)
