# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`ST-C8-3` (`sim_implementation_plan.md` S-C8's gate): "a plug-in bundle
loaded from a DEPLOYED root actually renders."
`test_c8_relocatability_installed.py` proves `ProjectModel.
resolve(library_dir=...)` itself works from a relocated bundle -- it does
not prove the *wiring* from `scripts/vantage.py`'s own CLI arguments,
through `MainWindow`'s `config_library_dir=`, into that same call. That
wiring is where the bug this test guards against actually lived: an
earlier version of `scripts/vantage.py` threaded a plug-in root's `config/`
directory only into `pipeline_config` (the pipeline's own `adasInit`),
never into `ProjectModel.resolve`'s `library_dir=` -- so `MainWindow._
resolve_project_model` fell back to a source-checkout path a deployed
copy does not have, and a component's own calibration reader crashed with
`FileNotFoundError` on the very first tick. A source checkout worked by
accident (the checkout-relative fallback path happens to exist there),
which is exactly why the bug was invisible until tested against a root
with no checkout reachable from it at all.

Reproduced against current source and found **already fixed**: `render/
viewer.py`'s `_resolve_project_model` does thread `self._config_library_dir`
into `ProjectModel.resolve(library_dir=...)`. This test is the missing
regression guard -- it drives the real wiring path (`scripts/vantage.py`'s
own `_register_plugin_root` into a real `MainWindow`), not a hand-assembled
call to `ProjectModel.resolve`, so a future edit that reintroduces the
`pipeline_config`-only wiring fails here rather than being found by hand a
third time.

Runs the check in a **fresh subprocess** (`scripts/vantage.py` mutates
`sys.path` at import time -- `test_d5_vantage_cli.py`'s own reasoning for
never importing it in-process -- and `scene.registry`'s provider registry is
process-global, the same isolation reason `test_c8_relocatability_
installed.py`'s own fresh-process check gives).

Skips with a named reason if no real `df_sil` build or recording exists here.
"""

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
_VANTAGE_PY = SIM_ROOT / "scripts" / "vantage.py"
_RECORDING = DF_ROOT / "tests" / "carla_testruns" / "bsd" / "bsd_ego_lane_exit.mcap"

_SKIP_REASON_NO_BUILD = (
    "no configured modules/df/build-sil-vs2026 (partial clone, or `sil` target not built here)"
)
_SKIP_REASON_NO_CMAKE = "cmake not found on PATH -- needed to exercise the real install() rule"
_SKIP_REASON_NO_RECORDING = f"{_RECORDING} is absent (partial clone, or no real CARLA run recorded here)"


def _configured_build_type() -> str | None:
    lib_name = "df_sil.dll" if sys.platform == "win32" else "libdf_sil.so"
    for build_type in ("Release", "Debug"):
        if (_SIL_BUILD_DIR / "src" / "platform" / "df_sil" / build_type / lib_name).is_file():
            return build_type
    return None


@pytest.fixture(autouse=True)
def _require_real_sil_build_and_recording():
    if not (_SIL_BUILD_DIR / "CMakeCache.txt").is_file() or _configured_build_type() is None:
        pytest.skip(_SKIP_REASON_NO_BUILD)
    if shutil.which("cmake") is None:
        pytest.skip(_SKIP_REASON_NO_CMAKE)
    if not _RECORDING.is_file():
        pytest.skip(_SKIP_REASON_NO_RECORDING)


def _install_real_df_sil(prefix: Path) -> Path:
    build_type = _configured_build_type()
    subprocess.run(
        ["cmake", "--install", str(_SIL_BUILD_DIR), "--config", build_type, "--prefix", str(prefix)],
        check=True, capture_output=True, text=True,
    )
    destdir = "bin" if sys.platform == "win32" else "lib"
    sim_dir = prefix / destdir / "sim"
    assert (sim_dir / "plugin.yaml").is_file(), f"install() did not ship sim/plugin.yaml at {sim_dir}"
    return sim_dir


# `library_dir` is the DEPLOYED root -- `sim/` and `config/` siblings, and
# deliberately no `src/project/` anywhere under it (the discriminator the
# original finding names: a checkout has one, a deployed copy does not).
_CHECK_SCRIPT = """
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
from pathlib import Path
sys.path.insert(0, {src!r})

import importlib.util
spec = importlib.util.spec_from_file_location("vantage_script", {vantage_py!r})
vantage_script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vantage_script)

from PySide6 import QtCore, QtWidgets
import adas_sim.io.mcap  # noqa: F401 -- registers the ".mcap" codec
from adas_sim.core.runner import build_scene
from adas_sim.player.shell.qt_window import MainWindow, set_high_dpi_policy

set_high_dpi_policy()
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

library_dir = Path({library_dir!r})
recording = Path({recording!r})

# The real wiring under test: scripts/vantage.py's own function, exactly as
# `main()` calls it for each --plugin-root argument.
config_library_dir = vantage_script._register_plugin_root(library_dir)
assert config_library_dir == library_dir / "config", config_library_dir

window = MainWindow(recording, project="base", config_library_dir=config_library_dir)

loop = QtCore.QEventLoop()
ceiling = QtCore.QTimer()
ceiling.setSingleShot(True)
ceiling.timeout.connect(loop.quit)
ceiling.start(10_000)
poll = QtCore.QTimer()
poll.timeout.connect(lambda: loop.quit() if window.session is not None else None)
poll.start(10)
loop.exec()
poll.stop()
ceiling.stop()
assert window.session is not None, "session did not load within the timeout"

model = window._project_model
assert model.bundle_origin == "library", model.bundle_origin
assert model.bundle_dir == config_library_dir, (model.bundle_dir, config_library_dir)

# The actual claim: a real BSD layer renders real prims, sourced from the
# DEPLOYED bundle's own config/ -- not a source-checkout fallback (there is
# none reachable from the deployed root at all).
scene = build_scene(window.session, 0, model=model)
layer_ids = {{layer.id for layer in scene.layers}}
assert "bsd.zone" in layer_ids, sorted(layer_ids)
zone_layer = next(layer for layer in scene.layers if layer.id == "bsd.zone")
assert len(zone_layer.prims) > 0, "bsd.zone rendered with no prims"

print("OK")
"""


def test_deployed_root_wiring_renders_a_real_bsd_layer_with_no_checkout_reachable(tmp_path):
    installed_sim_dir = _install_real_df_sil(tmp_path / "installed")
    installed_config_dir = installed_sim_dir.parent / "config"
    assert installed_config_dir.is_dir(), f"install() did not ship config/ beside sim/ at {installed_config_dir}"

    # Relocate away from the build tree entirely, same rigor `test_c8_
    # relocatability_installed.py`'s own strong form uses -- proves the
    # deployed copy is self-sufficient, not merely a second copy alongside
    # a reachable checkout.
    library_dir = tmp_path / "no_relation_to_the_build" / "deeply" / "nested"
    shutil.copytree(installed_sim_dir, library_dir / "sim")
    shutil.copytree(installed_config_dir, library_dir / "config")
    shutil.rmtree(tmp_path / "installed")  # prove nothing reaches back

    script = _CHECK_SCRIPT.format(
        src=str(SIM_ROOT / "src"), vantage_py=str(_VANTAGE_PY),
        library_dir=str(library_dir), recording=str(_RECORDING),
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0 and result.stdout.strip().endswith("OK"), (
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
