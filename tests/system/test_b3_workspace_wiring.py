# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 slice 9 system tests: `UT-B3-11`/`UT-B3-12` (docs/
sim_implementation_plan.md), the Qt half -- `view/workspace.py`'s own
parsing is already covered headlessly (`tests/unit/test_b3_workspace.py`).
Proves a workspace's first tab actually reaches `MainWindow`'s BEV
viewport and timeline lanes, that a missing file falls back silently,
that a malformed one still raises, and that a user's saved layout beats
the freshly-captured shipped default -- reset returns to the latter.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
from PySide6 import QtCore, QtWidgets  # noqa: E402

from adas_sim.core.errors import AuthoringError  # noqa: E402
from adas_sim.io.base import ComponentBuildInfo, Provenance, RunManifest, TopicInfo  # noqa: E402
from adas_sim.io.registry import writer_for  # noqa: E402
import adas_sim.io.mcap  # noqa: E402,F401 -- registers the ".mcap" codec
import adas_sim.render.viewer as viewer_module  # noqa: E402
from adas_sim.render.viewer import MainWindow, set_high_dpi_policy  # noqa: E402

_PROJECT = "base"
_TICK_COUNT = 5
_DT_NS = 50_000_000

_WORKSPACE_WITH_VIEWPOINT_AND_SIGNALS = """
workspaces:
  default:
    tabs:
      - name: "Main"
        views:
          - {panel: bev, viewpoint: close}
          - {panel: timeline, signals: [test.marker]}
"""

_WORKSPACE_MISSING_DEFAULT = """
workspaces:
  something_else:
    tabs: []
"""


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    root = tmp_path / "config"
    monkeypatch.setattr(viewer_module, "_config_root", lambda: root)
    return root


def _write_synthetic_recording(out_path) -> None:
    manifest = RunManifest(
        manifest_version=1, run_id="test-b3-workspace", run_kind="resim",
        created_utc="2026-07-30T00:00:00Z", source_kind="synthetic",
        scenario="fixtures/test_b3.yaml", project=_PROJECT, pipeline="p1", seed=0,
        components=(ComponentBuildInfo(name="test", library_sha256="0" * 64, build_id="test-b3i"),),
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


def _open_window(recording, **kwargs) -> MainWindow:
    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MainWindow(recording, project=_PROJECT, **kwargs)
    window.show()
    _pump_until_loaded(window)
    assert window.session is not None
    return window


def test_no_workspace_path_falls_back_to_the_default_bev_plus_timeline(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)
    panels = [v.panel for v in window.workspace.tabs[0].views]
    assert panels == ["bev", "timeline"]


def test_a_nonexistent_workspace_path_falls_back_silently(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording, workspace_path=tmp_path / "does-not-exist.yaml")
    assert window.workspace.tabs[0].name == "default"


def test_a_workspace_with_no_default_key_raises(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    ws_path = tmp_path / "workspace.yaml"
    ws_path.write_text(_WORKSPACE_MISSING_DEFAULT, encoding="utf-8")

    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    with pytest.raises(AuthoringError):
        MainWindow(recording, project=_PROJECT, workspace_path=ws_path)


def test_a_workspace_viewpoint_is_applied_to_the_bev(tmp_path):
    """UT-B3-11 (Qt half): a `viewpoint:` the framework's `DEFAULT_PRESETS`
    actually has reaches the BEV panel's viewport."""
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    ws_path = tmp_path / "workspace.yaml"
    ws_path.write_text(_WORKSPACE_WITH_VIEWPOINT_AND_SIGNALS, encoding="utf-8")

    window = _open_window(recording, workspace_path=ws_path)
    assert window.bev.viewport.scale_px_per_m == pytest.approx(20.0)  # "close" preset


def test_a_workspace_timeline_signal_is_added_as_a_lane(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    ws_path = tmp_path / "workspace.yaml"
    ws_path.write_text(_WORKSPACE_WITH_VIEWPOINT_AND_SIGNALS, encoding="utf-8")

    window = _open_window(recording, workspace_path=ws_path)
    assert window.timeline_state.signal_lanes() == ("test.marker",)
    assert "test.marker" in window._signal_series_cache
    assert len(window._signal_series_cache["test.marker"]) == _TICK_COUNT


def test_reset_layout_returns_to_the_shipped_default(tmp_path):
    """UT-B3-12 (reset half)."""
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    assert window.bev.isVisible() is True
    window.bev.close()
    assert window.bev.isVisible() is False

    window._on_reset_layout()
    assert window.bev.isVisible() is True


def test_users_saved_layout_wins_over_the_shipped_default_next_time(tmp_path):
    """UT-B3-12 (persistence half) -- the other side of what `Slice 3`
    already proved for `save_layout`/`restore_layout`, framed here against
    the *shipped default* specifically: a fresh window's initial state is
    the default (BEV visible), but a window opened after a save sees the
    user's own arrangement instead."""
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)
    window.bev.close()
    window.save_layout()

    window2 = _open_window(recording)
    assert window2.bev.isVisible() is False  # user's own layout, not the freshly-captured default
    window2._on_reset_layout()
    assert window2.bev.isVisible() is True  # reset still reaches the shipped default underneath
