# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

"""`ST-C8-1`/`ST-C8-2` (`sim_implementation_plan.md` S-C8): the plug-in
bundle's relocatability proof, sibling of `test_c5_relocatability_installed.
py` and run the same way -- a real `df_sil` `cmake --install`, relocated away
from the build tree, with the original installed copy removed before
resolving. `ST-C8-2` is the strong form S-C8's own gate names: `ST-C8-1`
alone can pass while a checkout is silently supplying a module, so this
proves the deployed `sim/` bundle is self-sufficient by deleting the
installed copy's *origin* (not just adding a second copy elsewhere) before
ever calling `PluginBundle.resolve`.

"Renders" here means the load-and-register half: `PluginBundle.resolve` +
`import_modules()` genuinely import `df`'s real `sim/layers/{common,bsd}.py`
from the relocated bundle alone and register their real layer ids into
`scene.registry` -- the same mechanism a full Vantage render depends on,
short of an actual GUI frame (mirrors `S-C5`'s own split between a
mechanism proof and the real artefact).

Skips with a named reason if no real `df_sil` build exists here."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SIM_ROOT = Path(__file__).resolve().parent.parent.parent
MODULES_ROOT = SIM_ROOT.parent
DF_ROOT = MODULES_ROOT / "df"
_SIL_BUILD_DIR = DF_ROOT / "build-sil-vs2026"

_SKIP_REASON_NO_BUILD = (
    "no configured modules/df/build-sil-vs2026 (partial clone, or `sil` target not built here)"
)
_SKIP_REASON_NO_CMAKE = "cmake not found on PATH -- needed to exercise the real install() rule"

_BUNDLE_DESTDIR = "bin" if sys.platform == "win32" else "lib"


def _configured_build_type() -> str | None:
    lib_name = "df_sil.dll" if sys.platform == "win32" else "libdf_sil.so"
    for build_type in ("Release", "Debug"):
        if (_SIL_BUILD_DIR / "src" / "platform" / "df_sil" / build_type / lib_name).is_file():
            return build_type
    return None


@pytest.fixture(autouse=True)
def _require_real_sil_build():
    if not (_SIL_BUILD_DIR / "CMakeCache.txt").is_file() or _configured_build_type() is None:
        pytest.skip(_SKIP_REASON_NO_BUILD)
    if shutil.which("cmake") is None:
        pytest.skip(_SKIP_REASON_NO_CMAKE)


def _install_real_df_sil(prefix: Path) -> Path:
    build_type = _configured_build_type()
    subprocess.run(
        ["cmake", "--install", str(_SIL_BUILD_DIR), "--config", build_type, "--prefix", str(prefix)],
        check=True, capture_output=True, text=True,
    )
    sim_dir = prefix / _BUNDLE_DESTDIR / "sim"
    assert (sim_dir / "plugin.yaml").is_file(), f"install() did not ship sim/plugin.yaml at {sim_dir}"
    return sim_dir


_CHECK_SCRIPT = """
import sys
sys.path.insert(0, {src!r})
from adas_sim.model.plugins import PluginBundle
from adas_sim.scene.registry import registered_providers

bundle = PluginBundle.resolve(library_dir={sim_dir!r})
assert bundle is not None
assert bundle.component == "df", bundle.component
assert bundle.origin == "library", bundle.origin
assert len(bundle.sha256) == 64, bundle.sha256

modules = bundle.import_modules()
assert len(modules) == len(bundle.provides)
assert "bsd.zone" in registered_providers(), sorted(registered_providers())
print("OK")
"""


def _run_check_in_a_fresh_process(sim_dir: Path) -> None:
    """A fresh interpreter, deliberately: `scene.registry`'s `_PROVIDERS` is
    process-global, and other tests in this same pytest session (e.g.
    `test_b1_df_layers.py`) legitimately import df's real `sim.layers.bsd`
    under the PLAIN module name for their own purposes. Running in-process
    here would make this test's pass/fail depend on pytest's collection
    order, which is exactly the "no reference to prior state" property a
    relocatability test exists to prove -- so it gets its own process
    instead, importing df's real files ONLY under the private name
    `PluginBundle.import_modules` uses, same as a real Vantage launch would."""
    script = _CHECK_SCRIPT.format(src=str(SIM_ROOT / "src"), sim_dir=str(sim_dir))
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0 and result.stdout.strip() == "OK", (
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def test_installed_sim_bundle_resolves_and_imports_real_df_layers(tmp_path):
    sim_dir = _install_real_df_sil(tmp_path / "installed")
    _run_check_in_a_fresh_process(sim_dir)


def test_relocated_and_original_deleted_sim_bundle_still_resolves_and_imports(tmp_path):
    """ST-C8-2, the strong form: copy the installed `sim/` bundle somewhere
    with no relation to the build tree, delete the original installed copy,
    and confirm the relocated copy alone is enough."""
    sim_dir = _install_real_df_sil(tmp_path / "installed")

    relocated_dir = tmp_path / "no_relation_to_the_build" / "deeply" / "nested" / "sim"
    shutil.copytree(sim_dir, relocated_dir)
    shutil.rmtree(tmp_path / "installed")  # prove nothing reaches back

    _run_check_in_a_fresh_process(relocated_dir)
