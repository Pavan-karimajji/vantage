cmake_minimum_required(VERSION 3.22)
project(adas-sim LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# WP-03 (DD-01, SWQ-01): src/simcore is a real static-library target now
# (conf/build.yml's recipe.type: static-library) -- the Python package
# (adas_sim, installed via `pip install -e .`/pyproject.toml, unrelated to
# this file) and the C++ engine are sibling deliverables of one component.
add_subdirectory(src)
