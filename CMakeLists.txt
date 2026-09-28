cmake_minimum_required(VERSION 3.22)
project(adas-sim LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# WP-03 (DD-01, SWQ-01): src/simcore is a real static-library target now
# (conf/build.yml's recipe.type: static-library) -- the Python package
# (adas_sim, installed via `pip install -e .`/pyproject.toml, unrelated to
# this file) and the C++ engine are sibling deliverables of one component.
add_subdirectory(src)

# PT-48 (python_tool_envs_plan.md D22): adas_sim ships in this package under
# python/, so a consumer's Python tool environment (viz's `parity` env,
# first_party: [adas-sim]) installs it from the Conan cache at the same
# version and recipe revision as the C++ it links -- never by reaching into
# modules/sim/src.
install(DIRECTORY src/adas_sim DESTINATION python
    PATTERN "__pycache__" EXCLUDE
    PATTERN "*.pyc" EXCLUDE)

# Item 3 (prompt 38, docs/build_superbuild_aggregator_plan.md §3): lets a
# future consumer link "AdasSim::AdasSim"/"AdasSim::io" whether this
# package is in-tree or a real Conan package, same convention viz/vantage
# already use for their own targets. Both names alias the SAME target:
# conf/build.yml's own `components: io: libs: [simcore]` names the only
# real library this recipe produces, and the unnamed root component
# (recipe.libs: [simcore]) is the SAME library -- Conan's package_info()
# gives the two CMake target names for two different consumers' existing
# spellings (vantage links AdasSim::AdasSim, viz links AdasSim::io), not
# two different binaries. Without this, in-tree aggregation (--with-all)
# has no AdasSim target at all, and a consumer's own
# `if(NOT TARGET AdasSim::io) find_package(AdasSim REQUIRED) endif()`
# guard falls through to a Cache lookup that fails outright for an
# in-tree build with no real adas-sim package in its graph (found live).
add_library(AdasSim::AdasSim ALIAS simcore)
add_library(AdasSim::io ALIAS simcore)

# WP-06: BUILD_TESTING is set by the gtest-vs2026 preset (CMakePresets.json),
# OFF by sil-vs2026 -- mirrors sil_host/CMakeLists.txt's identical guard.
if(BUILD_TESTING)
    enable_testing()
    add_subdirectory(tests)
endif()

# WP-33 (SM-11, O-7): `vantage` (the mechanism bridging a live PortFrame
# into a viz::session::Tick, IMP-0430) is NOT built here -- it cannot be, as
# a package-level Conan dependency on `adas-viz` from `adas-sim` itself is a
# real cycle (`adas-viz` already requires `adas-sim` unconditionally). It
# lives at `modules/sim/vantage/`, a second, independent Conan package
# (`adas-vantage`) in this same git repo, requiring both `adas-sim` and
# `adas-viz` as ordinary dependencies -- see that directory's own
# `conf/build.yml` and the `WP-33` plan row for the full account of why.
#
# SS13.3a restructure (done): "not built here" is about CMake/Conan package
# boundaries only, not about how you invoke a build. `conf/build.yml`'s own
# `subcomponents: [vantage]` makes this component's build entry point
# (build.bat/build.sh/scripts/build.py, unchanged) drive vantage's build
# too, automatically -- vantage has no build entry point of its own left to
# invoke separately.
