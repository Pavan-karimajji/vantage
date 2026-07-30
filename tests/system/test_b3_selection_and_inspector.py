# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 slice 5 system test: click-to-select / `Ctrl`+click / `Esc`, the
selection halo, and the docked inspector -- wired through a real
`MainWindow`, exercising the actual `BevPanel.clicked` signal connection
rather than calling a handler directly (`tests/unit/test_b3_inspector.py`
and `test_b3_selection_render.py` already cover `InspectorState` and the
halo pixels headlessly; this proves the pixel-click -> `hit_test` ->
selection -> render -> inspector path is actually wired end to end).
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

# World positions chosen so their box bounds (2m x 2m) do not overlap.
_OBJ_A_XY = (5.0, 0.0)
_OBJ_B_XY = (5.0, -6.0)


@layer_provider("test.b3e.objects", group="test")
def _objects_layer(ctx):
    del ctx
    return (Layer(id="test.b3e.objects", group="test", prims=(
        Prim(kind="box", cx_m=_OBJ_A_XY[0], cy_m=_OBJ_A_XY[1], length_m=2.0, width_m=2.0, yaw_rad=0.0,
             style="object.label", pick_id="a", fields=(("dist_x", "5.00 m"),)),
        Prim(kind="box", cx_m=_OBJ_B_XY[0], cy_m=_OBJ_B_XY[1], length_m=2.0, width_m=2.0, yaw_rad=0.0,
             style="object.label", pick_id="b", fields=(("dist_x", "5.00 m"), ("dist_y", "-6.00 m"))),
    )),)


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    root = tmp_path / "config"
    monkeypatch.setattr(viewer_module, "_config_root", lambda: root)
    return root


def _write_synthetic_recording(out_path) -> None:
    manifest = RunManifest(
        manifest_version=1, run_id="test-b3-selection", run_kind="resim",
        created_utc="2026-07-30T00:00:00Z", source_kind="synthetic",
        scenario="fixtures/test_b3.yaml", project=_PROJECT, pipeline="p1", seed=0,
        components=(ComponentBuildInfo(name="test", library_sha256="0" * 64, build_id="test-b3e"),),
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
    _pump_until_loaded(window)
    assert window.session is not None
    return window


def test_click_selects_ctrl_click_toggles_and_esc_clears(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    px_a = window.bev.viewport.to_px(*_OBJ_A_XY)
    px_b = window.bev.viewport.to_px(*_OBJ_B_XY)
    no_mod = QtCore.Qt.KeyboardModifier.NoModifier
    ctrl = QtCore.Qt.KeyboardModifier.ControlModifier

    window.bev.clicked.emit(*px_a, no_mod)
    assert window._selection == frozenset({"a"})

    window.bev.clicked.emit(*px_b, ctrl)
    assert window._selection == frozenset({"a", "b"})

    window.bev.clicked.emit(*px_a, ctrl)  # ctrl-click again -- toggles "a" back off
    assert window._selection == frozenset({"b"})

    window._on_clear_selection()  # Esc's own slot -- QShortcut delivery needs a real window
    assert window._selection == frozenset()

    # A click that hits nothing (no modifier) clears rather than leaving stale selection.
    window.bev.clicked.emit(*px_a, no_mod)
    assert window._selection == frozenset({"a"})
    window.bev.clicked.emit(-9999.0, -9999.0, no_mod)
    assert window._selection == frozenset()


def test_selecting_changes_the_rendered_frame_via_the_halo(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    unselected = window.bev.pixmap().toImage()
    window.bev.clicked.emit(*window.bev.viewport.to_px(*_OBJ_A_XY), QtCore.Qt.KeyboardModifier.NoModifier)
    selected = window.bev.pixmap().toImage()
    assert selected != unselected


def test_inspector_panel_shows_the_selected_entitys_declared_fields(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    window.bev.clicked.emit(*window.bev.viewport.to_px(*_OBJ_A_XY), QtCore.Qt.KeyboardModifier.NoModifier)

    tree = window.inspector_panel._tree
    assert tree.topLevelItemCount() == 1
    top = tree.topLevelItem(0)
    assert top.data(0, QtCore.Qt.ItemDataRole.UserRole) == "a"
    assert top.childCount() == 1
    assert top.child(0).text(0) == "dist_x: 5.00 m"


def test_pin_keeps_an_entity_after_deselection_inspector_drops_it_when_gone(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    window.bev.clicked.emit(*window.bev.viewport.to_px(*_OBJ_A_XY), QtCore.Qt.KeyboardModifier.NoModifier)
    window.inspector_state.toggle_pin("a")
    window._on_clear_selection()

    tree = window.inspector_panel._tree
    assert tree.topLevelItemCount() == 1
    assert tree.topLevelItem(0).data(0, QtCore.Qt.ItemDataRole.UserRole) == "a"

    # Now hide the layer that produces "a" -- gone from the *rendered* scene,
    # which is what the panel actually reflects (a real disappearance, not a
    # re-derivation-from-cache artifact).
    window.layers_state.set_group_visible("test", False)
    window.render_tick(window._current_tick)
    assert window.inspector_panel._tree.topLevelItemCount() == 0
