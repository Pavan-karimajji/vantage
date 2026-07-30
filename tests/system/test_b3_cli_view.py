# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 slice 13 `cli/view.py` / `app/gui.py` tests. `cli/view.py` parses
arguments and delegates (`GT-9`); `app/gui.py` is the actual orchestration
(construct `QApplication`, construct `MainWindow`, run the event loop) --
`app.exec()` is monkeypatched in every test here so a real GUI event loop
never blocks the test suite, matching how every other S-B3 system test
pumps a scoped `QEventLoop` instead of a real one.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys

import pytest

pytest.importorskip("PySide6")
from PySide6 import QtWidgets  # noqa: E402

from adas_sim.app.gui import launch  # noqa: E402
from adas_sim.cli import main as cli_main  # noqa: E402
from adas_sim.cli.view import build_parser  # noqa: E402
from adas_sim.io.base import ComponentBuildInfo, Provenance, RunManifest, TopicInfo  # noqa: E402
from adas_sim.io.registry import writer_for  # noqa: E402
import adas_sim.io.mcap  # noqa: E402,F401 -- registers the ".mcap" codec
import adas_sim.render.viewer as viewer_module  # noqa: E402
from adas_sim.render.viewer import MainWindow, set_high_dpi_policy  # noqa: E402

_PROJECT = "base"
_TICK_COUNT = 5
_DT_NS = 50_000_000


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    root = tmp_path / "config"
    monkeypatch.setattr(viewer_module, "_config_root", lambda: root)
    return root


def _write_synthetic_recording(out_path) -> None:
    manifest = RunManifest(
        manifest_version=1, run_id="test-b3-cli-view", run_kind="resim",
        created_utc="2026-07-30T00:00:00Z", source_kind="synthetic",
        scenario="fixtures/test_b3.yaml", project=_PROJECT, pipeline="p1", seed=0,
        components=(ComponentBuildInfo(name="test", library_sha256="0" * 64, build_id="test-b3m"),),
    )
    topics = {"/test/marker": TopicInfo(schema_name="", provenance=Provenance.UNKNOWN)}
    writer = writer_for(out_path)
    writer.open(out_path, manifest, topics, config_bundle_bytes=b"")
    for tick in range(_TICK_COUNT):
        writer.write("/test/marker", tick * _DT_NS, bytes([tick % 256]))
    writer.close()


def _pump_until_loaded(window: MainWindow, timeout_ms: int = 5000) -> None:
    from PySide6 import QtCore

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


def test_mainwindow_preset_param_sets_the_initial_viewport(tmp_path):
    """`sim view <session> --preset <name>` -- the mechanism `launch()`
    threads a `--preset` argument into (`test_launch_passes_preset_and_at_
    through_to_mainwindow` proves it reaches the constructor; this proves
    it actually takes effect)."""
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MainWindow(recording, project=_PROJECT, preset="close")
    _pump_until_loaded(window)
    assert window.bev.viewport.scale_px_per_m == pytest.approx(20.0)  # "close" preset


def test_mainwindow_initial_at_s_opens_at_the_right_tick(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MainWindow(recording, project=_PROJECT, initial_at_s=0.1)  # 2 ticks in at 50ms/tick
    _pump_until_loaded(window)
    assert window.transport.cursor == window.session.seek_ns(int(0.1 * 1e9))
    assert window._current_tick == window.transport.cursor


def test_build_parser_accepts_session_and_options():
    args = build_parser().parse_args(
        ["rec.mcap", "--project", "cus1", "--preset", "close", "--at", "0.2"],
    )
    assert str(args.session) == "rec.mcap"
    assert args.project == "cus1"
    assert args.preset == "close"
    assert args.at == pytest.approx(0.2)


def test_launch_constructs_a_mainwindow_with_every_option_and_shows_it(tmp_path, monkeypatch):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    exec_calls = []
    monkeypatch.setattr(QtWidgets.QApplication, "exec", lambda self: exec_calls.append(1) or 0)

    exit_code = launch(recording, project=_PROJECT, preset="close", at_s=None)
    assert exit_code == 0
    assert exec_calls == [1]


def test_launch_passes_preset_and_at_through_to_mainwindow(tmp_path, monkeypatch):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    monkeypatch.setattr(QtWidgets.QApplication, "exec", lambda self: 0)

    captured = {}
    from adas_sim.render import viewer as viewer_mod
    real_init = viewer_mod.MainWindow.__init__

    def _spy_init(self, *args, **kwargs):
        captured.update(kwargs)
        return real_init(self, *args, **kwargs)

    monkeypatch.setattr(viewer_mod.MainWindow, "__init__", _spy_init)
    launch(recording, project=_PROJECT, preset="close", at_s=0.1)
    assert captured["preset"] == "close"
    assert captured["initial_at_s"] == pytest.approx(0.1)


def test_view_via_the_main_dispatcher_delegates_to_launch(tmp_path, monkeypatch):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)

    called = {}

    def _fake_launch(session, **kwargs):
        called["session"] = session
        called.update(kwargs)
        return 0

    monkeypatch.setattr("adas_sim.app.gui.launch", _fake_launch)
    monkeypatch.setattr(sys, "argv", ["sim", "view", str(recording), "--project", "cus1"])
    assert cli_main() == 0
    assert called["session"] == recording
    assert called["project"] == "cus1"
