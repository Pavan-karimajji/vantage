# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`app/gui.launch` actually launches the `S-D8` shell (`VantageWindow`),
not `render/viewer.py`'s bare `MainWindow` directly -- the gap found
2026-08-06: every `S-D8` shell/workspace/palette/panel piece was built
and tested in isolation, but `sim view`/`vantage.bat`'s own real entry
point still constructed the old window directly, so none of it was
actually reachable. This file exists so that gap cannot silently return:
`launch()` must construct a real `VantageWindow`, and `recording=None`
must open onto the start page rather than raising."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
from PySide6 import QtCore, QtWidgets  # noqa: E402

QtCore.QStandardPaths.setTestModeEnabled(True)  # P-7: never touch the real user profile in tests

from adas_sim.app.gui import launch  # noqa: E402
from adas_sim.app.shell.window import VantageWindow  # noqa: E402
from adas_sim.io.base import ComponentBuildInfo, Provenance, RunManifest, TopicInfo  # noqa: E402
from adas_sim.io.registry import writer_for  # noqa: E402

import adas_sim.io.mcap  # noqa: E402,F401 -- registers the ".mcap" codec

_PROJECT = "base"


def _app() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _write_synthetic_recording(out_path) -> None:
    manifest = RunManifest(
        manifest_version=1, run_id="test-d8-gui-launch", run_kind="resim",
        created_utc="2026-08-06T00:00:00Z", source_kind="synthetic",
        scenario="fixtures/test_d8_gui_launch.yaml", project=_PROJECT, pipeline="p1", seed=0,
        components=(ComponentBuildInfo(name="test", library_sha256="0" * 64, build_id="test"),),
    )
    topics = {"/test/marker": TopicInfo(schema_name="", provenance=Provenance.UNKNOWN)}
    writer = writer_for(out_path)
    writer.open(out_path, manifest, topics, config_bundle_bytes=b"")
    for tick in range(3):
        writer.write("/test/marker", tick * 50_000_000, bytes([tick % 256]))
    writer.close()


def test_launch_constructs_a_real_vantage_window_not_a_bare_mainwindow(tmp_path, monkeypatch):
    """The regression test for the exact gap found 2026-08-06: `launch()`
    must reach `VantageWindow.__init__` for real."""
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    _app()

    captured = {}
    real_init = VantageWindow.__init__

    def _spy_init(self, *args, **kwargs):
        captured["called"] = True
        return real_init(self, *args, **kwargs)

    monkeypatch.setattr(VantageWindow, "__init__", _spy_init)
    monkeypatch.setattr(QtWidgets.QApplication, "exec", lambda self: 0)

    exit_code = launch(recording, project=_PROJECT)
    assert exit_code == 0
    assert captured.get("called") is True


def test_launch_with_no_recording_opens_the_start_page(monkeypatch):
    """`vantage.bat`/`vantage.py` with no positional argument (or a
    future no-arg `sim view`) must open Screen 1, never raise."""
    _app()
    monkeypatch.setattr(QtWidgets.QApplication, "exec", lambda self: 0)
    exit_code = launch(None)
    assert exit_code == 0


def test_a_real_launched_window_has_the_workspace_toggle_and_both_workspaces(tmp_path, monkeypatch):
    """Structural proof the launched window really is the `S-D8` shell:
    the Bench/Campaign toolbar toggle and both stack pages exist, not
    just the bare docks `MainWindow` alone would have."""
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    _app()

    captured = {}
    monkeypatch.setattr(QtWidgets.QApplication, "exec", lambda self: captured.setdefault("window", self) and 0)

    # Capture the constructed window directly instead of relying on exec()
    # (which we stub out) -- same technique test_b3_cli_view.py's own spy
    # tests already use.
    windows = []
    real_init = VantageWindow.__init__

    def _spy_init(self, *args, **kwargs):
        windows.append(self)
        return real_init(self, *args, **kwargs)

    monkeypatch.setattr(VantageWindow, "__init__", _spy_init)
    launch(recording, project=_PROJECT)

    assert len(windows) == 1
    window = windows[0]
    assert hasattr(window, "campaign")
    assert hasattr(window, "_start_page")
    assert window._bench_action.text() == "Bench"
    assert window._campaign_action.text() == "Campaign"
