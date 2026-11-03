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
if(NOT TARGET AdasInterfaces::AdasInterfaces)
    find_package(AdasInterfaces REQUIRED)
endif()
add_library(sim_test_fixture_echo_stub SHARED fixtures/echo_stub/echo_stub.cpp)
target_link_libraries(sim_test_fixture_echo_stub PRIVATE AdasInterfaces::AdasInterfaces)
target_compile_definitions(sim_test_fixture_echo_stub PRIVATE ADAS_SIL_ABI_EXPORTS)
set_target_properties(sim_test_fixture_echo_stub PROPERTIES OUTPUT_NAME "echo_stub")

# WP-09a (VANTAGE, C1): IMP-0042, fixture F-PROBE -- the exec probe, a component on the generic
# ABI that logs entry and exit of every adasExec() with its thread id (see
# fixtures/exec_probe/exec_probe.cpp's own header). One build; a test copies it per path.
add_library(sim_test_fixture_exec_probe SHARED fixtures/exec_probe/exec_probe.cpp)
target_link_libraries(sim_test_fixture_exec_probe PRIVATE AdasInterfaces::AdasInterfaces)
target_compile_definitions(sim_test_fixture_exec_probe PRIVATE ADAS_SIL_ABI_EXPORTS)
set_target_properties(sim_test_fixture_exec_probe PROPERTIES OUTPUT_NAME "exec_probe")

# WP-15 (VANTAGE, C2): IMP-0088 -- the stage `F-LM-HELD` adds to a lab case: reads and triggers like any stage,
# is read by nobody, and its first call returns only once a gate file exists
# (see fixtures/held_probe/held_probe.cpp's own header).
add_library(sim_test_fixture_held_probe SHARED fixtures/held_probe/held_probe.cpp)
target_link_libraries(sim_test_fixture_held_probe PRIVATE AdasInterfaces::AdasInterfaces)
target_compile_definitions(sim_test_fixture_held_probe PRIVATE ADAS_SIL_ABI_EXPORTS)
set_target_properties(sim_test_fixture_held_probe PROPERTIES OUTPUT_NAME "held_probe")

# WP-11 (VANTAGE, C1): IMP-0055, fixture F-TICK of SYT-ORC-12 -- the
# measurement_counter of the control a clock-started stage gets at tick k.
# Runs no stage and loads no library.
add_executable(control_tick support/control_tick.cpp)
target_link_libraries(control_tick PRIVATE simcore)

# WP-09a (VANTAGE, C1): IMP-0041, fixture F-TAP -- one JSON line per engine step
# (step, time, badges), optionally one jump. Built on the simEngine* ABI; reaches
# the Runner through the internal SimEngineRunner (src/simcore/abi/).
add_executable(step_tap support/step_tap.cpp)
target_link_libraries(step_tap PRIVATE simcore)
target_include_directories(step_tap PRIVATE ${CMAKE_SOURCE_DIR}/src/simcore)

# VNT-WP-09a-R1: RCT:SYT-REC-04 .c3 -- what Vantage's own C++ reader returns for a recording
# (topics, schemas, origins, the manifest and config_bundle blocks, every message), as JSON lines.
add_executable(recording_dump support/recording_dump.cpp)
target_link_libraries(recording_dump PRIVATE simcore)

