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

from adas_sim.player.shell.gui import launch  # noqa: E402
from adas_sim.cli import main as cli_main  # noqa: E402
from adas_sim.cli.view import build_parser  # noqa: E402
from adas_sim.io.base import ComponentBuildInfo, Provenance, RunManifest, TopicInfo  # noqa: E402
from adas_sim.plugins.registry import writer_for  # noqa: E402
import adas_sim.io.mcap  # noqa: E402,F401 -- registers the ".mcap" codec
import adas_sim.player.shell.qt_window as viewer_module  # noqa: E402
from adas_sim.player.shell.qt_window import MainWindow, set_high_dpi_policy  # noqa: E402
import yaml  # noqa: E402

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


def _scalar_message_cls():
    """A real `Scalar { x: float }` schema -- what an `expect:` block's
    `signal:` actually decodes, mirroring `test_c3_check.py`'s own helper
    of the same name (`R-SIM-1`: no function name anywhere)."""
    from google.protobuf import descriptor_pb2 as _dpb
    from google.protobuf import descriptor_pool as _dpool
    from google.protobuf import message_factory as _mfactory

    fdp = _dpb.FileDescriptorProto()
    fdp.name = "b3_cli_view_scalar.proto"
    fdp.package = "adas_sim.test.b3cliview"
    fdp.syntax = "proto3"
    msg = fdp.message_type.add()
    msg.name = "Scalar"
    f = msg.field.add()
    f.name, f.number, f.type = "x", 1, _dpb.FieldDescriptorProto.TYPE_FLOAT
    f.label = _dpb.FieldDescriptorProto.LABEL_OPTIONAL

    fds = _dpb.FileDescriptorSet()
    fds.file.append(fdp)

    pool = _dpool.DescriptorPool()
    pool.Add(fdp)
    cls = _mfactory.GetMessageClass(pool.FindMessageTypeByName("adas_sim.test.b3cliview.Scalar"))
    return cls, fds.SerializeToString()


def _write_scenario_backed_recording(tmp_path, values: list[float]) -> tuple:
    """A recording carrying a real, decodable `widget.outputs` topic --
    the schema-bearing counterpart to `_write_synthetic_recording`'s raw
    marker bytes, needed for a real `expect:` predicate to resolve
    against. Written directly (`_write_synthetic_recording`'s own
    pattern), not via `Recorder`: `Recorder.topics()`
    (`sources/recorder.py`) never sets `TopicInfo.schema_bytes` today --
    schema propagation for a live DLL comes from `adasManifest()`
    (`R-SIM-11`), a path a stub `InProcessSilComponent` has no equivalent
    of, so a `Recorder`-made recording built from one would hit the exact
    same undecodable-field gap this helper works around, not something
    introduced by this test. Returns `(recording_path, scalar_cls)`."""
    scalar_cls, descriptor_set = _scalar_message_cls()
    manifest = RunManifest(
        manifest_version=1, run_id="test-b3-expectation-windows", run_kind="sim",
        created_utc="2026-08-03T00:00:00Z", source_kind="synthetic",
        scenario="case", project=_PROJECT, pipeline="widget_only", seed=0,
        components=(ComponentBuildInfo(name="widget", library_sha256="0" * 64, build_id="test"),),
    )
    topics = {
        "/widget/outputs": TopicInfo(
            schema_name="adas_sim.test.b3cliview.Scalar", provenance=Provenance.SIMULATED,
            schema_bytes=descriptor_set,
        ),
    }
    recording_path = tmp_path / "scenario_backed.mcap"
    writer = writer_for(recording_path)
    writer.open(recording_path, manifest, topics, config_bundle_bytes=b"")
    for i, value in enumerate(values):
        writer.write("/widget/outputs", i * _DT_NS, scalar_cls(x=value).SerializeToString())
    writer.close()
    return recording_path, scalar_cls


