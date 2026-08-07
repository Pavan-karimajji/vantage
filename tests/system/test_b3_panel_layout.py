# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 slice 3 system tests: `UT-B3-10` (panel grid: open/close/split/tab/
float; a saved layout restores) and the persistence wiring closed out from
Slice 2 -- `LayerTreeState.save()/load()` now runs against a real
`QStandardPaths.AppConfigLocation` path, per (project, pipeline)
(`sim_visualization_spec.md` §6), and the dock grid's own arrangement
persists per project (§11.1).

`project` here is always `"base"` (the real fallback project, `R-VAR-4`) --
`build_scene()` resolves `EgoModel` against `modules/shared_config/projects/
<project>/`, which a made-up name would fail. Isolation between tests instead
comes from monkeypatching `render.viewer._config_root` to a per-test
`tmp_path`, so no test's persisted layout/layer-state file can be seen by
another.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
from PySide6 import QtCore, QtWidgets  # noqa: E402

from adas_sim.io.base import ComponentBuildInfo, Provenance, RunManifest, TopicInfo  # noqa: E402
from adas_sim.io.registry import writer_for  # noqa: E402
import adas_sim.io.mcap  # noqa: E402,F401 -- registers the ".mcap" codec
import adas_sim.render.viewer as viewer_module  # noqa: E402
from adas_sim.render.viewer import MainWindow, set_high_dpi_policy  # noqa: E402
from adas_sim.scene.registry import layer_provider  # noqa: E402
from adas_sim.scene.types import Layer, Prim  # noqa: E402

_PROJECT = "base"
_TICK_COUNT = 3
_DT_NS = 50_000_000


@layer_provider("test.b3c.ego", group="test")
def _fixed_ego_layer(ctx):
    del ctx
    return (Layer(id="test.b3c.ego", group="test", prims=(
        Prim(kind="box", cx_m=0.0, cy_m=0.0, length_m=4.5, width_m=1.8, style="ego.body"),
    )),)


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    """Every persisted path this slice writes routes through
    `_config_root()` -- redirecting it is enough to isolate every test in
    this file from both the real user profile and each other."""
    root = tmp_path / "config"
    monkeypatch.setattr(viewer_module, "_config_root", lambda: root)
    return root


def _write_synthetic_recording(out_path, *, pipeline: str) -> None:
    manifest = RunManifest(
        manifest_version=1, run_id="test-b3-panel-layout", run_kind="resim",
        created_utc="2026-07-30T00:00:00Z", source_kind="synthetic",
        scenario="fixtures/test_b3.yaml", project=_PROJECT, pipeline=pipeline, seed=0,
        components=(ComponentBuildInfo(name="test", library_sha256="0" * 64, build_id="test-b3c"),),
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


def _open_window(recording) -> MainWindow:
    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MainWindow(recording, project=_PROJECT)
    window.show()  # a dock's `isVisible()` reflects the whole ancestor chain
    _pump_until_loaded(window)
    assert window.session is not None
    return window


def test_default_layout_matches_sim_player_section_3(tmp_path):
    """`AR-59`: a fresh window, on a profile with no saved
    layout, used to put every one of `bev`/`inspector_panel`/
    `evidence_panel` in `RightDockWidgetArea` together -- `QMainWindow`
    tabifies same-area docks by default, so only the last one added
    (`evidence_panel`) ended up on top and `bev.isVisible()` measured
    `False` on first open. `sim_player.md` §3: Pipeline dock left, CENTRE
    = the BEV, Layers dock right, "everything else... closed by default"
    (inspector/evidence). `BevPanel` stays a real `QDockWidget` (unchanged:
    `test_tab_and_float_are_native_dock_mechanics` below depends on it) --
    what this proves is that it no longer collides with anything and
    dominates the window by default, the same visual outcome a central
    widget would give without giving up dock flexibility."""
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording, pipeline="p1")
    window = _open_window(recording)
    window.resize(1500, 950)

    assert window.bev.isVisible() is True
    assert window.dockWidgetArea(window.pipeline_panel) == QtCore.Qt.DockWidgetArea.LeftDockWidgetArea
    assert window.dockWidgetArea(window.layers_panel) == QtCore.Qt.DockWidgetArea.RightDockWidgetArea
    # BEV dominates the window rather than being squeezed into a third of
    # it alongside two other docks (the measured defect: bev previously
    # wasn't even the visible tab, so its width didn't matter).
    assert window.bev.geometry().width() > window.width() * 0.5

    assert window.inspector_panel.isVisible() is False
    assert window.evidence_panel.isVisible() is False


def test_toggle_view_action_reopens_a_closed_dock(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording, pipeline="p1")
    window = _open_window(recording)

    assert window.bev.isVisible() is True
    window.bev.close()
    assert window.bev.isVisible() is False

    window.bev.toggleViewAction().trigger()
    assert window.bev.isVisible() is True


def test_tab_and_float_are_native_dock_mechanics(tmp_path):
    """Split/tab/float need no wrapper of our own -- `QMainWindow`/
    `QDockWidget` already provide them; this only proves our two docks
    (stable `objectName()`s) participate normally."""
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording, pipeline="p1")
    window = _open_window(recording)

    window.tabifyDockWidget(window.bev, window.layers_panel)
    assert window.layers_panel in window.tabifiedDockWidgets(window.bev)

    window.layers_panel.setFloating(True)
    assert window.layers_panel.isFloating() is True


def test_saved_layout_restores_dock_arrangement(tmp_path):
    """`UT-B3-10`'s persistence half: closing a dock and floating another,
    then saving, must survive into a fresh `MainWindow` for the same
    project."""
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording, pipeline="p1")
    window = _open_window(recording)

    window.bev.close()
    window.layers_panel.setFloating(True)
    window.save_layout()
    assert viewer_module.layout_path(_PROJECT).is_file()

    window2 = _open_window(recording)
    assert window2.bev.isVisible() is False
    assert window2.layers_panel.isFloating() is True


def test_layer_state_persists_per_project_and_pipeline(tmp_path):
    """The Slice 2 debt this slice closes: a real, discoverable
    `QStandardPaths.AppConfigLocation` path, written when the panel
    dispatches a change and read back on the next load of the same
    (project, pipeline)."""
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording, pipeline="pipeline-a")
    window = _open_window(recording)
    assert window.layers_state.is_visible("test.b3c.ego") is True

    window.layers_state.set_visible("test.b3c.ego", False)
    window.layers_panel.changed.emit()  # what a real checkbox click dispatches
    assert viewer_module.layers_state_path(_PROJECT, "pipeline-a").is_file()

    window2 = _open_window(recording)
    assert window2.layers_state.is_visible("test.b3c.ego") is False


def test_layer_state_does_not_leak_across_pipelines(tmp_path):
    """§6: overrides persist per project **+ pipeline** -- a different
    pipeline under the same project must not inherit them."""
    rec_a = tmp_path / "a.mcap"
    rec_b = tmp_path / "b.mcap"
    _write_synthetic_recording(rec_a, pipeline="pipeline-a")
    _write_synthetic_recording(rec_b, pipeline="pipeline-b")

    window_a = _open_window(rec_a)
    window_a.layers_state.set_visible("test.b3c.ego", False)
    window_a.layers_panel.changed.emit()

    window_b = _open_window(rec_b)
    assert window_b.layers_state.is_visible("test.b3c.ego") is True
