# WP-33 (SM-11): the PortFrame -> Tick bridge (IMP-0430) -- see
# frame_bridge.hpp/host_loop.hpp for the mechanism itself.
add_library(vantage_bridge STATIC
    frame_bridge.cpp
    host_loop.cpp
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

# WP-33 (SM-11), named, honest workaround -- not a permanent fix: even after
# conanfile.py's editable-mode includedirs override (this pass's own fix,
# verified correct by direct instrumentation -- self.cpp_info.includedirs
# reads ["cpp", "include"] exactly as expected), the CMakeDeps-generated
# `AdasInterfaces::AdasInterfaces` imported target's own
# INTERFACE_INCLUDE_DIRECTORIES still comes out empty specifically when
# `adas-interfaces` is resolved as an EDITABLE package two hops away
# (vantage -> sim/viz -> interfaces) rather than a direct one (vantage ->
# sim, vantage -> viz, both correct) -- a real, unexplained Conan/CMakeDeps
# limit in how it regenerates a transitively-reached editable node's own
# per-config data file, not a bug this pass's package_info() changes can
# reach. Worked around here, locally, by reading the SAME
# `adas-interfaces_PACKAGE_FOLDER_RELEASE`/`_DEBUG` variable CMakeDeps
# itself generates and already resolves correctly (confirmed correct in
# every case checked) -- fragile (an internal Conan variable name, not a
# public API) but scoped to this one target and clearly named as a
# workaround, not silently relied upon.
if(DEFINED adas-interfaces_PACKAGE_FOLDER_RELEASE)
    target_include_directories(vantage_bridge PUBLIC "${adas-interfaces_PACKAGE_FOLDER_RELEASE}/cpp")
elseif(DEFINED adas-interfaces_PACKAGE_FOLDER_DEBUG)
    target_include_directories(vantage_bridge PUBLIC "${adas-interfaces_PACKAGE_FOLDER_DEBUG}/cpp")
endif()
