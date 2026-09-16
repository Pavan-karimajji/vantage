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

# WP-33 (SM-11), named, honest workaround -- not a permanent fix: the
# CMakeDeps-generated `AdasInterfaces::AdasInterfaces` imported target's own
# INTERFACE_INCLUDE_DIRECTORIES still comes out empty specifically for
# `adas-interfaces` as vantage's own nested `conan install` resolves it
# (multiple paths reaching the same node -- vantage requires both adas-sim
# and adas-viz, both of which require adas-interfaces themselves) even with
# NO editable packages registered at all (SS13.3b, 2026-09-16 -- the
# original 2026-08 finding above blamed editable mode specifically; found
# live that a plain Cache resolution hits the identical symptom once
# vantage's build is actually exercised end-to-end again, via the
# `subcomponents:` restructure). Worked around here, locally, by reading
# the SAME `adas-interfaces_PACKAGE_FOLDER_RELEASE`/`_DEBUG` variable
# CMakeDeps itself generates and already resolves correctly (confirmed
# correct in every case checked, including this one) -- fragile (an
# internal Conan variable name, not a public API) but scoped to this one
# target and clearly named as a workaround, not silently relied upon.
#
# Subdirectory corrected 2026-09-16: `adas-interfaces`'s own packaged layout
# no longer has a top-level `cpp/` folder (confirmed live against the
# cached package -- only `cmake/include/lib/scripts/share`); its headers
# install under `include/adas-interfaces/...`, and `simcore/transport.hpp`
# (adas-sim's own installed header, `AdasSim::io`'s public surface) includes
# `transport/ITransport.hpp` bare, without the `adas-interfaces/` prefix --
# confirmed by comparing against sim's OWN generated
# `adas-interfaces_INCLUDE_DIRS_RELEASE`, which correctly resolves to
# `.../include/adas-interfaces` in sim's simpler (single-path) graph. The
# old `/cpp` suffix here predates that layout and was silently wrong for
# this same reason -- it happened to never matter while the primary
# (non-workaround) mechanism worked, and this row's own fallback was never
# exercised until now.
if(DEFINED adas-interfaces_PACKAGE_FOLDER_RELEASE)
    target_include_directories(vantage_bridge PUBLIC "${adas-interfaces_PACKAGE_FOLDER_RELEASE}/include/adas-interfaces")
elseif(DEFINED adas-interfaces_PACKAGE_FOLDER_DEBUG)
    target_include_directories(vantage_bridge PUBLIC "${adas-interfaces_PACKAGE_FOLDER_DEBUG}/include/adas-interfaces")
endif()
