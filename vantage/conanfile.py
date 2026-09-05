from conan import ConanFile


class VantageConan(ConanFile):
    python_requires = "adas-toolchain/1.0.1"
    python_requires_extend = "adas-toolchain.AdasComponent"
