from conan import ConanFile


class VantageConan(ConanFile):
    python_requires = "adas-toolchain/1.0.4"
    python_requires_extend = "adas-toolchain.AdasComponent"
