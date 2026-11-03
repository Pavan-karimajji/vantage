# WP-16 (VANTAGE, C2): IMP-0101 -- the live measurement inspector `vantage-inspect`. It links the `interfaces` layout
# header and the `adas.livemeas` classes (through `livemeas`, which links AdasInterfaces), the protobuf runtime, and
# `simcore` for its `io` recording reader alone (`check --recording`); it calls no component-host code. A port
# payload is decoded only through the description's `descriptor_set` (`DynamicDecoder`), so nothing generated is
# looked up at run time (`SYS-0078`). The sources are a static `inspector_core` so the unit tests link what the
# executable runs.
find_package(protobuf REQUIRED)

add_library(inspector_core STATIC
    attach.cpp
    status_report.cpp
    decoder.cpp
    follow.cpp
    dump.cpp
    check.cpp
)
target_include_directories(inspector_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR} PRIVATE ${PROJECT_SOURCE_DIR}/src)
target_include_directories(inspector_core PUBLIC ${PROJECT_SOURCE_DIR}/src)
target_compile_features(inspector_core PUBLIC cxx_std_17)
target_link_libraries(inspector_core PUBLIC livemeas simcore protobuf::libprotobuf)
set_target_properties(inspector_core PROPERTIES ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/src/inspector")
include(${PROJECT_SOURCE_DIR}/cmake/FloatingPoint.cmake)
adas_sim_apply_fp_flags(inspector_core)

add_executable(vantage-inspect main.cpp)
target_link_libraries(vantage-inspect PRIVATE inspector_core)
target_compile_features(vantage-inspect PUBLIC cxx_std_17)

install(TARGETS vantage-inspect RUNTIME DESTINATION bin)
