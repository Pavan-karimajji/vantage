# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 slice 8 system tests: `TimelineStrip` wired through a real
`MainWindow` -- adding a lane, click-to-seek, playhead rendering, bookmarks
and jump-to-event. `view/timeline.py` (state/event-marker logic) and
`render/timeline.py` (the raster + `px_to_tick`) are already covered
headlessly (`tests/unit/test_b3_timeline.py`, `test_b3_timeline_render.py`);
this proves the Qt wiring on top of them.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
from PySide6 import QtCore, QtWidgets  # noqa: E402

from adas_sim.io.base import ComponentBuildInfo, Provenance, RunManifest, TopicInfo  # noqa: E402
from adas_sim.plugins.registry import writer_for  # noqa: E402
import adas_sim.io.mcap  # noqa: E402,F401 -- registers the ".mcap" codec
import adas_sim.player.shell.qt_window as viewer_module  # noqa: E402
from adas_sim.player.shell.qt_window import MainWindow, set_high_dpi_policy  # noqa: E402

_PROJECT = "base"
_TICK_COUNT = 10
_DT_NS = 50_000_000

#: b"A" ticks 0-2, b"B" ticks 3-5, b"C" ticks 6-9 -- two transitions, at
#: tick 3 and tick 6, for jump-to-event / event-marker assertions.
_STATE_BY_TICK = [b"A"] * 3 + [b"B"] * 3 + [b"C"] * 4


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    root = tmp_path / "config"
    monkeypatch.setattr(viewer_module, "_config_root", lambda: root)
    return root


def _write_synthetic_recording(out_path) -> None:
    manifest = RunManifest(
        manifest_version=1, run_id="test-b3-timeline", run_kind="resim",
        created_utc="2026-07-30T00:00:00Z", source_kind="synthetic",
        scenario="fixtures/test_b3.yaml", project=_PROJECT, pipeline="p1", seed=0,
        components=(ComponentBuildInfo(name="test", library_sha256="0" * 64, build_id="test-b3h"),),
    )
    topics = {"/test/state": TopicInfo(schema_name="", provenance=Provenance.UNKNOWN)}
    writer = writer_for(out_path)
    writer.open(out_path, manifest, topics, config_bundle_bytes=b"")
    for tick in range(_TICK_COUNT):
        writer.write("/test/state", tick * _DT_NS, _STATE_BY_TICK[tick])
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


def test_loading_pins_the_strips_head_tick(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)
    assert window.timeline_strip._head_tick == _TICK_COUNT - 1


def test_add_signal_lane_via_the_menu_dialog_resolves_and_caches(tmp_path, monkeypatch):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    monkeypatch.setattr(QtWidgets.QInputDialog, "getText", staticmethod(lambda *a, **k: ("test.state", True)))
    window._on_add_timeline_lane(is_state=False)

    assert window.timeline_state.signal_lanes() == ("test.state",)
    assert window._signal_series_cache["test.state"] == tuple(
        (i, _STATE_BY_TICK[i]) for i in range(_TICK_COUNT)
    )


def test_cancelling_the_dialog_adds_nothing(tmp_path, monkeypatch):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    monkeypatch.setattr(QtWidgets.QInputDialog, "getText", staticmethod(lambda *a, **k: ("", False)))
    window._on_add_timeline_lane(is_state=True)
    assert window.timeline_state.state_lanes() == ()


def test_click_to_seek_moves_the_transport_and_renders(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    # Midpoint of the strip's fixed-width canvas -> roughly the midpoint tick.
    mid_x = window.timeline_strip.size_px[0] / 2.0
    window.timeline_strip._label.clicked.emit(mid_x, 0.0, QtCore.Qt.KeyboardModifier.NoModifier)

    assert window.transport.cursor == round((_TICK_COUNT - 1) / 2)
    assert window._current_tick == window.transport.cursor


def test_playhead_changes_the_rendered_strip(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    before = window.timeline_strip.pixmap().toImage()
    window.transport_bar.step(3)
    after = window.timeline_strip.pixmap().toImage()
    assert before != after


def test_add_bookmark_at_cursor(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    window.transport.goto(4)
    window._on_add_bookmark()
    assert [b.tick_index for b in window.timeline_state.bookmarks()] == [4]


def test_jump_to_event_seeks_to_the_next_and_previous_transition(tmp_path, monkeypatch):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    monkeypatch.setattr(QtWidgets.QInputDialog, "getText", staticmethod(lambda *a, **k: ("test.state", True)))
    window._on_add_timeline_lane(is_state=True)  # transitions at tick 3 and tick 6

    window.transport.goto(0)
    window._on_jump_to_event(1)
    assert window.transport.cursor == 3
    window._on_jump_to_event(1)
    assert window.transport.cursor == 6
    window._on_jump_to_event(1)
    assert window.transport.cursor == 6  # no further transition -- stays put

    window._on_jump_to_event(-1)
    assert window.transport.cursor == 3


def test_bracket_key_shortcuts_drive_jump_to_event(tmp_path, monkeypatch):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    monkeypatch.setattr(QtWidgets.QInputDialog, "getText", staticmethod(lambda *a, **k: ("test.state", True)))
    window._on_add_timeline_lane(is_state=True)
    window.transport.goto(0)

    def _fire(key: str) -> None:
        for shortcut in window._shortcuts:
            if shortcut.key().toString() == key:
                shortcut.activated.emit()
                return
        raise AssertionError(f"no shortcut bound to {key!r}")

    _fire("]")
    assert window.transport.cursor == 3
    _fire("]")
    assert window.transport.cursor == 6
    _fire("[")
    assert window.transport.cursor == 3
