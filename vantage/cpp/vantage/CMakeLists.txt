# WP-33 (SM-11): the PortFrame -> Tick bridge (IMP-0430) -- see
# frame_bridge.hpp/host_loop.hpp for the mechanism itself.
add_library(vantage_bridge STATIC
    frame_bridge.cpp
    host_loop.cpp
    engine_thread.cpp
)
set_target_properties(vantage_bridge PROPERTIES POSITION_INDEPENDENT_CODE ON)

# docs/build_superbuild_aggregator_plan.md §3 -- lets a future consumer link
# "AdasVantage::AdasVantage" whether this package is in-tree or a real Conan
# package, same convention every other component's CMakeLists.txt uses
# unconditionally (mathlib's adas-mathlib, viz's adas-viz, ...), even though
# nothing links this package by name yet.
add_library(AdasVantage::AdasVantage ALIAS vantage_bridge)

# frame_bridge.hpp/host_loop.hpp both reach modules/interfaces' own
# transport/ITransport.hpp (R-IFACE-1) directly (PortFrame is defined
# there) -- declared explicitly rather than relied on transitively through
# AdasSim::io, matching SM-02's own established reasoning that a consumer's
# real header needs are spelled out, never assumed.
if(NOT TARGET AdasInterfaces::AdasInterfaces)
    find_package(AdasInterfaces REQUIRED)
endif()

target_include_directories(vantage_bridge PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/..)
target_link_libraries(vantage_bridge PUBLIC AdasSim::io AdasViz::player AdasInterfaces::AdasInterfaces)
target_compile_features(vantage_bridge PUBLIC cxx_std_17)

# WP-33 (SM-11) / item 2 (prompt 38), named, honest workaround -- not a
# permanent fix, root cause still in Conan's own CMakeDeps generator, not
# ours to patch: the CMakeDeps-generated `AdasInterfaces::AdasInterfaces`
# imported target's own INTERFACE_INCLUDE_DIRECTORIES -- and even the raw
# `adas-interfaces_INCLUDE_DIRS_RELEASE`/`_DEBUG` variable CMakeDeps itself
# writes -- comes out EMPTY specifically for `adas-interfaces` as vantage's
# own nested `conan install` resolves it, in BOTH package and develop mode
# (SS13.3b, 2026-09-16): vantage reaches `adas-interfaces` via TWO graph
# paths (through `adas-sim` AND through `adas-viz`, both of which require
# `adas-interfaces` themselves) -- confirmed live that this is specifically
# a diamond-graph aggregation problem, not an editable-vs-cache one:
# `adas-sim` and `adas-viz` (each reached via exactly one path from
# vantage) both generate correct, non-empty `_INCLUDE_DIRS_RELEASE` in the
# same build; only `adas-interfaces` (the two-path node) comes out empty,
# in every mode tested. Worked around here, locally, by deriving the
# include path straight from `adas-interfaces_PACKAGE_FOLDER_RELEASE`/
# `_DEBUG` instead of the broken aggregation -- that variable itself is
# unaffected by the diamond-path bug and resolves correctly in both modes,
# just to a DIFFERENT root depending on mode:
#   - a real (non-editable) `adas-interfaces` package installs headers
#     nested under `include/adas-interfaces/...` (base_recipe.py's own
#     install_includedir_matches_name convention, package_info()) --
#     `_PACKAGE_FOLDER_RELEASE` there is the Conan cache package folder.
#   - an EDITABLE `adas-interfaces` resolves straight from its checkout,
#     unnested (base_recipe.py layout()'s `self.cpp.source.includedirs =
#     ["cpp", "include"]`) -- `_PACKAGE_FOLDER_RELEASE` there IS the
#     checkout root (self.recipe_folder: confirmed live,
#     "C:/adas/.../modules/interfaces"), so the cache-only nested subpath
#     (`include/adas-interfaces`) does not exist under it and silently
#     resolves nothing -- this is the actual ITransport.hpp failure this
#     item exists to fix. `--mode package` alone (no editables registered)
#     never exercises this branch, which is why item 1's own fan-out run
#     built vantage cleanly while a direct `--mode develop` build of it
#     failed with exactly this error -- reproduced live both ways.
#
# All three candidate subpaths (the cache-mode nested one, plus editable's
# own `cpp` and `include`) are added unconditionally rather than branching
# on editable-ness: a directory that does not exist is simply never
# searched by the compiler (CMake does not require an include-directory
# argument to exist, and does not warn or fail if one is absent), so this
# resolves correctly in either mode without this file having to
# independently re-derive which one it is in.
if(DEFINED adas-interfaces_PACKAGE_FOLDER_RELEASE)
    target_include_directories(vantage_bridge PUBLIC
        "${adas-interfaces_PACKAGE_FOLDER_RELEASE}/include/adas-interfaces"
        "${adas-interfaces_PACKAGE_FOLDER_RELEASE}/cpp"
        "${adas-interfaces_PACKAGE_FOLDER_RELEASE}/include")
elseif(DEFINED adas-interfaces_PACKAGE_FOLDER_DEBUG)
    target_include_directories(vantage_bridge PUBLIC
        "${adas-interfaces_PACKAGE_FOLDER_DEBUG}/include/adas-interfaces"
        "${adas-interfaces_PACKAGE_FOLDER_DEBUG}/cpp"
        "${adas-interfaces_PACKAGE_FOLDER_DEBUG}/include")
endif()
