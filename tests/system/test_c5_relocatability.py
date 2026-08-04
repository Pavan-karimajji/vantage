# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`ST-C5-1` (Python-facing half), `sim_implementation_plan.md` S-C5:
`adasInit(NULL)` resolves a real config bundle packed beside a real,
dynamically-loaded library, and that still holds after the whole tree is
relocated with no reference back to where it was built -- "a build output
plus its `config/` runs on a machine with no Conan cache and no repo
checkout" (`R-SIM-3a`).

This environment has no C++/Conan toolchain to build `df_sil` itself
(`modules/df`'s real SIL library), so this test proves the MECHANISM against
a minimal, dependency-free fixture library
(`tests/fixtures/c5_bundle_fixture/adas_fixture.cpp`, compiled here with
g++) whose `adasInit`/`adasManifest` bodies mirror
`df_interface_c.cpp`'s own S-C5 logic exactly: `resolveOwnLibraryDir()` via
`dladdr`, an `is_directory(<dir>/config)` check, `bundle.sha256` read
through into `config_bundle_sha256`. It is evidence for the mechanism, not a
substitute for building `df_sil` for real -- that proof is
`modules/df/tests/unit/sil/test_generic_abi.cpp`'s own
`AdasInitResolvesThePackedBundle` (`UT-C5-1`), run wherever a real build
exists. The `sil_host` executable's own half of `ST-C5-1` is `S-C7`'s job,
not built yet (`sim_implementation_plan.md` build order #15)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from adas_sim.contracts.component import CtypesSilComponent
from adas_sim.core.errors import EnvironmentError_

_FIXTURE_SRC = (
    Path(__file__).resolve().parents[1] / "fixtures" / "c5_bundle_fixture" / "adas_fixture.cpp"
)
_INTERFACES_SCRIPTS = Path(__file__).resolve().parents[3] / "interfaces" / "scripts"

# AR-3: the platform marker comes FIRST, deliberately. Both conditions are true
# on a typical Windows box, pytest reports whichever it matches first, and the
# g++ one said only "no C++ toolchain (g++) available" -- which reads as a gap
# in the environment when it is actually a designed boundary. A Windows
# developer then cannot tell whether ST-C5-1 is unproven or proven elsewhere.
# It is proven elsewhere: df's own AdasInitResolvesThePackedBundle (UT-C5-1)
# exercises the real GetModuleFileNameW path against the real df_sil.dll, and
# is green at 238/238. This fixture covers the POSIX dladdr path only.
pytestmark = [
    pytest.mark.skipif(
        sys.platform == "win32",
        reason=(
            "POSIX-only by design: this fixture exercises the dladdr path. "
            "df_sil's Windows path (GetModuleFileNameW) is covered for real by "
            "modules/df/tests/unit/sil/test_generic_abi.cpp::"
            "GenericAbiTest.AdasInitResolvesThePackedBundle (UT-C5-1)"
        ),
    ),
    pytest.mark.skipif(shutil.which("g++") is None, reason="no C++ toolchain (g++) available"),
]


def _compile_fixture_library(out_dir: Path) -> Path:
    lib_path = out_dir / "libadas_fixture.so"
    subprocess.run(
        ["g++", "-std=c++17", "-shared", "-fPIC", "-o", str(lib_path), str(_FIXTURE_SRC)],
        check=True, capture_output=True, text=True,
    )
    return lib_path


def _pack_bundle(bundle_dir: Path, tmp_path: Path) -> str:
    sys.path.insert(0, str(_INTERFACES_SCRIPTS))
    import pack_config_bundle  # noqa: PLC0415

    default_yaml = tmp_path / "src_default.yaml"
    default_yaml.write_text("aeb:\n  X: 1\n", encoding="utf-8")
    ego_yaml = tmp_path / "src_ego.yaml"
    ego_yaml.write_text("EGO_WHEELBASE_M: 2.7\n", encoding="utf-8")
    ports_yaml = tmp_path / "fixture.ports.yaml"
    ports_yaml.write_text("component: fixture\n", encoding="utf-8")
    return pack_config_bundle.pack(out=bundle_dir, default_yaml=default_yaml, ego_yaml=ego_yaml, ports_yaml=ports_yaml)


@pytest.fixture(autouse=True)
def _require_interfaces_checkout():
    if not _INTERFACES_SCRIPTS.is_dir():
        pytest.skip(f"interfaces submodule not checked out at {_INTERFACES_SCRIPTS}")


def test_adas_init_null_resolves_the_packed_bundle(tmp_path):
    """UT-C5-1's Python-facing half: NULL -> <library_dir>/config/, and
    adasManifest() reports the real config_bundle_sha256 the bundle hashes
    to -- read off the SAME loaded component, no second computation."""
    lib_dir = tmp_path / "libdir"
    lib_dir.mkdir()
    lib_path = _compile_fixture_library(lib_dir)
    digest = _pack_bundle(lib_dir / "config", tmp_path)

    comp = CtypesSilComponent(lib_path)
    try:
        assert comp.manifest.config_bundle_sha256 == digest
        comp.init(None)  # adasInit(NULL) -- must not raise
    finally:
        comp.shutdown()


def test_adas_init_null_fails_honestly_with_no_packed_bundle(tmp_path):
    """UT-C5-1's other side (§3.4 tier 3): no config/ beside the library ->
    NULL is genuinely unresolvable, and adasInit refuses rather than
    returning a handle computing plausible numbers from no calibration
    (NR-SIM-4). CtypesSilComponent.init() surfaces a NULL handle as
    EnvironmentError_, never a silent success."""
    lib_dir = tmp_path / "libdir"
    lib_dir.mkdir()
    lib_path = _compile_fixture_library(lib_dir)
    # Deliberately no _pack_bundle() call -- no config/ directory at all.

    comp = CtypesSilComponent(lib_path)
    assert comp.manifest.config_bundle_sha256 == ""  # nothing to report either
    with pytest.raises(EnvironmentError_):
        comp.init(None)


def test_relocated_tree_still_resolves_with_no_reference_to_where_it_was_built(tmp_path):
    """ST-C5-1: copy the built library + its config/ to a directory with no
    connection to the original build tree or checkout, and it still
    resolves -- `resolveOwnLibraryDir()` is module-relative (`dladdr`
    against its own loaded address), never a baked-in absolute path."""
    build_dir = tmp_path / "build_output"
    build_dir.mkdir()
    lib_path = _compile_fixture_library(build_dir)
    digest = _pack_bundle(build_dir / "config", tmp_path)

    relocated_dir = tmp_path / "no_relation_to_the_build" / "deeply" / "nested"
    relocated_dir.mkdir(parents=True)
    shutil.copy2(lib_path, relocated_dir / lib_path.name)
    shutil.copytree(build_dir / "config", relocated_dir / "config")
    shutil.rmtree(build_dir)  # prove nothing reaches back to the original tree

    comp = CtypesSilComponent(relocated_dir / lib_path.name)
    try:
        assert comp.manifest.config_bundle_sha256 == digest
        comp.init(None)
    finally:
        comp.shutdown()
