from conan import ConanFile


class SimConan(ConanFile):
    python_requires = "adas-toolchain/1.0.0"
    python_requires_extend = "adas-toolchain.AdasComponent"
