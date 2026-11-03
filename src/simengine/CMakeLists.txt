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

# RCT:IMP-0051: where the Python side of this target finds the one recording writer. `adas_recording.path`
# beside the executable holds the `python/` folder of the `adas-interfaces` package in THIS target's lock, so
# each target (sil, gtest) names its own and the last build never wins. Written at generate time, so a lock
# refreshed to a newer revision (R-BUILD-7) rewrites it with the next configure.
if(NOT DEFINED adas-interfaces_PACKAGE_FOLDER_RELEASE)
    find_package(AdasInterfaces REQUIRED)
endif()
file(GENERATE OUTPUT "$<TARGET_FILE_DIR:simengine>/adas_recording.path"
     CONTENT "${adas-interfaces_PACKAGE_FOLDER_RELEASE}/python\n")

install(TARGETS simengine RUNTIME DESTINATION bin)
