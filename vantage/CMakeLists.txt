cmake_minimum_required(VERSION 3.22)
project(adas-vantage VERSION 0.1.0 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# WP-33 (SM-11, O-7): a second, independent Conan package inside the
# modules/sim git repo -- conf/build.yml's own top comment has the full
# "why not adas-sim itself" account. Resolved as ordinary Conan
# dependencies, never in-tree -- no aggregator, no ordering tricks needed,
# because neither `adas-sim` nor `adas-viz` depends back on this package.
if(NOT TARGET AdasSim::AdasSim)
    find_package(AdasSim REQUIRED)
endif()
if(NOT TARGET AdasViz::AdasViz)
    find_package(AdasViz REQUIRED)
endif()

add_subdirectory(cpp/vantage)

# WP-34 (SM-11): same TARGET_TYPE cache-var gate df's/perception-core's own
# root CMakeLists.txt already use for their own sil-only executable
# subdirectory -- vantage_bridge (above) stays buildable unconditionally
# (the gtest target links it directly), while vantage_app (the real
# windowed main()) is gated the same way a component's platform host always
# is. Defaults to "sil" so a plain `-p vs2026` build (sil or gtest -- this
# package's own build.py invocation never passes -DTARGET_TYPE) always
# includes it.
if(NOT DEFINED TARGET_TYPE)
    set(TARGET_TYPE sil CACHE STRING "Build target: sil")
endif()
if(TARGET_TYPE STREQUAL "sil")
    add_subdirectory(cpp/vantage_app)
endif()

if(BUILD_TESTING)
    enable_testing()
    add_subdirectory(tests)
endif()