# VNT-WP-13: IMP-0069, RCT:SYT-REC-03 .c3 -- a recording read through the engine's reader and written again through
# the engine's writer, so two calls compare two writer calls with the same arguments.
add_executable(rewrite_recording support/rewrite_recording.cpp)
target_link_libraries(rewrite_recording PRIVATE simcore)

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
    # WP-01 (VANTAGE, C1): LoadRunSpec reads schema 2.0 -- IMP-0001 to IMP-0004
    # and IMP-0049 (refusals by name).
    unit/test_ut_runspec_load.cpp
    # WP-02 (VANTAGE, C1): IMP-0006, IMP-0008, IMP-0009 (IMP-0010 retired the
    # cycle reconstructor and its test file).
    unit/test_ut_bus_sample_buffer.cpp
    unit/test_ut_bus_signal_header.cpp
    unit/test_ut_bus_identity.cpp
    # WP-09 (SI-02 bus / SI-03 scheduler): PortBus + Scheduler core.
    unit/test_ut_bus_port_bus.cpp
    # WP-14 (VANTAGE, C2): the live measurement writer library -- IMP-0071..IMP-0074, IMP-0076, IMP-0077.
    unit/test_livemeas_writer.cpp
    # WP-15 (VANTAGE, C2): the engine writes it through the C ABI -- IMP-0078..IMP-0084.
    unit/test_livemeas_engine.cpp
    # WP-16 (VANTAGE, C2): the inspector -- IMP-0091..IMP-0101, RCT:IMP-0038, RCT:IMP-0039.
    unit/test_inspector.cpp
    # WP-17 (VANTAGE, C2): the supervision cell and the supervisor with its seal -- IMP-0075, IMP-0103..IMP-0111, IMP-0124.
    unit/test_supervision_cell.cpp
    ../src/simengine/supervision_cell.cpp
    integration/test_wp17_supervisor.cpp
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
    # WP-03 (VANTAGE, C1): IMP-0012..IMP-0015 (IMP-0015 retired
    # test_sch_dump.cpp with the schedule dump).
    unit/test_orc_graph.cpp
    unit/test_orc_plan.cpp
    # WP-04 (VANTAGE, C1): IMP-0016..IMP-0023, IMP-0050.
    unit/test_orc_steps.cpp
    unit/test_orc_readiness.cpp
    unit/test_orc_event_log.cpp
    # WP-05 (VANTAGE, C1): RCT:IMP-0032, IMP-0026, RCT:IMP-0033, IMP-0027, IMP-0028..0030.
    unit/test_orc_control.cpp
    unit/test_run_read_ahead.cpp
    unit/test_run_select_inputs.cpp
    unit/test_run_stage.cpp
    unit/test_run_step.cpp
    # WP-07 (VANTAGE, C1): IMP-0034..IMP-0036 (threads, the same-path guard, commit order).
    unit/test_run_threads.cpp
    # WP-06 (VANTAGE, C1): IMP-0032, IMP-0033 (EqualOutputs, the divergence latch).
    unit/test_run_divergence.cpp
    # WP-15 (SI-08): engine diagnostics -- IMP-0131..0140.
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
    # RCT:WP-13 / WP-12 / WP-07 (VNT-WP-09a-R1): the engine's manifest (IMP-0052), its
    # config_bundle block (IMP-0059) and the call thread (IMP-0060), through the real C ABI.
    integration/test_wp13_engine_recording.cpp
)

add_executable(simcore_tests ${SIM_TEST_SOURCES})
target_link_libraries(simcore_tests PRIVATE
    simcore
    livemeas
    inspector_core
    GTest::gtest_main
)
# SM-05a: test_ut_io_erg_reconstruct.cpp reaches erg_wire.hpp -- an
# internal io/codecs/ helper, deliberately not part of simcore's own
# public include/ surface -- to build its OWN independent DescriptorPool
# from the fixture's manifest sidecar (never reusing ErgReader's state).
target_include_directories(simcore_tests PRIVATE ${CMAKE_SOURCE_DIR}/src/simcore ${CMAKE_SOURCE_DIR}/src ${CMAKE_SOURCE_DIR}/src/inspector ${CMAKE_SOURCE_DIR}/src/simengine ${CMAKE_CURRENT_SOURCE_DIR}/support)
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
    # WP-16: the inspector tests run the real `vantage-inspect`, and WP-17 the held_probe fixture beside echo_stub.
    VANTAGE_INSPECT_EXECUTABLE="$<TARGET_FILE:vantage-inspect>"
    # WP-15: IT-10's own Python-side prediction script
    # (tests/fixtures/graph_dump/predict_graph.py) -- a source-tree path,
    # not a build output, but named as a compile definition for the same
    # reason ADAS_SIM_TEST_FIXTURE_DIR is: one place, known at configure
    # time, never a relative path a test has to guess at from its own cwd.
    IT10_FIXTURE_DIR="${CMAKE_CURRENT_SOURCE_DIR}/fixtures/graph_dump"
)
add_dependencies(simcore_tests sim_test_fixture_echo_stub sim_test_fixture_exec_probe sim_test_fixture_held_probe simengine vantage-inspect)

include(GoogleTest)
gtest_discover_tests(simcore_tests)