def test_mainwindow_indexes_expectation_windows_from_a_real_scenario(tmp_path):
    """End to end: `--scenario` -> `_on_loaded` evaluates it against the
    real loaded `Session` -> `_expectation_windows` carries the result,
    keyed by signal (`test_b3_expectation_windows.py` covers the pure
    indexing logic directly; this proves `_on_loaded` actually calls it)."""
    recording, _scalar_cls = _write_scenario_backed_recording(tmp_path, [0.0, 0.0, 1.0, 1.0, 1.0])
    scenario_path = tmp_path / "case.yaml"
    scenario_path.write_text(yaml.safe_dump({
        "schema": 2, "id": "case", "doc": "",
        "scenario": {"ego": {"speed_mps": 10.0}, "actors": []},
        "world": {}, "sensor_model": {}, "run": {},
        "sut": {"pipeline": None, "project": "base"},
        "markers": [],
        "expect": [{
            "id": "EXP-1", "signal": "widget.outputs.x", "equals": 0.0, "during": [0.0, 0.05],
        }],
    }, sort_keys=False), encoding="utf-8")

    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MainWindow(recording, project=_PROJECT, scenario_path=scenario_path)
    _pump_until_loaded(window)

    assert set(window._expectation_windows) == {"widget.outputs.x"}
    result = window._expectation_windows["widget.outputs.x"][0]
    assert result.id == "EXP-1"
    assert result.window_s == (0.0, 0.05)
    assert result.passed is True  # x is 0.0 for the first two ticks (t=0.0, 0.05)


def test_build_parser_accepts_session_and_options():
    args = build_parser().parse_args(
        ["rec.mcap", "--project", "cus1", "--preset", "close", "--at", "0.2"],
    )
    assert str(args.session) == "rec.mcap"
    assert args.project == "cus1"
    assert args.preset == "close"
    assert args.at == pytest.approx(0.2)
    assert args.scenario is None


def test_build_parser_accepts_scenario():
    args = build_parser().parse_args(["rec.mcap", "--scenario", "case.yaml"])
    assert str(args.scenario) == "case.yaml"


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
    import adas_sim.player.shell.qt_window as viewer_mod
    real_init = viewer_mod.MainWindow.__init__

    def _spy_init(self, *args, **kwargs):
        captured.update(kwargs)
        return real_init(self, *args, **kwargs)

    monkeypatch.setattr(viewer_mod.MainWindow, "__init__", _spy_init)
    launch(recording, project=_PROJECT, preset="close", at_s=0.1)
    assert captured["preset"] == "close"
    assert captured["initial_at_s"] == pytest.approx(0.1)
    assert captured["scenario_path"] is None


def test_launch_passes_scenario_path_through_to_mainwindow(tmp_path, monkeypatch):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    scenario_path = tmp_path / "case.yaml"

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    monkeypatch.setattr(QtWidgets.QApplication, "exec", lambda self: 0)

    captured = {}
    import adas_sim.player.shell.qt_window as viewer_mod
    real_init = viewer_mod.MainWindow.__init__

    def _spy_init(self, *args, **kwargs):
        captured.update(kwargs)
        return real_init(self, *args, **kwargs)

    monkeypatch.setattr(viewer_mod.MainWindow, "__init__", _spy_init)
    # No scenario file on disk -- `load_scenario` would raise, and this
    # test is only proving the value reaches the constructor's kwarg, the
    # same split `test_mainwindow_*` (actually loading one) draws.
    monkeypatch.setattr(viewer_mod, "load_scenario", lambda path: None)
    launch(recording, project=_PROJECT, scenario_path=scenario_path)
    assert captured["scenario_path"] == scenario_path


def test_view_via_the_main_dispatcher_delegates_to_launch(tmp_path, monkeypatch):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)

    called = {}

    def _fake_launch(session, **kwargs):
        called["session"] = session
        called.update(kwargs)
        return 0

    monkeypatch.setattr("adas_sim.player.shell.gui.launch", _fake_launch)
    monkeypatch.setattr(sys, "argv", ["sim", "view", str(recording), "--project", "cus1"])
    assert cli_main() == 0
    assert called["session"] == recording
    assert called["project"] == "cus1"
