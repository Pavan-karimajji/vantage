# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 slice 7b system tests: `TransportBar` wired through a real
`MainWindow`. `view/transport.Transport`'s own state machine (head/review
mode, clamping, resume-eligibility) is already fully covered headlessly by
`tests/unit/test_b2_transport.py` (`S-B2`); this proves the Qt wiring on
top of it -- buttons, slider, keyboard shortcuts and the playback timer --
without re-testing `Transport` itself. The playback timer is driven by
calling `MainWindow._on_playback_tick()` directly rather than waiting on a
real `QTimer` firing, for determinism and speed.
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
_DT_NS = 50_000_000  # 50ms/tick, 20Hz


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    root = tmp_path / "config"
    monkeypatch.setattr(viewer_module, "_config_root", lambda: root)
    return root


def _write_synthetic_recording(out_path) -> None:
    manifest = RunManifest(
        manifest_version=1, run_id="test-b3-transport", run_kind="resim",
        created_utc="2026-07-30T00:00:00Z", source_kind="synthetic",
        scenario="fixtures/test_b3.yaml", project=_PROJECT, pipeline="p1", seed=0,
        components=(ComponentBuildInfo(name="test", library_sha256="0" * 64, build_id="test-b3g"),),
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


def test_loading_binds_transport_and_syncs_the_bar(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    assert window.transport is not None
    assert window.transport.head_tick == _TICK_COUNT - 1
    assert window.transport_bar._slider.maximum() == _TICK_COUNT - 1
    assert window.transport_bar._tick_label.text() == f"tick 0/{_TICK_COUNT - 1}"


def test_step_buttons_move_the_cursor_and_render(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    window.transport_bar.step(1)
    assert window.transport.cursor == 1
    assert window._current_tick == 1

    window.transport_bar.step(-1)
    assert window.transport.cursor == 0
    assert window._current_tick == 0


def test_step_back_at_zero_clamps_rather_than_going_negative(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    window.transport_bar.step(-5)
    assert window.transport.cursor == 0


def test_slider_drag_seeks_and_renders(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    window.transport_bar._slider.setValue(5)
    assert window.transport.cursor == 5
    assert window._current_tick == 5


def test_play_pause_toggle_starts_and_stops_the_timer(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    assert window._playback_timer.isActive() is False
    window.transport_bar.toggle_play_pause()
    assert window.transport.playing is True
    assert window._playback_timer.isActive() is True

    window.transport_bar.toggle_play_pause()
    assert window.transport.playing is False
    assert window._playback_timer.isActive() is False


def test_playback_tick_advances_the_cursor_by_one(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    window.transport.play()
    window._on_playback_tick()
    assert window.transport.cursor == 1
    assert window._current_tick == 1


def test_playback_auto_pauses_at_the_end(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    window.transport.goto(_TICK_COUNT - 1)
    window.transport.play()
    window._sync_playback_timer()  # cursor already at head_tick -- must auto-pause, not schedule a tick
    assert window.transport.playing is False
    assert window._playback_timer.isActive() is False


def test_loop_replays_the_marked_interval_instead_of_running_past_it(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    window.transport.goto(2)
    window.transport_bar._on_set_loop_start()
    window.transport.goto(4)
    window.transport_bar._on_set_loop_end()
    assert window.transport.loop_marks == (2, 4)

    window.transport_bar.toggle_loop()
    assert window.transport_bar.loop_active is True

    window.transport.goto(2)  # back to the in-mark
    window.transport.play()
    window._on_playback_tick()  # 2 -> 3
    assert window.transport.cursor == 3
    window._on_playback_tick()  # 3 -> 4 (the out-mark)
    assert window.transport.cursor == 4
    window._on_playback_tick()  # at the out-mark -- loops back to the in-mark, not 5
    assert window.transport.cursor == 2


def test_speed_change_updates_transport_speed(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    index = window.transport_bar._speed_box.findData(2.0)
    assert index >= 0
    window.transport_bar._speed_box.setCurrentIndex(index)
    assert window.transport.speed == 2.0


def test_keyboard_shortcuts_drive_the_same_transport(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    def _fire(key: str) -> None:
        for shortcut in window._shortcuts:
            if shortcut.key().toString() == key:
                shortcut.activated.emit()
                return
        raise AssertionError(f"no shortcut bound to {key!r}")

    _fire("Right")
    assert window.transport.cursor == 1
    _fire("Shift+Right")  # 1 + 10 overruns a 10-tick session -- clamps at the last index
    assert window.transport.cursor == _TICK_COUNT - 1
    _fire("Left")
    assert window.transport.cursor == _TICK_COUNT - 2
    _fire("Space")
    assert window.transport.playing is True
    _fire("Space")
    assert window.transport.playing is False
    _fire("L")
    assert window.transport_bar.loop_active is True
