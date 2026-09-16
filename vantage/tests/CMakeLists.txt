cmake_minimum_required(VERSION 3.22)

# Same GTest resolution modules/sim's own tests/CMakeLists.txt uses.
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

# De-duplicated 2026-09-16 (prompt 32, item 2): this used to be a hand-
# maintained BYTE COPY of modules/sim's own echo_stub fixture, justified by
# a claim that vantage "must build standalone with only this checkout
# present." That claim doesn't hold: vantage is versioned INSIDE the sim
# git repo (WP-33's own conf/build.yml top comment), not a separate
# checkout, so sim's real fixture is always right there via a relative
# path -- a hand-copied test fixture with hand-maintained include paths is
# exactly the drift CPY-1 guards against, in a directory CPY-1 does not
# scan (CPY-1 only fans out build.bat/build.sh/scripts/build.py/
# scripts/build_gui.py/.clang-format, never test fixtures). Building
# sim's own source file directly means one file, one set of include paths,
# never two copies to keep in sync by hand.
if(NOT TARGET AdasInterfaces::AdasInterfaces)
    find_package(AdasInterfaces REQUIRED)
endif()
# echo_stub.cpp uses protobuf's DescriptorPool/DynamicMessageFactory
# reflection directly (google/protobuf/descriptor.h) -- a real, direct
# dependency of this fixture file, declared explicitly rather than relied
# on transitively through AdasInterfaces (SM-02's own established
# reasoning: a consumer's own header needs are spelled out, never assumed).
find_package(protobuf REQUIRED)
add_library(vantage_test_fixture_echo_stub SHARED
    ${CMAKE_CURRENT_SOURCE_DIR}/../../tests/fixtures/echo_stub/echo_stub.cpp)
target_link_libraries(vantage_test_fixture_echo_stub PRIVATE AdasInterfaces::AdasInterfaces protobuf::libprotobuf)
# WP-33 (SM-11), named, honest workaround, corrected 2026-09-16 (same root
# cause and same fix as cpp/vantage/CMakeLists.txt's own workaround):
# `AdasInterfaces::AdasInterfaces`'s own generated INTERFACE_INCLUDE_
# DIRECTORIES comes out empty for this multi-hop graph in EVERY mode
# (package and develop alike), not "with no editables registered"
# specifically -- item 2 (prompt 38) found live that this row's own
# original fix (cache-mode-only `include/adas-interfaces`, below) is
# exactly what left `--mode develop` broken: an EDITABLE `adas-interfaces`
# resolves `adas-interfaces_PACKAGE_FOLDER_RELEASE`/`_DEBUG` to its own
# checkout root (base_recipe.py's `is_editable` branch), where headers sit
# UNNESTED under `cpp/` and (generated protobuf) `generated/` -- the
# `include/adas-interfaces/` nesting below is real, but only for a
# genuinely packaged (non-editable) `adas-interfaces`, confirmed live
# against the real cached package. All candidate subpaths are added
# unconditionally rather than branching on editable-ness, same reasoning
# as cpp/vantage/CMakeLists.txt's own copy of this fix: a directory that
# doesn't exist is simply never searched.
#
# `generated/` (echo_stub.cpp's protoc-generated `Adas__Sil/
# component_manifest.pb.h`) is NOT under PACKAGE_FOLDER directly in
# editable mode -- it's a BUILD output, under whichever target/platform
# build tree `adas-interfaces` itself was last built into
# (base_recipe.py's `_editable_target`/`_editable_platform`, imp_design.md
# §4.1). `adas-interfaces_LIB_DIRS_RELEASE`/`_DEBUG` (CMakeDeps' own,
# already target-aware) already resolves to exactly that build tree's
# `.../build/<config>` -- one directory up from it is `.../build/`, whose
# `generated/` sibling is where protoc actually wrote the header
# (confirmed live against `_LIB_DIRS_RELEASE` for THIS build, item 2).
if(DEFINED adas-interfaces_PACKAGE_FOLDER_RELEASE)
    target_include_directories(vantage_test_fixture_echo_stub PRIVATE
        "${adas-interfaces_PACKAGE_FOLDER_RELEASE}/include/adas-interfaces"
        "${adas-interfaces_PACKAGE_FOLDER_RELEASE}/cpp"
        "${adas-interfaces_PACKAGE_FOLDER_RELEASE}/include"
        "${adas-interfaces_LIB_DIRS_RELEASE}/../generated"
    )
elseif(DEFINED adas-interfaces_PACKAGE_FOLDER_DEBUG)
    target_include_directories(vantage_test_fixture_echo_stub PRIVATE
        "${adas-interfaces_PACKAGE_FOLDER_DEBUG}/include/adas-interfaces"
        "${adas-interfaces_PACKAGE_FOLDER_DEBUG}/cpp"
        "${adas-interfaces_PACKAGE_FOLDER_DEBUG}/include"
        "${adas-interfaces_LIB_DIRS_DEBUG}/../generated"
    )
endif()
# WP-33 (SM-11), named, honest workaround: `protobuf::libprotobuf`'s own
# generated INTERFACE_INCLUDE_DIRECTORIES comes out empty in this build
# (verified live in the generated data file) even though the target itself
# resolves and links -- the same class of gap `cpp/vantage/CMakeLists.txt`
# already names for `AdasInterfaces::AdasInterfaces`, not chased further
# here for the same reason. Worked around by reading the real, correct
# `protobuf_PACKAGE_FOLDER_RELEASE`/`_DEBUG` variable CMakeDeps itself
# generates.
if(DEFINED protobuf_PACKAGE_FOLDER_RELEASE)
    target_include_directories(vantage_test_fixture_echo_stub PRIVATE "${protobuf_PACKAGE_FOLDER_RELEASE}/include")
elseif(DEFINED protobuf_PACKAGE_FOLDER_DEBUG)
    target_include_directories(vantage_test_fixture_echo_stub PRIVATE "${protobuf_PACKAGE_FOLDER_DEBUG}/include")
endif()
target_compile_definitions(vantage_test_fixture_echo_stub PRIVATE ADAS_SIL_ABI_EXPORTS)
set_target_properties(vantage_test_fixture_echo_stub PROPERTIES OUTPUT_NAME "echo_stub")

# IT-23/UT-VTG-01 (WP-33, SW-0426).
add_executable(vantage_tests vantage/test_it23_vantage_bridge.cpp)
target_link_libraries(vantage_tests PRIVATE
    vantage_bridge
    GTest::gtest_main
)
target_compile_definitions(vantage_tests PRIVATE
    ADAS_SIM_TEST_FIXTURE_DIR="$<TARGET_FILE_DIR:vantage_test_fixture_echo_stub>"
)
add_dependencies(vantage_tests vantage_test_fixture_echo_stub)

include(GoogleTest)
gtest_discover_tests(vantage_tests)
