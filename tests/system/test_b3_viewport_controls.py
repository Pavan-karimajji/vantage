# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 slice 7a system tests: pan/zoom/fit/presets/follow (`sim_visualization_spec.md`
§4.4), wired through a real `MainWindow` and `_ClickableImageLabel`. Viewport
geometry itself (`panned`/`fitted_to`/`zoomed_about_cursor`) is
`tests/unit/test_b1_viewport.py`'s job; this proves the Qt event -> signal ->
`Viewport` update path, including the drag-vs-click distinction that only
exists inside `_ClickableImageLabel`'s own event handlers.
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
from adas_sim.render.viewer import MainWindow, _ClickableImageLabel, set_high_dpi_policy  # noqa: E402
from adas_sim.scene.registry import layer_provider  # noqa: E402
from adas_sim.scene.types import Layer, Prim  # noqa: E402
from adas_sim.view.viewport import Viewport  # noqa: E402

_PROJECT = "base"
_TICK_COUNT = 3
_DT_NS = 50_000_000


#: A distinctive group, not the "test" group every other S-B3 system-test
#: file's provider uses -- those have no `requires=` gating either, so in a
#: full-suite run every one of them contributes prims to every other test's
#: Scene (`build_scene`'s own "every registered provider" docstring). Most
#: assertions here don't care; `test_f_fits_to_the_visible_content` computes
#: a scene-wide bounds union and does, so it solos this group first.
_GROUP = "test-b3f"


@layer_provider("test.b3f.box", group=_GROUP)
def _box_layer(ctx):
    del ctx
    return (Layer(id="test.b3f.box", group=_GROUP, prims=(
        Prim(kind="box", cx_m=20.0, cy_m=0.0, length_m=2.0, width_m=2.0, yaw_rad=0.0,
             style="object.label", pick_id="box"),
    )),)


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    root = tmp_path / "config"
    monkeypatch.setattr(viewer_module, "_config_root", lambda: root)
    return root


def _write_synthetic_recording(out_path) -> None:
    manifest = RunManifest(
        manifest_version=1, run_id="test-b3-viewport", run_kind="resim",
        created_utc="2026-07-30T00:00:00Z", source_kind="synthetic",
        scenario="fixtures/test_b3.yaml", project=_PROJECT, pipeline="p1", seed=0,
        components=(ComponentBuildInfo(name="test", library_sha256="0" * 64, build_id="test-b3f"),),
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


def _press(label: _ClickableImageLabel, x: float, y: float) -> None:
    pos = QtCore.QPointF(x, y)
    label.mousePressEvent(QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseButtonPress, pos, pos, pos,
        QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier,
    ))


def _move(label: _ClickableImageLabel, x: float, y: float) -> None:
    pos = QtCore.QPointF(x, y)
    label.mouseMoveEvent(QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseMove, pos, pos, pos,
        QtCore.Qt.MouseButton.NoButton, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier,
    ))


def _release(label: _ClickableImageLabel, x: float, y: float) -> None:
    pos = QtCore.QPointF(x, y)
    label.mouseReleaseEvent(QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseButtonRelease, pos, pos, pos,
        QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.MouseButton.NoButton, QtCore.Qt.KeyboardModifier.NoModifier,
    ))


def test_a_small_movement_is_a_click_not_a_drag(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    clicks, drags = [], []
    window.bev.clicked.connect(lambda x, y, mods: clicks.append((x, y)))
    window.bev.dragged.connect(lambda fx, fy, tx, ty: drags.append((fx, fy, tx, ty)))

    label = window.bev._label
    _press(label, 100.0, 100.0)
    _move(label, 101.0, 100.0)  # inside the drag threshold
    _release(label, 101.0, 100.0)

    assert len(clicks) == 1
    assert drags == []


def test_a_real_movement_is_a_drag_not_a_click(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    clicks, drags = [], []
    window.bev.clicked.connect(lambda x, y, mods: clicks.append((x, y)))
    window.bev.dragged.connect(lambda fx, fy, tx, ty: drags.append((fx, fy, tx, ty)))

    label = window.bev._label
    _press(label, 100.0, 100.0)
    _move(label, 140.0, 100.0)
    _release(label, 140.0, 100.0)

    assert clicks == []
    assert len(drags) == 1


def test_dragging_pans_the_viewport_and_a_second_click_still_selects(tmp_path):
    """The drag itself changes `Viewport.centre_m`; a plain click afterward
    still resolves to a real selection -- the two paths don't corrupt each
    other's state."""
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    before = window.bev.viewport
    label = window.bev._label
    _press(label, 100.0, 100.0)
    _move(label, 140.0, 130.0)
    _release(label, 140.0, 130.0)

    assert window.bev.viewport.centre_m != before.centre_m
    assert window.bev.viewport.scale_px_per_m == before.scale_px_per_m  # pan never touches scale

    px_box = window.bev.viewport.to_px(20.0, 0.0)
    _press(label, *px_box)
    _release(label, *px_box)
    assert window._selection == frozenset({"box"})


def test_wheel_zooms_about_the_cursor(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    before_scale = window.bev.viewport.scale_px_per_m
    label = window.bev._label
    pos = QtCore.QPointF(300.0, 200.0)
    wheel_event = QtGui.QWheelEvent(
        pos, pos, QtCore.QPoint(0, 0), QtCore.QPoint(0, 120), QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.KeyboardModifier.NoModifier, QtCore.Qt.ScrollPhase.NoScrollPhase, False,
    )
    label.wheelEvent(wheel_event)
    assert window.bev.viewport.scale_px_per_m > before_scale


def test_f_fits_to_the_visible_content(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    # Solo this test's own group -- a full-suite run has every other S-B3
    # system test's provider registered too (see _GROUP's own comment), and
    # a bounds union is exactly the kind of assertion that would otherwise
    # see their prims as well.
    window.layers_state.toggle_solo(_GROUP)

    window._on_fit_to_content()
    # The box sits at (20, 0); a fit must centre on (roughly) its bounds.
    assert window.bev.viewport.centre_m == pytest.approx((20.0, 0.0), abs=0.5)


def test_zero_resets_the_viewport_keeping_widget_size(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    size = window.bev.viewport.size_px
    window.bev.viewport = window.bev.viewport.zoomed_about_cursor(3.0, (0.0, 0.0))
    assert window.bev.viewport.centre_m != (0.0, 0.0) or window.bev.viewport.scale_px_per_m != 10.0

    window._on_reset_viewport()
    assert window.bev.viewport == Viewport(size_px=size)


def test_r_cycles_through_the_three_follow_modes(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    assert window.bev.viewport.follow == "ego_forward"
    window._on_cycle_follow_mode()
    assert window.bev.viewport.follow == "ego_heading"
    window._on_cycle_follow_mode()
    assert window.bev.viewport.follow == "world"
    window._on_cycle_follow_mode()
    assert window.bev.viewport.follow == "ego_forward"


def test_number_key_jumps_to_the_nth_default_preset(tmp_path):
    """`DEFAULT_PRESETS` today: "close", "wide" -- sorted, so `1` is
    "close" and `2` is "wide"."""
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    window._on_jump_to_preset("close")
    assert window.bev.viewport.scale_px_per_m == pytest.approx(20.0)
    window._on_jump_to_preset("wide")
    assert window.bev.viewport.scale_px_per_m == pytest.approx(6.0)
