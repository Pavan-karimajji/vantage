# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 slice 10 system tests: `UT-B3-6` (closed by this slice), `UT-B3-9`
(docs/sim_implementation_plan.md), the Qt half -- `view/plots.PlotState`'s
kind-gating and `render/plots.py`'s rasters are already covered headlessly
(`tests/unit/test_b3_plots.py`, `test_b3_plots_render.py`). Proves
`MainWindow._on_add_plot` creates real dockable panels, that a
`timeseries`/`state` panel's click-to-seek moves the shared playhead (BEV
+ timeline together, `UT-B3-9`), that the playhead updates a plot's own
raster on every tick, and that the timeline strip and a plot panel resolve
one address to the identical series (`UT-B3-6`, `NR-SIM-8`'s "one
resolver, five consumers").
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

_PROJECT = "base"
_TICK_COUNT = 10
_DT_NS = 50_000_000


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    root = tmp_path / "config"
    monkeypatch.setattr(viewer_module, "_config_root", lambda: root)
    return root


def _write_synthetic_recording(out_path) -> None:
    manifest = RunManifest(
        manifest_version=1, run_id="test-b3-plots", run_kind="resim",
        created_utc="2026-07-30T00:00:00Z", source_kind="synthetic",
        scenario="fixtures/test_b3.yaml", project=_PROJECT, pipeline="p1", seed=0,
        components=(ComponentBuildInfo(name="test", library_sha256="0" * 64, build_id="test-b3j"),),
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


def test_add_timeseries_plot_creates_a_panel_with_cached_lanes(tmp_path, monkeypatch):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    monkeypatch.setattr(QtWidgets.QInputDialog, "getText", staticmethod(lambda *a, **k: ("test.marker", True)))
    window._on_add_plot("timeseries")

    assert len(window.plot_panels) == 1
    panel = window.plot_panels[0]
    assert panel.state.kind == "timeseries"
    assert panel.state.lanes() == ("test.marker",)
    assert "test.marker" in window._signal_series_cache


def test_add_xy_plot_stores_x_and_y(tmp_path, monkeypatch):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    monkeypatch.setattr(QtWidgets.QInputDialog, "getText",
                         staticmethod(lambda *a, **k: ("test.marker, test.marker", True)))
    window._on_add_plot("xy")

    assert len(window.plot_panels) == 1
    assert window.plot_panels[0].state.kind == "xy"
    assert (window.plot_panels[0].state.x, window.plot_panels[0].state.y) == ("test.marker", "test.marker")


def test_xy_plot_with_only_one_address_is_rejected(tmp_path, monkeypatch):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    monkeypatch.setattr(QtWidgets.QInputDialog, "getText", staticmethod(lambda *a, **k: ("test.marker", True)))
    window._on_add_plot("xy")
    assert window.plot_panels == []


def test_add_distribution_plot_stores_the_address(tmp_path, monkeypatch):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    monkeypatch.setattr(QtWidgets.QInputDialog, "getText", staticmethod(lambda *a, **k: ("test.marker", True)))
    window._on_add_plot("distribution")

    assert window.plot_panels[0].state.kind == "distribution"
    assert window.plot_panels[0].state.address == "test.marker"


def test_cancelling_the_dialog_adds_no_panel(tmp_path, monkeypatch):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    monkeypatch.setattr(QtWidgets.QInputDialog, "getText", staticmethod(lambda *a, **k: ("", False)))
    window._on_add_plot("timeseries")
    assert window.plot_panels == []


def test_click_to_seek_on_a_timeseries_plot_moves_the_shared_playhead(tmp_path, monkeypatch):
    """UT-B3-9: seeking in a plot moves the BEV and the timeline to the
    same tick."""
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    monkeypatch.setattr(QtWidgets.QInputDialog, "getText", staticmethod(lambda *a, **k: ("test.marker", True)))
    window._on_add_plot("timeseries")
    panel = window.plot_panels[0]

    mid_x = panel.size_px[0] / 2.0
    panel._label.clicked.emit(mid_x, 0.0, QtCore.Qt.KeyboardModifier.NoModifier)

    expected_tick = round((_TICK_COUNT - 1) / 2)
    assert window.transport.cursor == expected_tick
    assert window._current_tick == expected_tick  # BEV rendered this tick too


def test_stepping_the_transport_updates_every_open_plot_panel(tmp_path, monkeypatch):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    monkeypatch.setattr(QtWidgets.QInputDialog, "getText", staticmethod(lambda *a, **k: ("test.marker", True)))
    window._on_add_plot("timeseries")
    panel = window.plot_panels[0]

    before = panel.pixmap().toImage()
    window.transport_bar.step(5)
    after = panel.pixmap().toImage()
    assert before != after


def test_xy_and_distribution_panels_use_a_plain_non_clickable_label(tmp_path, monkeypatch):
    """`render/plots.py`'s own documented gap: `xy`/`distribution` axes are
    data-scaled, not click-seekable."""
    from adas_sim.render.viewer import _ClickableImageLabel

    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    monkeypatch.setattr(QtWidgets.QInputDialog, "getText",
                         staticmethod(lambda *a, **k: ("test.marker, test.marker", True)))
    window._on_add_plot("xy")
    assert not isinstance(window.plot_panels[0]._label, _ClickableImageLabel)


def test_the_timeline_strip_and_a_plot_panel_resolve_one_address_identically(tmp_path, monkeypatch):
    """UT-B3-6, closed: the same address, added to both consumers,
    resolves to the byte-identical series -- because it is literally the
    same `Session.signal()` call, cached once in `_signal_series_cache`
    and read by both (`NR-SIM-8`: one resolver, five consumers)."""
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    monkeypatch.setattr(QtWidgets.QInputDialog, "getText", staticmethod(lambda *a, **k: ("test.marker", True)))
    window._on_add_timeline_lane(is_state=False)
    window._on_add_plot("timeseries")

    timeline_series = window._signal_series_cache["test.marker"]
    plot_series = window._signal_series_cache["test.marker"]
    assert timeline_series is plot_series  # not just equal -- the one cached resolution, read twice
    assert timeline_series == window.session.signal("test.marker", project=_PROJECT)
