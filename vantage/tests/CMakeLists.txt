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

# WP-33: a COPY of modules/sim's own echo_stub fixture, not a shared
# reference -- this is a separate git repo-adjacent Conan package and must
# build standalone with only this checkout present (same reasoning
# modules/sim's own copy is itself "ported from sil_host's identical
# fixture", tests/CMakeLists.txt's own top note there).
find_package(AdasInterfaces REQUIRED)
# echo_stub.cpp uses protobuf's DescriptorPool/DynamicMessageFactory
# reflection directly (google/protobuf/descriptor.h) -- a real, direct
# dependency of this fixture file, declared explicitly rather than relied
# on transitively through AdasInterfaces (SM-02's own established
# reasoning: a consumer's own header needs are spelled out, never assumed).
find_package(protobuf REQUIRED)
add_library(vantage_test_fixture_echo_stub SHARED fixtures/echo_stub/echo_stub.cpp)
target_link_libraries(vantage_test_fixture_echo_stub PRIVATE AdasInterfaces::AdasInterfaces protobuf::libprotobuf)
# WP-33 (SM-11), named, honest workaround: `AdasInterfaces::AdasInterfaces`'s
# own generated INTERFACE_INCLUDE_DIRECTORIES comes out empty for the same
# reason cpp/vantage/CMakeLists.txt already names -- echo_stub.cpp needs
# BOTH its source headers (cpp/) and its build-generated proto headers
# (conan_workarea/build-sil-<platform>/build/generated/, `Adas__Sil/component_manifest.
# pb.h`), so both are added explicitly here rather than relied on
# transitively.
if(DEFINED adas-interfaces_PACKAGE_FOLDER_RELEASE)
    target_include_directories(vantage_test_fixture_echo_stub PRIVATE
        "${adas-interfaces_PACKAGE_FOLDER_RELEASE}/cpp"
        "${adas-interfaces_PACKAGE_FOLDER_RELEASE}/include"
        "${adas-interfaces_PACKAGE_FOLDER_RELEASE}/conan_workarea/build-sil-vs2026/build/generated"
    )
elseif(DEFINED adas-interfaces_PACKAGE_FOLDER_DEBUG)
    target_include_directories(vantage_test_fixture_echo_stub PRIVATE
        "${adas-interfaces_PACKAGE_FOLDER_DEBUG}/cpp"
        "${adas-interfaces_PACKAGE_FOLDER_DEBUG}/include"
        "${adas-interfaces_PACKAGE_FOLDER_DEBUG}/conan_workarea/build-sil-vs2026/build/generated"
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
