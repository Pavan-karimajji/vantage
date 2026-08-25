cmake_minimum_required(VERSION 3.22)
project(adas-vantage VERSION 0.1.0 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# WP-33 (SM-11, O-7): a second, independent Conan package inside the
# modules/sim git repo -- conf/build.yml's own top comment has the full
# "why not adas-sim itself" account. Resolved as ordinary Conan
# dependencies, never in-tree -- no aggregator, no ordering tricks needed,
# because neither `adas-sim` nor `adas-viz` depends back on this package.
find_package(AdasSim REQUIRED)
find_package(AdasViz REQUIRED)

add_subdirectory(cpp/vantage)

if(BUILD_TESTING)
    enable_testing()
    add_subdirectory(tests)
endif()
