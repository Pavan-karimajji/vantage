# WP-03: the engine library, first real content (errors/events.cpp).
# WP-05 (DD-02): runspec/load.cpp is the first real dependency -- a
# vendored single-header JSON reader under third_party/, never a Conan
# package (the design's own "single-header" choice).
# WP-06 (SI-01): the io contract + the one codec DD-13 registers now --
# mcap/1.2.0 (conancenter), the same library sil_host already vendors.
find_package(mcap REQUIRED)
# SM-05a: the `.erg` codec's DescriptorPool/DynamicMessageFactory
# reflection engine -- third-party (conancenter), same pin every other
# component in this repo uses.
find_package(protobuf REQUIRED)
# SM-06 (SI-25, D-5): the player<->engine Transport contract lives in
# modules/interfaces (R-IFACE-1) -- this is the one first-party dependency
# simcore's own conf/build.yml comment (above WP-06) used to say it never
# needed. `io`'s own named Conan component keeps its separate, narrower
# `requires:` list (conf/build.yml), so `io` alone still requires nothing
# first-party; only the whole-engine root target gains this edge.
find_package(AdasInterfaces REQUIRED)

add_library(simcore STATIC
    errors/events.cpp
    runspec/load.cpp
    io/registry.cpp
    io/reader_base.cpp
    io/writer_base.cpp
    io/decode.cpp
    io/translate.cpp
    io/meta.cpp
    io/codecs/mcap.cpp
    io/codecs/erg.cpp
    io/codecs/erg_wire.cpp
    # WP-07 (SI-02): the signal header, Origin, bulk-array references, the
    # PortKind::Static rule and the port catalogue.
    bus/header.cpp
    bus/value.cpp
    bus/static_data.cpp
    bus/bulk.cpp
    bus/catalogue.cpp
    # SM-06 (SI-25, D-5): the engine-side implementations behind
    # modules/interfaces' ITransport contract.
    transport/inproc.cpp
    transport/shm.cpp
)
target_include_directories(simcore PUBLIC ${PROJECT_SOURCE_DIR}/include)
# PRIVATE: third_party/ is an implementation detail of simcore's own .cpp
# files (nlohmann/json never appears in a public include/simcore/*.hpp
# signature), so a consumer linking simcore never needs this on its own
# include path.
target_include_directories(simcore PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_features(simcore PUBLIC cxx_std_17)
# PUBLIC: `io.hpp` names `Reader`/`Writer` etc. but never an mcap type in a
# public signature (`ANL-SW-04`'s own "simcore opens no .yaml" cousin: no
# codec-library type leaks above `io`) -- linked PUBLIC anyway because
# `mcap::mcap` is a compiled library a consumer of `simcore.lib` must also
# link against at the final executable, same reasoning `sil_host`'s own
# `sil_core` target already applies to this identical dependency.
target_link_libraries(simcore PUBLIC mcap::mcap protobuf::libprotobuf AdasInterfaces::AdasInterfaces)
if(UNIX AND NOT APPLE)
    # SM-06: SharedMemoryTransport's shm_open/shm_unlink -- glibc < 2.34
    # ships these in librt, not libc; linking it unconditionally on Linux
    # costs nothing on newer glibc (the symbols are already satisfied) and
    # is what makes ubuntu_gcc a portable target rather than "whatever
    # glibc the dev box happens to have".
    target_link_libraries(simcore PUBLIC rt)
endif()

include(${PROJECT_SOURCE_DIR}/cmake/FloatingPoint.cmake)
adas_sim_apply_fp_flags(simcore)

# SM-02: a real `conan create` calls CMake.install() (conanfile.py's
# package()) -- with no install() rule here that step silently produced an
# empty package ("No files in this package!", live 2026-08-19), even though
# build.py's own build-sil-<platform>/ tree (conanfile.py's editable-mode
# layout()) never needed one. Both consumers now get the same two artifacts.
install(TARGETS simcore ARCHIVE DESTINATION lib)
install(DIRECTORY ${PROJECT_SOURCE_DIR}/include/ DESTINATION include)
