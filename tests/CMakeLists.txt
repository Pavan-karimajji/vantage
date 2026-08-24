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

# WP-10 (SI-04): echo_stub, a minimal generic-ABI component (see
# fixtures/echo_stub/echo_stub.cpp's own header) -- ported from sil_host's
# identical fixture, same reasoning: Component::Load's tests need a real,
# resolvable library implementing adas_sil_abi.h, not a mock inside the
# test binary. find_package here (not only in src/simcore/CMakeLists.txt,
# which is a sibling directory scope, not a parent of tests/) -- an
# imported target from find_package is directory-scoped, so this fixture's
# own direct `target_link_libraries(... AdasInterfaces::AdasInterfaces)`
# needs its own resolution, idempotent against Conan's already-generated
# find module.
find_package(AdasInterfaces REQUIRED)
add_library(sim_test_fixture_echo_stub SHARED fixtures/echo_stub/echo_stub.cpp)
target_link_libraries(sim_test_fixture_echo_stub PRIVATE AdasInterfaces::AdasInterfaces)
target_compile_definitions(sim_test_fixture_echo_stub PRIVATE ADAS_SIL_ABI_EXPORTS)
set_target_properties(sim_test_fixture_echo_stub PROPERTIES OUTPUT_NAME "echo_stub")

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
    # WP-08 (SI-02 bus): UT-BUS-07..13, UT-BUS-19 (CycleReconstructor).
    unit/test_ut_bus_cycle.cpp
    # WP-09 (SI-02 bus / SI-03 scheduler): PortBus + Scheduler core.
    unit/test_ut_bus_port_bus.cpp
    unit/test_ut_sch_core.cpp
    # SM-06 (SI-25, D-5): InProcessTransport's own class-level contract.
    unit/test_transport_inproc.cpp
    # SM-06 (SI-25, D-5): SharedMemoryTransport's own class-level contract.
    unit/test_transport_shm.cpp
    # WP-10 (SI-04): module_host -- exec_timeout ported unchanged (WP-10's
    # own exit criterion) plus Component/Lifecycle/Quarantine/Dso against
    # the real echo_stub fixture.
    unit/test_mh_exec_timeout.cpp
    unit/test_mh_component.cpp
    # WP-11 (SI-05): mutate -- UT-MUT-01..10, against a self-contained
    # synthetic message type (no fixture file, no AdasInterfaces dep).
    unit/test_mut_core.cpp
    # WP-13 (SI-06): runner -- UT-RUN-01..08, against a self-contained
    # synthetic in-test codec (a Reader/Writer pair over a message vector,
    # no fixture file) plus the real echo_stub for anything needing a
    # loadable Component.
    unit/test_ut_run_core.cpp
    # WP-14 (SI-09): UT-HOST-13 -- RunIsolatedStage's fail/crash/timeout
    # classification (IMP-0096). IT-11 -- simcore embedded from a host
    # that is NOT simengine, over abi/simcore.h alone (SW-0144). UT-EXE-04
    # -- the restart supervisor. UT-EXE-05 -- ExitCode coverage through
    # the real simengine binary.
    unit/test_mh_isolate.cpp
    integration/test_it11_embed_host.cpp
    integration/test_ut_exe_04_restart.cpp
    integration/test_ut_exe_05_exit_codes.cpp
    # WP-15a row 1: simcore/io (WP-06) + CycleReconstructor (WP-08) wired
    # into one recording-read-and-group capability, compared to
    # sil_host/recording_reader.cpp -- closes scripts/prove_equal.py's row 1.
    integration/test_wp15a_row1_recording_read.cpp
    # WP-15 (SI-08): engine diagnostics -- IMP-0076/0131..0140.
    unit/test_sch_dump.cpp
    unit/test_diag_graph_dump.cpp
    unit/test_diag_trace.cpp
    unit/test_diag_cost.cpp
    unit/test_diag_modules.cpp
    unit/test_diag_breakpoints.cpp
    unit/test_diag_reproducer.cpp
    integration/test_it10_graph_diff.cpp
    # WP-14a (SI-09): the embeddable ABI's real writer and real resolver
    # (IMP-0426/IMP-0427) -- UT-ABI-01/UT-ABI-02.
    integration/test_ut_abi_writer_and_resolver.cpp
    # WP-15 (SI-08): simEngineCreate wires a real Checkpoint (IMP-0139's
    # own design decision, 2026-08-24) -- UT-ABI-03.
    integration/test_ut_abi_checkpoint.cpp
    # WP-13's own IT-09 (IMP-0114): mixed record policies proved through
    # the real C ABI, closing this row's last remaining gap.
    integration/test_it09_record_policy.cpp
    # WP-27 (SI-25 transport): UT-TRN-01, a real Runner wired to both
    # transports, diffing the consumer's observed stream.
    integration/test_it_transport.cpp
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
# WP-10: a stage's own build directory, known at configure time -- lets a
# test resolve echo_stub's real path without a copy-next-to-exe step
# (sil_host/tests/CMakeLists.txt's identical ADAS_SIL_TEST_FIXTURE_DIR
# pattern, applied here).
target_compile_definitions(simcore_tests PRIVATE
    ADAS_SIM_TEST_FIXTURE_DIR="$<TARGET_FILE_DIR:sim_test_fixture_echo_stub>"
    # WP-14: UT-EXE-04/UT-EXE-05 spawn the REAL simengine binary rather
    # than asserting against its source -- the built executable's own
    # path, known at configure time, same pattern as the fixture dir above.
    SIMENGINE_EXECUTABLE="$<TARGET_FILE:simengine>"
    # WP-15: IT-10's own Python-side prediction script
    # (tests/fixtures/graph_dump/predict_graph.py) -- a source-tree path,
    # not a build output, but named as a compile definition for the same
    # reason ADAS_SIM_TEST_FIXTURE_DIR is: one place, known at configure
    # time, never a relative path a test has to guess at from its own cwd.
    IT10_FIXTURE_DIR="${CMAKE_CURRENT_SOURCE_DIR}/fixtures/graph_dump"
)
add_dependencies(simcore_tests sim_test_fixture_echo_stub simengine)

include(GoogleTest)
gtest_discover_tests(simcore_tests)
