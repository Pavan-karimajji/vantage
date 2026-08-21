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
    unit/test_ut_io_mcap_roundtrip.cpp
    # SM-05a: the real .erg codec, against real fixtures (tests/fixtures/erg/).
    unit/test_ut_io_erg_reconstruct.cpp
    # Regression coverage for three real defects found in code review,
    # 2026-08-21 -- see this file's own top note.
    unit/test_ut_io_erg_negative.cpp
    # WP-07 (SI-02 bus): UT-BUS-01..06, UT-BUS-17, UT-BUS-18, UT-BUS-20..22.
    unit/test_ut_bus_header.cpp
    unit/test_ut_bus_value.cpp
    unit/test_ut_bus_config.cpp
    unit/test_ut_bus_bulk.cpp
    unit/test_ut_bus_static.cpp
    unit/test_ut_bus_catalogue.cpp
    # SM-06 (SI-25, D-5): InProcessTransport's own class-level contract.
    unit/test_transport_inproc.cpp
    # SM-06 (SI-25, D-5): SharedMemoryTransport's own class-level contract.
    unit/test_transport_shm.cpp
)

add_executable(simcore_tests ${SIM_TEST_SOURCES})
target_link_libraries(simcore_tests PRIVATE
    simcore
    GTest::gtest_main
)
# SM-05a: test_ut_io_erg_reconstruct.cpp reaches erg_wire.hpp -- an
# internal io/codecs/ helper, deliberately not part of simcore's own
# public include/ surface -- to build its OWN independent DescriptorPool
# from the fixture's manifest sidecar (never reusing ErgReader's state).
target_include_directories(simcore_tests PRIVATE ${CMAKE_SOURCE_DIR}/src/simcore)

include(GoogleTest)
gtest_discover_tests(simcore_tests)
