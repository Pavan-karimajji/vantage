from conan import ConanFile
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain, cmake_layout
from pathlib import Path
import re
import yaml

# =====================================================================
# ONE conanfile.py, byte-identical in every component repo (plan.md item
# 20, docs/conanfile_commonality_plan.md). Nothing in this file is
# per-component: every real difference between components is DATA in that
# component's own conf/build.yml (the `recipe:` block and `variants:`) or
# is derived from its own CMakeLists.txt project() line. Do NOT hand-edit
# this file per component - change conf/build.yml instead. CI enforces
# `diff -q` across all copies (§8.4).
# =====================================================================


def _conf(recipe_folder):
    return yaml.safe_load((Path(recipe_folder) / "conf" / "build.yml").read_text(encoding="utf-8"))


def _editable_platform(conf, project, settings_os):
    # DF-01 (2026-08-19): layout()'s two RECIPE_EDITABLE branches used to
    # read platforms[0]["build"] unconditionally -- silently correct only
    # while exactly one platform was declared per component (every real
    # conf/build.yml, until this session). Adding a second platform
    # (ubuntu_gcc, alongside vs2026) broke it for any consumer built on
    # that second platform: editable-mode layout() has no direct signal
    # for "which platform token is this", only Conan's own auto-detected
    # settings.os -- so this matches against the token's own naming
    # convention (every real token today is "vs*" for Windows or contains
    # "ubuntu"/"linux" for Linux) rather than inventing a second,
    # independently-maintained token<->os table.
    platforms = [p["build"] for p in conf["variants"][project]["sil"]["platforms"]]
    if len(platforms) == 1:
        return platforms[0]
    os_ = str(settings_os)
    if os_ == "Windows":
        matches = [p for p in platforms if p.startswith("vs")]
    elif os_ == "Linux":
        matches = [p for p in platforms if "ubuntu" in p or "linux" in p]
    else:
        matches = []
    if len(matches) != 1:
        raise RuntimeError(
            f"cannot resolve which of this component's own declared sil platforms "
            f"{platforms} matches os={os_} -- extend _editable_platform's naming rule")
    return matches[0]


