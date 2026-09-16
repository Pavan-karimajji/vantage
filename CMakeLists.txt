cmake_minimum_required(VERSION 3.22)
project(adas-sim LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# WP-03 (DD-01, SWQ-01): src/simcore is a real static-library target now
# (conf/build.yml's recipe.type: static-library) -- the Python package
# (adas_sim, installed via `pip install -e .`/pyproject.toml, unrelated to
# this file) and the C++ engine are sibling deliverables of one component.
add_subdirectory(src)

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
