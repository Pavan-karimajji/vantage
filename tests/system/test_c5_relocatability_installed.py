# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

"""`ST-C5-1`, the real half: `sim_implementation_plan.md`'s S-C5
audit found the config bundle travelled with `df_sil`'s own *build* directory
(the `POST_BUILD` packing step) but was never `install()`-ed, so a real
`df_sil` resolved through Conan packaging -- which is how `sil_host` gets it
-- could never satisfy `adasInit(NULL)`. `tests/system/test_c5_relocatability.py`
proves the mechanism against a POSIX-only, dependency-free fixture and
explicitly defers the real `df_sil` proof to `df`'s own gtest
(`AdasInitResolvesThePackedBundle`) -- but that gtest runs from
`df_tests.exe`'s *build*-tree copy (`copy_directory`), not the installed
package, so it never exercised the `install()` rule this stage's own fix
added. This test does: `cmake --install` the real `df_sil` build into an
isolated prefix, relocate that prefix somewhere with no path back to the
original build tree, strip the process `PATH` down to just the relocated
`bin/` + the OS system directories (no Conan cache, no repo checkout
reachable), and confirm `adasInit(NULL)` still resolves.

Skips with a named reason if no real `df_sil` build exists here (partial
clone / different platform) -- never fabricates the result."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from adas_sim.contracts.component import CtypesSilComponent
from adas_sim.core.errors import EnvironmentError_

SIM_ROOT = Path(__file__).resolve().parent.parent.parent
MODULES_ROOT = SIM_ROOT.parent
DF_ROOT = MODULES_ROOT / "df"
_SIL_BUILD_DIR = DF_ROOT / "build-sil-vs2026"

_SKIP_REASON_NO_BUILD = (
    "no configured modules/df/build-sil-vs2026 (partial clone, or `sil` target not built here)"
)
_SKIP_REASON_NO_CMAKE = "cmake not found on PATH -- needed to exercise the real install() rule"

_LIB_NAME = "df_sil.dll" if sys.platform == "win32" else "libdf_sil.so"
_BUNDLE_DESTDIR = "bin" if sys.platform == "win32" else "lib"


def _configured_build_type() -> str | None:
    for build_type in ("Release", "Debug"):
        if (_SIL_BUILD_DIR / "src" / "platform" / "df_sil" / build_type / _LIB_NAME).is_file():
            return build_type
    return None


@pytest.fixture(autouse=True)
def _require_real_sil_build():
    if not (_SIL_BUILD_DIR / "CMakeCache.txt").is_file() or _configured_build_type() is None:
        pytest.skip(_SKIP_REASON_NO_BUILD)
    if shutil.which("cmake") is None:
        pytest.skip(_SKIP_REASON_NO_CMAKE)


def _install_real_df_sil(prefix: Path) -> Path:
    """Runs the actual `cmake --install` step -- the rule `AR-1` added -- into
    `prefix`, never a hand-copy of the build tree (that would prove nothing
    about the `install()` rule itself)."""
    build_type = _configured_build_type()
    subprocess.run(
        ["cmake", "--install", str(_SIL_BUILD_DIR), "--config", build_type, "--prefix", str(prefix)],
        check=True, capture_output=True, text=True,
    )
    lib_path = prefix / _BUNDLE_DESTDIR / _LIB_NAME
    assert lib_path.is_file(), f"install() did not produce {lib_path}"
    assert (lib_path.parent / "config" / "bundle.sha256").is_file(), (
        f"install() did not ship config/ beside {lib_path.name} -- the exact AR-1 regression"
    )
    return lib_path


def test_installed_tree_resolves_adas_init_null_with_no_conan_cache_reachable(tmp_path):
    installed = _install_real_df_sil(tmp_path / "installed")

    # Relocate to a directory with no relation to the build tree or the
    # install-time prefix, then remove the original -- same idiom as
    # test_c5_relocatability.py's fixture-based proof, applied to the real
    # artefact.
    relocated_dir = tmp_path / "no_relation_to_the_build" / "deeply" / "nested" / _BUNDLE_DESTDIR
    relocated_dir.mkdir(parents=True)
    for item in installed.parent.iterdir():
        dest = relocated_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)
    shutil.rmtree(tmp_path / "installed")

    expected_sha256 = (relocated_dir / "config" / "bundle.sha256").read_text(encoding="utf-8").strip()
    assert len(expected_sha256) == 64 and all(c in "0123456789abcdef" for c in expected_sha256)

    relocated_lib = relocated_dir / _LIB_NAME

    # The rigorous part: strip PATH to exactly the relocated bin dir plus the
    # OS's own system directories, so nothing in the Conan cache or this repo
    # checkout is reachable while the DLL loads and resolves its bundle.
    old_path = os.environ.get("PATH", "")
    if sys.platform == "win32":
        windir = os.environ.get("SYSTEMROOT", r"C:\Windows")
        minimal_path = os.pathsep.join([str(relocated_dir), windir, str(Path(windir) / "System32")])
    else:
        minimal_path = os.pathsep.join([str(relocated_dir), "/usr/bin", "/bin"])
    os.environ["PATH"] = minimal_path
    try:
        comp = CtypesSilComponent(relocated_lib)
        try:
            assert comp.manifest.config_bundle_sha256 == expected_sha256
            assert comp.manifest.project  # AR-1: project is also resolved, never blank
            comp.init(None)  # adasInit(NULL) -- must not raise EnvironmentError_
        finally:
            comp.shutdown()
    finally:
        os.environ["PATH"] = old_path


def test_installed_tree_with_config_removed_fails_honestly(tmp_path):
    """The tier-3 negative, against the real artefact: an installed df_sil
    with its config/ deleted must NOT fall back to a parent directory or the
    source checkout (`S-C1b`'s delta) -- `adasInit(NULL)` stays genuinely
    unresolvable (`NR-SIM-4`)."""
    installed = _install_real_df_sil(tmp_path / "installed")
    shutil.rmtree(installed.parent / "config")

    comp = CtypesSilComponent(installed)
    assert comp.manifest.config_bundle_sha256 == ""
    with pytest.raises(EnvironmentError_):
        comp.init(None)