class AdasComponent(ConanFile):
    # package_type is the one recipe attribute Conan reads before any hook
    # runs, so it can't come from set_name()/init() cleanly - it's read from
    # conf/build.yml's recipe.type at class-body import time. Verified across
    # conan inspect / conan create (cache export) / graph-info-as-dependency
    # (docs/conanfile_commonality_plan.md §7.4). conf/* is `exports` (below),
    # so the cached recipe copy can read it too.
    package_type = _conf(Path(__file__).parent)["recipe"]["type"]

    settings = "os", "arch", "compiler", "build_type"

    # Real Conan option (not an env var) so `project` participates in
    # package_id automatically - plan.md item 14 Bug #16: ADAS_PROJECT read via
    # os.environ was invisible to Conan's package identity, so base and cus1
    # produced a byte-identical package_id. "ANY" (not an enumerated list) so a
    # new project needs no conanfile.py change - conf/build.yml's variants: dict
    # stays the single source of truth (an unknown project fails naturally in
    # _build_conf() with a KeyError).
    options = {
        "project": ["ANY"],
    }

    # Superset of every component's default_options. Options for a dependency
    # not in this component's graph are simply ignored by Conan, so carrying
    # yaml-cpp/protobuf toggles everywhere is harmless and keeps the file common.
    default_options = {
        "project": "base",
        "protobuf/*:shared": False,
        "protobuf/*:with_zlib": False,
        "yaml-cpp/*:shared": False,
    }

    # Supersets of every component's file sets. Conan silently ignores export
    # patterns that match nothing, so this is safe in every component. conf/ is
    # `exports` (not exports_sources) because requirements()/build_requirements()
    # and the class-body package_type read run at graph time, before
    # exports_sources are materialized - only `exports` is available that early
    # (a real `conan create` fails with FileNotFoundError otherwise; editable
    # mode never exercises that path). CMakePresets.json is deliberately NOT
    # exported: it's build.py's hand-authored presets and would collide with the
    # ones Conan's own CMakeToolchain generates for `conan create`.
    exports = "conf/*"
    exports_sources = (
        "CMakeLists.txt", "src/*", "cpp/*", "include/*", "proto/*", "cmake/*",
        "scripts/*", "projects/*",
    )

    # ---- data helpers -----------------------------------------------------
    def _build_conf_for(self, project):
        return _conf(self.recipe_folder)["variants"][project]

    def _build_conf(self):
        return self._build_conf_for(str(self.options.project))

    def _recipe_meta(self):
        return _conf(self.recipe_folder).get("recipe", {})

    def _cmake_name(self):
        # Convention: the package name maps 1:1 to its CMake target/file name,
        # so neither has to be stored as data. adas-vdy -> AdasVdy,
        # adas-shared-config -> AdasSharedConfig.
        return "".join(part.capitalize() for part in self.name.split("-"))

    # ---- identity: name + version from CMakeLists.txt / VERSION -----------
    def set_name(self):
        content = (Path(self.recipe_folder) / "CMakeLists.txt").read_text(encoding="utf-8")
        match = re.search(r"project\(\s*([A-Za-z0-9_\-]+)", content)
        if not match:
            raise RuntimeError("Could not extract project name from CMakeLists.txt")
        self.name = match.group(1)

    def set_version(self):
        cmakelists = Path(self.recipe_folder) / "CMakeLists.txt"
        content = cmakelists.read_text(encoding="utf-8")
        match = re.search(
            rf"project\(\s*{re.escape(self.name)}\s+VERSION\s+([0-9]+\.[0-9]+\.[0-9]+)",
            content, re.IGNORECASE)
        if match:
            self.version = match.group(1)
        else:
            # Components whose project() carries no VERSION (e.g. a pure-data
            # package with LANGUAGES NONE) keep their version in a VERSION file.
            self.version = (Path(self.recipe_folder) / "VERSION").read_text(encoding="utf-8").strip()

    # ---- dependencies (read straight from conf/build.yml) -----------------
    def requirements(self):
        for ref in self._build_conf().get("requires", []):
            self.requires(ref)

    def build_requirements(self):
        for ref in self._build_conf().get("tool_requires", []):
            self.tool_requires(ref)

    def layout(self):
        # plan.md item 11, docs/sil_dependency_wiring_plan.md - editable-mode
        # consumers (e.g. sil's --local df vdy) resolve headers/libs via
        # self.cpp.source/self.cpp.build below, entirely independent of
        # package()/package_info() (which only run for a real `conan create`,
        # never exercised by editable mode). Branches on this component's own
        # layout_kind and Conan's own self.package_type.
        conf_path = Path(self.recipe_folder) / "conf" / "build.yml"
        conf = yaml.safe_load(conf_path.read_text(encoding="utf-8"))
        layout_kind = conf.get("layout_kind", "output_folder")

        if layout_kind == "cmake_layout":
            # This component's OWN direct build (scripts/build.py, R-BUILD-2)
            # already gets a target/platform-prefixed build dir for free:
            # --output-folder is set to build-<target>-<platform>, and
            # Conan's cmake_layout() appends its own (default "build")
            # folders.build UNDERNEATH that base automatically -- giving
            # build-sil-vs2026/build, which is correct as-is (RECIPE_CONSUMER,
            # the literal root of that install command).
            #
            # But when this package is resolved as an EDITABLE dependency of
            # ANOTHER component's build (RECIPE_EDITABLE, e.g. df linking
            # AdasMathlib), Conan re-evaluates THIS layout() fresh with no
            # such --output-folder base to borrow -- the unpatched default
            # "build/" was used, and the real compiled library (at
            # build-sil-<platform>/build/<config>/, "sil" being the
            # canonical library-producing target, same convention the
            # output_folder branch below already hardcodes) was never found
            # there (found live 2026-08-19, DF-01: df's own plain `sil`
            # build failed resolving AdasMathlib with "Library
            # 'adas-mathlib' not found in package"). Applying the
            # sil-prefixed path unconditionally would instead double the
            # prefix for the RECIPE_CONSUMER case above (verified live:
            # build-sil-vs2026/build-sil-vs2026/build) -- the two cases need
            # different build_folder values, distinguished by recipe role.
            is_root_build = getattr(getattr(self, "_conan_node", None), "recipe", None) == "Consumer"
            if is_root_build:
                cmake_layout(self)
            else:
                platform = _editable_platform(conf, str(self.options.project), self.settings.os)
                cmake_layout(self, build_folder=f"build-sil-{platform}/build")
            # "include" alongside "cpp": interfaces (the only cmake_layout
            # component today) also ships include/ - the pure-C SIL ABI
            # header meant for any host language (S-C1a). Without this, a
            # standalone (non-aggregator) build of a consumer resolving
            # AdasInterfaces via Conan editable mode could not find
            # "adas/adas_sil_abi.h", even though the in-tree aggregator path
            # already works (CMake target_include_directories PUBLIC on
            # adas-interfaces already covers both directories there).
            self.cpp.source.includedirs = ["cpp", "include"]
            self.cpp.build.includedirs = ["generated"]
            # S-C1d: exposes cmake/ (sil_ports_generate.cmake) on a consumer's
            # CMAKE_MODULE_PATH via CMakeDeps, so df/vdy's own CMakeLists.txt
            # can `include(sil_ports_generate)` after find_package(AdasInterfaces)
            # with no sibling checkout of their own (R-SIM-11's own reasoning,
            # applied to build-time codegen rather than run-time proto classes).
            # scripts/gen_sil_ports.py is found relative to the .cmake file's own
            # CMAKE_CURRENT_LIST_DIR, not via a second builddirs entry.
            self.cpp.source.builddirs = ["cmake"]
        elif self.package_type in ("shared-library", "static-library"):
            # output_folder-kind compiled libraries: the real artifact lives
            # under build.py's own build-sil-<platform>/<build_subdir>/<config>/
            # - not a package()/install() folder, so that path is named here,
            # derived from data (component name, conf/build.yml's platform),
            # not hardcoded per component. build_subdir defaults to the
            # df/vdy-style src/platform/<comp>_sil/ tree; a component whose
            # source tree differs (sim's src/simcore/, SM-02) overrides it via
            # conf/build.yml's build_subdir/build_includedir keys rather than
            # a second branch here.
            comp = self.name.replace("adas-", "")
            platform = _editable_platform(conf, str(self.options.project), self.settings.os)
            build_type = str(self.settings.build_type) if self.settings.get_safe("build_type") else "Release"
            build_subdir = conf.get("build_subdir", f"src/platform/{comp}_sil")
            build_includedir = conf.get("build_includedir", build_subdir)
            self.folders.build = "."
            self.cpp.source.includedirs = [build_includedir]
            self.cpp.build.libdirs = [f"build-sil-{platform}/{build_subdir}/{build_type}"]
            self.cpp.build.bindirs = [f"build-sil-{platform}/{build_subdir}/{build_type}"]
        # package_type application/unknown need no override here - application
        # components are never find_package()'d by another component, and data's
        # real files sit directly in the source tree already.

    def generate(self):
        tc = CMakeToolchain(self)
        tc.generate()

        deps = CMakeDeps(self)
        deps.build_context_activated = ["protobuf"]
        deps.build_context_suffix = {"protobuf": "_BUILD"}
        deps.generate()

    # ---- build/package, defined once, no-op where package_type has nothing
    #      to compile through Conan (application: built via build.py/aggregator)
    def build(self):
        if self.package_type in ("shared-library", "static-library", "unknown"):
            cmake = CMake(self)
            enabled = self._build_conf().get("enabled_functions")
            variables = {"ENABLED_FUNCTIONS": ";".join(enabled)} if enabled else None
            cmake.configure(variables=variables)
            cmake.build()

    def package(self):
        if self.package_type in ("shared-library", "static-library", "unknown"):
            CMake(self).install()

    def package_id(self):
        # Pure-data packages (package_type unknown, e.g. shared_config) collapse
        # os/arch/compiler/build_type away - one universal package regardless of
        # profile, since the packaged content never varies by platform.
        if self.package_type == "unknown":
            self.info.clear()
            return
        # Otherwise fold every conf recipe.package_id_extra key into the hash
        # (df's enabled_functions: base 'aeb' and cus1 'aeb;bsd' become distinct
        # packages). Reads self.info.options.project, NOT self.options.project
        # ("'self.options' access in package_id() is forbidden" - hard Conan
        # error); self.info.options already mirrors the final resolved options.
        for key in self._recipe_meta().get("package_id_extra", []):
            value = self._build_conf_for(str(self.info.options.project)).get(key, [])
            setattr(self.info.options, key, ";".join(value) if isinstance(value, list) else value)

    def package_info(self):
        # Applications are never consumed by another component - nothing to
        # declare.
        if self.package_type == "application":
            return
        meta = self._recipe_meta()
        if self.package_type == "unknown":
            # Pure-data package: expose its resource dirs, no libs/includes.
            self.cpp_info.includedirs = []
            self.cpp_info.libdirs = []
            self.cpp_info.resdirs = meta.get("resdirs", ["projects"])
        elif not meta.get("components"):
            self.cpp_info.libs = meta["libs"]
            # SM-02's own live verification (2026-08-19, VZ-12's real
            # consumer): a named `recipe.components:` block is the ONLY
            # place a lib should be declared once one exists -- also
            # setting the same lib on the unnamed root cpp_info here made
            # CMakeDeps search for it twice, and in editable mode the root
            # search silently used the wrong (package-folder) libdirs while
            # the component's own libdirs resolved correctly, so
            # `find_package()` failed on the unused root target even though
            # nothing links it. A component-carrying package's root now
            # declares no libs of its own (still a real find_package()
            # target, just an empty aggregate) -- one repo (sim) exercises
            # this branch today; every other repo's root keeps declaring
            # its libs exactly as before (R-BUILD-1: still one byte-
            # identical file, difference lives in conf/build.yml data).
            self.cpp_info.libs = meta["libs"]
        conf = _conf(self.recipe_folder)
        if conf.get("layout_kind") == "cmake_layout":
            # Mirrors layout()'s editable-mode builddirs above, for a real
            # `conan create` package - untested by this stage (today's only
            # exercised path is editable mode), kept symmetric on principle
            # rather than left to silently diverge later.
            self.cpp_info.builddirs = ["cmake"]
        name = self._cmake_name()
        self.cpp_info.set_property("cmake_target_name", f"{name}::{name}")
        self.cpp_info.set_property("cmake_file_name", name)

        # VZ-12 (VIZ_Sync_Plan_v0.1.md, ANL-VZ-05): the unnamed/default
        # component auto-links every requires() by default (Conan has no
        # per-component *dependency resolution*, only per-component
        # *linking*) - fine everywhere a package's components all want the
        # same deps, wrong the day one dep exists for exactly one named
        # component (adas-sim, wanted only by viz's own `player` component
        # below). An explicit `recipe.root_requires:` list in conf/build.yml
        # restricts what the ROOT component actually links to; omitted
        # (every other recipe today) leaves the implicit auto-link-all
        # behaviour untouched, so this is additive, not a behaviour change
        # for any existing repo (R-BUILD-1: still one byte-identical file,
        # the difference lives in conf/build.yml data).
        root_requires = meta.get("root_requires")
        if root_requires is not None:
            self.cpp_info.requires = root_requires

        # SM-02 (VIZ_Sync_Plan_v0.1.md): an optional recipe.components: block
        # in conf/build.yml declares a named subset of this package's own
        # libs as a separately linkable Conan component - so far exercised
        # only by adas-sim's `io` component (a consumer links `adas-sim::io`
        # and acquires none of this package's OTHER components/libs). Empty
        # dict where no component declares itself, so every other recipe's
        # package_info() is unaffected (R-BUILD-1: this file stays byte-
        # identical; the difference lives in conf/build.yml data, same as
        # every other per-component variation this file reads).
        for comp_name, comp_meta in meta.get("components", {}).items():
            comp = self.cpp_info.components[comp_name]
            comp.libs = comp_meta.get("libs", [])
            # Same PascalCase::component naming the root already declares
            # above (cmake_target_name) - without this a component defaults
            # to the raw, lower-kebab package name (adas-sim::io) instead of
            # AdasSim::io, which is what a consumer's target_link_libraries
            # actually spells (R-NAME's PascalCase convention, applied here
            # for the first time by SM-02's own component).
            comp.set_property("cmake_target_name", f"{name}::{comp_name}")
            # Unlike the unnamed root cpp_info (which auto-links every
            # requires()), a named component gets NOTHING implicitly - a
            # consumer linking only this component needs its own transitive
            # deps spelled out here (SM-02's own live verification).
            comp.requires = comp_meta.get("requires", [])
            if conf.get("layout_kind") == "cmake_layout":
                comp.builddirs = ["cmake"]
            elif self.package_type in ("shared-library", "static-library"):
                # A named component does not inherit layout()'s self.cpp.build
                # the way the unnamed root cpp_info does (SM-02's own live
                # verification, VZ-12's real consumer) -- copied explicitly
                # rather than left to the same silent package-folder/lib
                # default this branch's root already had to stop relying on
                # above. But layout()'s self.cpp.build/.source paths are the
                # EDITABLE-mode-relative ones (build-sil-<platform>/...); a
                # real (non-editable) package's artifacts sit under
                # package_folder's plain install() layout instead (lib/bin/
                # include, from this component's own CMakeLists.txt install()
                # rules) -- copying the editable path there points at a
                # directory that never exists in a real package (found live,
                # VZ-18's own `test_erg_pull_integration.cpp` build). Same
                # node.recipe check layout() already uses for its own
                # editable-vs-consumer branch above.
                is_editable = getattr(getattr(self, "_conan_node", None), "recipe", None) == "Editable"
                if is_editable:
                    comp.libdirs = self.cpp.build.libdirs
                    comp.bindirs = self.cpp.build.bindirs
                    comp.includedirs = self.cpp.source.includedirs
                # else: leave cpp_info's own defaults (lib/bin/include under
                # package_folder), which is exactly where install() put them.
