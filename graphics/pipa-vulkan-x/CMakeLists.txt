cmake_minimum_required(VERSION 3.16)
project(pipa_vulkan_x LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
option(PIPA_BUILD_TESTS "Build portable frame pacing unit tests" ON)

add_library(pipa_frame_engine SHARED src/pipa_frame_engine.cpp)
target_include_directories(pipa_frame_engine PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}/include")
target_compile_options(pipa_frame_engine PRIVATE -Wall -Wextra -Werror)

if(PIPA_BUILD_TESTS)
  enable_testing()
  add_executable(pipa_frame_engine_tests tests/test_pipa_frame_engine.cpp)
  target_link_libraries(pipa_frame_engine_tests PRIVATE pipa_frame_engine)
  add_test(NAME pipa_frame_engine_tests COMMAND pipa_frame_engine_tests)
endif()
