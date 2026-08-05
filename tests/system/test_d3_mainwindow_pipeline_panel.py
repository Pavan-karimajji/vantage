# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

"""S-D3 slice 3 system test: the pipeline dock wired into `MainWindow`,
read-only this slice (`view/pipeline_panel.py`'s own scope note -- no
live re-run). Three things proven, all offscreen (`P-7`):

1. no `pipeline_path` given -- unchanged from before this slice, no dock
   content, no crash (the common case, backward compatible);
2. a `pipeline_path` whose `dll:` stage cannot resolve degrades the DOCK,
   never the window -- `MainWindow` still shows the recording;
3. a REAL, resolvable `stubdll:` stage populates the dock for real, and
   `File > Save Run Manifest...` writes a real, reloadable manifest.

(3) reuses `sil_host`'s own `echo_stub.dll` (built earlier this session
by `S-C7`'s real verification, at the known `ws/sil_host-base-gtest-
vs2026/tests/Release/` build path) rather than building a second trivial
fixture library -- skips with a named reason if it is not present here,
same pattern `test_c8_relocatability_installed.py` already uses for a
missing `df_sil` build.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

pytest.importorskip("PySide6")
from PySide6 import QtCore, QtWidgets  # noqa: E402

QtCore.QStandardPaths.setTestModeEnabled(True)  # P-7: never touch the real user profile in tests

from adas_sim.io.base import ComponentBuildInfo, Provenance, RunManifest, TopicInfo  # noqa: E402
from adas_sim.io.registry import writer_for  # noqa: E402
import adas_sim.io.mcap  # noqa: E402,F401 -- registers the ".mcap" codec
from adas_sim.render.viewer import MainWindow, set_high_dpi_policy  # noqa: E402
from adas_sim.scene.registry import layer_provider  # noqa: E402
from adas_sim.scene.types import Layer, Prim  # noqa: E402

_ECHO_STUB_DIR = Path(__file__).resolve().parents[4] / "ws" / "sil_host-base-gtest-vs2026" / "tests" / "Release"
_TICK_COUNT = 3
_DT_NS = 50_000_000


@layer_provider("test.d3.ego", group="test")
def _fixed_ego_layer(ctx):
    del ctx
    return (Layer(id="test.d3.ego", group="test", prims=(
        Prim(kind="box", cx_m=0.0, cy_m=0.0, length_m=4.5, width_m=1.8, style="ego.body"),
    )),)


def _write_synthetic_recording(out_path: Path) -> None:
    manifest = RunManifest(
        manifest_version=1, run_id="test-d3-mainwindow", run_kind="resim",
        created_utc="2026-08-05T00:00:00Z", source_kind="synthetic",
        scenario="fixtures/test_d3.yaml", project="base", pipeline="none", seed=0,
        components=(ComponentBuildInfo(name="test", library_sha256="0" * 64, build_id="test-d3"),),
    )
    topics = {"/test/marker": TopicInfo(schema_name="", provenance=Provenance.UNKNOWN)}
    writer = writer_for(out_path)
    writer.open(out_path, manifest, topics, config_bundle_bytes=b"")
    for tick in range(_TICK_COUNT):
        writer.write("/test/marker", tick * _DT_NS, bytes([tick % 256]))
    writer.close()


def _pump_until_loaded(window: MainWindow, timeout_ms: int = 5000) -> None:
    loop = QtCore.QEventLoop()
    ceiling = QtCore.QTimer()
    ceiling.setSingleShot(True)
    ceiling.timeout.connect(loop.quit)
    ceiling.start(timeout_ms)
    poll = QtCore.QTimer()
    poll.timeout.connect(lambda: loop.quit() if window.session is not None else None)
    poll.start(10)
    loop.exec()
    poll.stop()
    ceiling.stop()


def test_no_pipeline_path_leaves_the_dock_empty_and_does_not_crash(tmp_path):
    recording = tmp_path / "test_d3.mcap"
    _write_synthetic_recording(recording)

    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MainWindow(recording)
    _pump_until_loaded(window)

    assert window.session is not None
    assert window.pipeline_panel_state is None
    assert not window._save_run_manifest_action.isEnabled()


def test_an_unresolvable_dll_stage_degrades_the_dock_not_the_window(tmp_path):
    recording = tmp_path / "test_d3.mcap"
    _write_synthetic_recording(recording)
    pipeline_path = tmp_path / "broken_pipeline.yaml"
    pipeline_path.write_text(yaml.safe_dump({
        "name": "broken", "stages": [{"name": "a", "mode": "simulate", "impl": "dll:does_not_exist_anywhere"}],
    }, sort_keys=False), encoding="utf-8")

    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MainWindow(recording, pipeline_path=pipeline_path)
    _pump_until_loaded(window)

    assert window.session is not None, "an unresolvable pipeline must not take the whole window down"
    assert window.pipeline_panel_state is None
    assert not window._save_run_manifest_action.isEnabled()


@pytest.mark.skipif(
    not (_ECHO_STUB_DIR / "echo_stub.dll").is_file(),
    reason=f"needs sil_host's echo_stub.dll built at {_ECHO_STUB_DIR} (scripts/build.py sil_host -t gtest -p vs2026 -P base)",
)
def test_a_real_resolvable_pipeline_populates_the_dock_and_save_run_manifest_writes_a_real_file(tmp_path):
    recording = tmp_path / "test_d3.mcap"
    _write_synthetic_recording(recording)
    pipeline_path = tmp_path / "real_pipeline.yaml"
    pipeline_path.write_text(yaml.safe_dump({
        "name": "real", "stages": [{"name": "echo", "mode": "simulate", "impl": "stubdll:echo_stub"}],
    }, sort_keys=False), encoding="utf-8")

    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MainWindow(recording, pipeline_path=pipeline_path, pipeline_search=[_ECHO_STUB_DIR])
    _pump_until_loaded(window)

    assert window.session is not None
    assert window.pipeline_panel_state is not None
    assert [v.name for v in window.pipeline_panel_state.stages()] == ["echo"]
    assert window._save_run_manifest_action.isEnabled()
    assert window.pipeline_panel._table.rowCount() == 1

    out_path = tmp_path / "saved_manifest.yaml"
    with patch.object(QtWidgets.QFileDialog, "getSaveFileName", return_value=(str(out_path), "")):
        window._on_save_run_manifest()

    assert out_path.is_file()
    written = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert written["stages"][0]["name"] == "echo"
    assert written["recording"]  # some relative path was written
    assert not Path(written["recording"]).is_absolute()
