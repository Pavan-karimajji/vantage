# WP-03: the engine library, first real content (errors/events.cpp). No
# external deps yet -- yaml-cpp/mcap land at WP-05/WP-06 when the engine
# actually reads a spec or a recording.
add_library(simcore STATIC
    errors/events.cpp
)
target_include_directories(simcore PUBLIC ${PROJECT_SOURCE_DIR}/include)
target_compile_features(simcore PUBLIC cxx_std_17)

include(${PROJECT_SOURCE_DIR}/cmake/FloatingPoint.cmake)
adas_sim_apply_fp_flags(simcore)
