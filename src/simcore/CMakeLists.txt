# WP-03: the engine library, first real content (errors/events.cpp).
# WP-05 (DD-02): runspec/load.cpp is the first real dependency -- a
# vendored single-header JSON reader under third_party/, never a Conan
# package (the design's own "single-header" choice).
# WP-06 (SI-01): the io contract + the one codec DD-13 registers now --
# mcap/1.2.0 (conancenter), the same library sil_host already vendors.
find_package(mcap REQUIRED)

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
target_link_libraries(simcore PUBLIC mcap::mcap)

include(${PROJECT_SOURCE_DIR}/cmake/FloatingPoint.cmake)
adas_sim_apply_fp_flags(simcore)
