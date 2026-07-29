cmake_minimum_required(VERSION 3.22)
project(adas-sim LANGUAGES NONE)

# Pure Python package - no compiled artifact. adas_sim is installed via
# `pip install -e .` (pyproject.toml), not via this CMakeLists.txt. This file
# exists only so conanfile.py's byte-identical recipe (R-BUILD-1) - which
# reads the package name from project() and runs a configure/build/install
# pass for every package_type including "unknown" - has something valid and
# trivial to configure against, same shape as modules/shared_config.
