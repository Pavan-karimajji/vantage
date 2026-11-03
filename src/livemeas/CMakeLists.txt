# WP-14 (VANTAGE, C2): IMP-0077 -- the live measurement writer library. A static library of its own, so an
# engine that is not the resim engine can use the writer without the engine, the recording codecs or the
# component host (`ARCH §10.2`). It links the `interfaces` layout header and the generated `adas.livemeas`
# classes, the protobuf runtime, and no `simcore` target.
find_package(protobuf REQUIRED)
if(NOT TARGET AdasInterfaces::AdasInterfaces)
    find_package(AdasInterfaces REQUIRED)
endif()

if(WIN32)
    set(LIVEMEAS_REGION_SOURCE shared_region_windows.cpp)
else()
    set(LIVEMEAS_REGION_SOURCE shared_region_posix.cpp)
endif()

add_library(livemeas STATIC
    ${LIVEMEAS_REGION_SOURCE}
    cycle_encoder.cpp
    writer.cpp
    seal.cpp
)
target_include_directories(livemeas PUBLIC ${PROJECT_SOURCE_DIR}/include)
# PRIVATE: shared_region.hpp and cycle_encoder.hpp are implementation, not the package's surface; the tests
# reach them through their own include path.
target_include_directories(livemeas PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/..)
target_compile_features(livemeas PUBLIC cxx_std_17)
target_link_libraries(livemeas PUBLIC AdasInterfaces::AdasInterfaces protobuf::libprotobuf)
if(UNIX AND NOT APPLE)
    # shm_open/shm_unlink: glibc before 2.34 keeps them in librt.
    target_link_libraries(livemeas PUBLIC rt)
endif()
# conf/build.yml's one libdir is src/simcore: the archive lands beside simcore's, so an editable consumer
# finds both there, and `install` below puts both in the package's lib/.
set_target_properties(livemeas PROPERTIES ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/src/simcore")
include(${PROJECT_SOURCE_DIR}/cmake/FloatingPoint.cmake)
adas_sim_apply_fp_flags(livemeas)

install(TARGETS livemeas ARCHIVE DESTINATION lib)
