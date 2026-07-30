# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 slice 11 system tests: `UT-B3-4`'s Qt half (docs/
sim_implementation_plan.md) -- `view/measure.py`'s own geometry (distance/
dx/dy/bearing, snap) is already covered headlessly
(`tests/unit/test_b3_measure.py`). Proves ruler-mode dragging on the BEV
produces a real ruler (snapped to a real anchor), that ruler mode and pan
are mutually exclusive on the same drag gesture, that range rings and
`Shift`+click annotations reach `MeasureState`, and that hover updates the
cursor-readout label without triggering a re-render.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402

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
_GROUP = "test-b3k"


@layer_provider("test.b3k.box", group=_GROUP)
def _box_layer(ctx):
    del ctx
    return (Layer(id="test.b3k.box", group=_GROUP, prims=(
        Prim(kind="box", cx_m=10.0, cy_m=0.0, length_m=2.0, width_m=2.0, yaw_rad=0.0,
             style="object.label", pick_id="box"),
    )),)


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    root = tmp_path / "config"
    monkeypatch.setattr(viewer_module, "_config_root", lambda: root)
    return root


def _write_synthetic_recording(out_path) -> None:
    manifest = RunManifest(
        manifest_version=1, run_id="test-b3-measure", run_kind="resim",
        created_utc="2026-07-30T00:00:00Z", source_kind="synthetic",
        scenario="fixtures/test_b3.yaml", project=_PROJECT, pipeline="p1", seed=0,
        components=(ComponentBuildInfo(name="test", library_sha256="0" * 64, build_id="test-b3k"),),
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
    window.show()
    _pump_until_loaded(window)
    assert window.session is not None
    return window


def test_ruler_mode_off_by_default_drag_still_pans(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    before = window.bev.viewport
    window.bev.dragged.emit(100.0, 100.0, 140.0, 100.0)
    assert window.bev.viewport.centre_m != before.centre_m
    assert window.measure_state.ruler() is None


def test_ruler_mode_on_drag_measures_instead_of_panning(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    window._measure_mode_action.setChecked(True)
    assert window._measure_mode is True

    before = window.bev.viewport
    window.bev.dragged.emit(100.0, 100.0, 140.0, 100.0)
    assert window.bev.viewport.centre_m == before.centre_m  # no pan while measuring

    start_px = window.bev.viewport.to_px(0.0, 0.0)
    end_px = window.bev.viewport.to_px(5.0, 0.0)
    window.bev.drag_extent_changed.emit(*start_px, *end_px)

    ruler = window.measure_state.ruler()
    assert ruler is not None
    assert ruler.distance_m == pytest.approx(5.0, abs=0.05)


def test_ruler_snaps_to_a_real_anchor(tmp_path):
    """UT-B3-4: snap picks the nearest anchor within the threshold --
    dragging to *near* the box (at world (10, 0)) should snap exactly onto
    one of its corners/centre, not land on the raw cursor position."""
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)
    window._measure_mode_action.setChecked(True)

    start_px = window.bev.viewport.to_px(0.0, 0.0)
    near_box_px = window.bev.viewport.to_px(10.02, 0.02)  # a couple cm off the box centre
    window.bev.drag_extent_changed.emit(*start_px, *near_box_px)

    ruler = window.measure_state.ruler()
    assert ruler.end_m == pytest.approx((10.0, 0.0))  # snapped exactly to the box's own centre


def test_turning_ruler_mode_off_clears_the_ruler(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)
    window._measure_mode_action.setChecked(True)
    window.bev.drag_extent_changed.emit(0.0, 0.0, 10.0, 10.0)
    assert window.measure_state.ruler() is not None

    window._measure_mode_action.setChecked(False)
    assert window.measure_state.ruler() is None


def test_range_rings_toggle_and_radii_reach_measure_state(tmp_path, monkeypatch):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    monkeypatch.setattr(QtWidgets.QInputDialog, "getText", staticmethod(lambda *a, **k: ("10, 20, 30", True)))
    window._on_set_range_ring_radii()
    assert window.measure_state.overlay_prims() == ()  # set, not shown yet

    window._range_rings_action.setChecked(True)
    assert window.measure_state.range_rings_visible is True
    prims = window.measure_state.overlay_prims()
    assert [p.r_m for p in prims] == [10.0, 20.0, 30.0]


def test_shift_click_adds_a_snapped_annotation(tmp_path, monkeypatch):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    monkeypatch.setattr(QtWidgets.QInputDialog, "getText", staticmethod(lambda *a, **k: ("note here", True)))
    near_box_px = window.bev.viewport.to_px(10.03, -0.02)
    window.bev._label.clicked.emit(*near_box_px, QtCore.Qt.KeyboardModifier.ShiftModifier)

    annotations = window.measure_state.annotations()
    assert len(annotations) == 1
    assert annotations[0].label == "note here"
    assert annotations[0].point_m == pytest.approx((10.0, 0.0))  # snapped


def test_shift_click_does_not_also_select(tmp_path, monkeypatch):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    monkeypatch.setattr(QtWidgets.QInputDialog, "getText", staticmethod(lambda *a, **k: ("", True)))
    box_px = window.bev.viewport.to_px(10.0, 0.0)
    window.bev._label.clicked.emit(*box_px, QtCore.Qt.KeyboardModifier.ShiftModifier)
    assert window._selection == frozenset()


def test_hover_updates_the_cursor_readout_label_with_no_rerender(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    before_pixmap = window.bev.pixmap().toImage()
    world = window.bev.viewport.to_m(50.0, 60.0)
    window.bev.hovered.emit(50.0, 60.0)

    assert f"{world[0]:.2f}" in window._cursor_readout_label.text()
    assert f"{world[1]:.2f}" in window._cursor_readout_label.text()
    assert window.bev.pixmap().toImage() == before_pixmap  # no re-render triggered
