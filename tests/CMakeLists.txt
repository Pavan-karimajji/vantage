cmake_minimum_required(VERSION 3.22)

# Same GTest resolution df/tests, sil_host/tests use: system/package-manager
# copy first, FetchContent fallback -- not a third, differently-configured
# copy of this logic.
find_package(GTest QUIET)

if(NOT GTest_FOUND)
    message(STATUS "GTest not found locally. Fetching GoogleTest from GitHub...")
    include(FetchContent)
    FetchContent_Declare(
        googletest
        URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.zip
    )
    set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
    FetchContent_MakeAvailable(googletest)
endif()

# WP-06: modules/sim's first C++ test binary (WP-03's own scoping note: "no
# gtest target, no C++ tests exist yet"). UT-IO-01..21 (io codec contract).
set(SIM_TEST_SOURCES
    unit/test_ut_io_codec_contract.cpp
    unit/test_ut_io_streaming_and_memory.cpp
    unit/test_ut_io_translate.cpp
    unit/test_ut_io_meta.cpp
    unit/test_ut_io_writer.cpp
)

add_executable(simcore_tests ${SIM_TEST_SOURCES})
target_link_libraries(simcore_tests PRIVATE
    simcore
    GTest::gtest_main
)

include(GoogleTest)
gtest_discover_tests(simcore_tests)
