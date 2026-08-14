# WP-03: the engine library, first real content (errors/events.cpp).
# WP-05 (DD-02): runspec/load.cpp is the first real dependency -- a
# vendored single-header JSON reader under third_party/, never a Conan
# package (the design's own "single-header" choice); mcap lands at WP-06
# when the engine reads a recording.
add_library(simcore STATIC
    errors/events.cpp
    runspec/load.cpp
)
target_include_directories(simcore PUBLIC ${PROJECT_SOURCE_DIR}/include)
# PRIVATE: third_party/ is an implementation detail of simcore's own .cpp
# files (nlohmann/json never appears in a public include/simcore/*.hpp
# signature), so a consumer linking simcore never needs this on its own
# include path.
target_include_directories(simcore PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_features(simcore PUBLIC cxx_std_17)

include(${PROJECT_SOURCE_DIR}/cmake/FloatingPoint.cmake)
adas_sim_apply_fp_flags(simcore)
