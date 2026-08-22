# WP-14 (SI-09): the thin executable. Links `simcore` and nothing else --
# `ANL-SW-06` scans this target's binary for an interpreter symbol,
# `ANL-SW-33` scans its link line for a GUI toolkit and its source for a
# forbidden display/toolkit symbol; both must find none (SW-0142/SW-0146).
# One target, no `-DCI` variant, no headless build flag (SW-0145,
# ANL-SW-32) -- the same binary serves interactive, batch and CI use
# unchanged.
add_executable(simengine main.cpp)
target_link_libraries(simengine PRIVATE simcore)
target_compile_features(simengine PUBLIC cxx_std_17)

install(TARGETS simengine RUNTIME DESTINATION bin)
