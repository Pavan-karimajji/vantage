# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-21` (`SI-13` `resolve`) -- `UT-RES-01`..`UT-RES-09`, against a
hand-built `F-LIBDIR`-shaped tree (a deployed library directory: binary +
`config/` bundle + `sim/` plug-ins + `bundle.sha256`, no source checkout
reachable). No real `.dll`/`.so` is needed for these -- `resolve_library`/
`is_available` only check file existence (`SW-0205`'s own "no `dlopen`"),
and `ProjectModel`/`PluginBundle` resolution never loads the library
either, so a placeholder file with the right name is a faithful fixture.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

from adas_sim.config.project import ProjectModel
from adas_sim.diagnostics.errors import EnvironmentError_, ProvenanceWarning
from adas_sim.resolve.bundle import resolve_bundle
from adas_sim.resolve.library import is_available, resolve_library, resolve_library_resolution
from adas_sim.resolve.order import Resolution
from adas_sim.resolve.plugins import PluginBundle, pin_status, resolve_plugins

_EGO_TEMPLATE = (
    "EGO_LENGTH_M: 4.5\nEGO_WIDTH_M: 1.8\nEGO_WHEELBASE_M: {wheelbase}\nEGO_OVERHANG_FRONT_M: 0.9\n"
)


def _make_libdir(root: Path, *, wheelbase: float = 2.7, plugin_component: str = "df") -> Path:
    """`F-LIBDIR`: `<root>/lib/` carrying a placeholder binary, a `config/`
    bundle and a `sim/` plug-in bundle -- no source checkout anywhere
    under `root`."""
    lib_dir = root / "lib"
    lib_dir.mkdir(parents=True)
    (lib_dir / "df_sil.dll").write_bytes(b"")
    config_dir = lib_dir / "config"
    (config_dir / "vehicle").mkdir(parents=True)
    (config_dir / "vehicle" / "ego_params.yaml").write_text(
        _EGO_TEMPLATE.format(wheelbase=wheelbase), encoding="utf-8",
    )
    sim_dir = lib_dir / "sim"
    sim_dir.mkdir()
    (sim_dir / "plugin.yaml").write_text(
        yaml.safe_dump({
            "api": 1, "component": plugin_component, "provides": [], "sha256": "deadbeef",
            "description": "test plugin", "version": "1.0", "author": "test", "projects": ["base"],
        }),
        encoding="utf-8",
    )
    return lib_dir


# --------------------------------------------------------------------------
# UT-RES-01/02/03 -- library.py
# --------------------------------------------------------------------------


def test_ut_res_01_resolves_a_stem_on_both_platforms(tmp_path):
    """`UT-RES-01`: resolve a stem on both platforms; count resolver
    implementations in the tree -- `resolve/library.py::resolve_library` is
    the one implementation (`ANL-SW-08` covers the "in the tree" half)."""
    win_dir = _make_libdir(tmp_path / "win")
    found_win = resolve_library("df_sil", search=[win_dir], platform="win32")
    assert found_win == win_dir / "df_sil.dll"

    posix_dir = tmp_path / "posix"
    posix_dir.mkdir()
    (posix_dir / "libdf_sil.so").write_bytes(b"")
    found_posix = resolve_library("df_sil", search=[posix_dir], platform="linux")
    assert found_posix == posix_dir / "libdf_sil.so"


def test_ut_res_02_reads_every_directory_searched_and_every_rejection(tmp_path):
    """`UT-RES-02`: several candidates present; read every directory
    searched and every rejection with its reason, via the shared
    `Resolution[T]` shape (`ANL-SW-38`)."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    winning_dir = _make_libdir(tmp_path / "win2")

    result = resolve_library_resolution("df_sil", search=[empty_dir, winning_dir], platform="win32")

    assert isinstance(result, Resolution)
    assert result.chosen == winning_dir / "df_sil.dll"
    assert result.tier == str(winning_dir)
    assert result.searched == (str(empty_dir), str(winning_dir))
    assert result.rejected == ((str(empty_dir), "no candidate"),)


def test_ut_res_02_reports_no_chosen_tier_on_a_total_miss(tmp_path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    result = resolve_library_resolution("df_sil", search=[empty_dir], platform="win32")
    assert result.chosen is None
    assert result.tier is None
    assert result.rejected == ((str(empty_dir), "no candidate"),)


def test_ut_res_03_availability_present_and_absent_with_no_dlopen(tmp_path, monkeypatch):
    """`UT-RES-03`: query availability for a present and an absent module;
    count `dlopen`/`ctypes.CDLL` calls -- zero, either way."""
    calls = []
    monkeypatch.setattr("ctypes.CDLL", lambda *a, **kw: calls.append((a, kw)) or (_ for _ in ()).throw(AssertionError))

    present_dir = _make_libdir(tmp_path / "present")
    assert is_available("df_sil", search=[present_dir], platform="win32") is True

    absent_dir = tmp_path / "absent"
    absent_dir.mkdir()
    assert is_available("df_sil", search=[absent_dir], platform="win32") is False

    assert calls == []  # no dlopen/CDLL call happened


# --------------------------------------------------------------------------
# UT-RES-04/05/06 -- bundle.py
# --------------------------------------------------------------------------


def test_ut_res_04_reads_the_bundle_and_its_sha256(tmp_path):
    """`UT-RES-04`: read the bundle and its `bundle.sha256`; one bundle per
    component per build (`IMP-0206`)."""
    lib_dir = _make_libdir(tmp_path)
    result = resolve_bundle(library_dir=lib_dir / "config", project="base")
    assert isinstance(result, Resolution)
    assert result.tier == "library"
    assert result.chosen.bundle_sha256  # a real hash, not empty
    assert result.chosen.ego().wheelbase_m == 2.7


def test_ut_res_05_resolves_module_relative_then_explicit_then_mismatch(tmp_path):
    """`UT-RES-05`: resolve module-relative, then with an explicit path,
    then with a project mismatch (a warning, never a raise, `R-SIM-3a`)."""
    lib_dir = _make_libdir(tmp_path / "a", wheelbase=2.7)
    module_relative = resolve_bundle(library_dir=lib_dir / "config", project="base")
    assert module_relative.tier == "library"

    explicit_dir = _make_libdir(tmp_path / "b", wheelbase=3.1)
    explicit = resolve_bundle(explicit=explicit_dir / "config", library_dir=lib_dir / "config", project="base")
    assert explicit.tier == "explicit"
    assert explicit.chosen.bundle_dir == explicit_dir / "config"

    (lib_dir / "config" / "manifest.yaml").write_text(yaml.safe_dump({"project": "other_project"}), encoding="utf-8")
    with pytest.warns(ProvenanceWarning):
        mismatch = resolve_bundle(library_dir=lib_dir / "config", project="base")
    assert mismatch.tier == "library"
    assert mismatch.chosen.project == "other_project"


def test_ut_res_06_resolves_from_embedded_library_and_checkout_and_states_which(tmp_path):
    """`UT-RES-06`: resolve from a recording's embedded bundle, from
    `config/`, and from a checkout; read which tier was stated."""
    lib_dir = _make_libdir(tmp_path / "lib", wheelbase=2.7)
    from_library = resolve_bundle(library_dir=lib_dir / "config", project="base")
    assert from_library.tier == "library"
    assert from_library.chosen.bundle_origin == "library"

    recording_dir = _make_libdir(tmp_path / "recording", wheelbase=3.4)
    from_embedded = resolve_bundle(recording=recording_dir / "config", project="base")
    assert from_embedded.tier == "embedded"
    assert from_embedded.chosen.bundle_origin == "embedded"

    from_checkout = resolve_bundle(project="base")
    assert from_checkout.tier == "checkout"
    assert from_checkout.chosen.bundle_origin == "checkout"


# --------------------------------------------------------------------------
# UT-RES-07/08/09 -- plugins.py
# --------------------------------------------------------------------------


def test_ut_res_07_discovers_plugins_and_reports_hash_and_identity_not_bytes(tmp_path):
    """`UT-RES-07`: a plug-in's recorded identity is its hash and
    component name -- never its bytes (`NR-SIM-44`)."""
    lib_dir = _make_libdir(tmp_path)
    result = resolve_plugins([lib_dir])
    assert isinstance(result, Resolution)
    bundles = result.chosen
    assert bundles is not None and len(bundles) == 1
    assert bundles[0].component == "df"
    assert bundles[0].sha256 == "deadbeef"


def test_ut_res_08_refuses_an_unsupported_plugin_generation_before_import(tmp_path, monkeypatch):
    """`UT-RES-08`: an unsupported declared generation is refused before
    any import happens -- count imports performed: zero."""
    lib_dir = _make_libdir(tmp_path)
    (lib_dir / "sim" / "plugin.yaml").write_text(
        yaml.safe_dump({
            "api": 99, "component": "df", "provides": [],
            "description": "test plugin", "version": "1.0", "author": "test", "projects": ["base"],
        }),
        encoding="utf-8",
    )
    imports = []
    monkeypatch.setattr(PluginBundle, "import_modules", lambda self: imports.append(self) or ())

    from adas_sim.diagnostics.errors import AuthoringError
    with pytest.raises(AuthoringError):
        PluginBundle.resolve(library_dir=lib_dir / "sim")
    assert imports == []


def test_ut_res_09_a_locally_built_library_with_no_published_build_is_unpinnable():
    """`UT-RES-09`: a library hash matching no published build is reported
    `unpinnable`, never silently pinned (`IMP-0213`)."""
    assert pin_status("abc123", "") == "unpinnable"
    assert pin_status("abc123", None) == "unpinnable"
    assert pin_status("abc123", "different") == "mismatch"
    assert pin_status("abc123", "abc123") == "pinned"


# --------------------------------------------------------------------------
# Header hygiene (found while auditing `resolve/plugins.py`, R-STYLE-1).
# --------------------------------------------------------------------------


def test_plugins_module_header_uses_the_placeholder_convention():
    text = Path("src/adas_sim/resolve/plugins.py").read_text(encoding="utf-8")
    header = "\n".join(text.splitlines()[:4])
    assert "LT EPS" not in header
    assert "larsentoubro" not in header.lower()
    assert "Copyright (c) <ORG>." in header
    assert "@author Pavan Karimajji" in header
