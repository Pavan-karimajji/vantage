# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji
# noqa: E402 -- intentional: PySide6/Qt imports need QT_QPA_PLATFORM set first

"""S-B3 `ST-B3-2`'s full claim (docs/sim_implementation_plan.md): every
panel the stage built -- `BevPanel`, `LayersPanel`, `InspectorPanel`,
`TimelineStrip`, `TransportBar`, a `PlotPanel` -- opens and renders a real
frame together, offscreen, end to end. `test_b3_offscreen_smoke.py`
(`S-B3` Slice 1) proved this for the window + `BevPanel` alone, before the
other panels existed; this is the completed claim now that they all do.

**Windows only, not "on both platforms."** `P-7`'s own text requires
Ubuntu too -- this session has no Ubuntu environment to verify against, so
that half of `ST-B3-2` is not something this test, or this session, can
close. The offscreen-platform mechanism itself (`QT_QPA_PLATFORM=offscreen`)
is the same code path either way; what is unverified is the platform, not
the mechanism.
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
_TICK_COUNT = 5
_DT_NS = 50_000_000
_GROUP = "test-b3n"


@layer_provider("test.b3n.box", group=_GROUP)
def _box_layer(ctx):
    del ctx
    return (Layer(id="test.b3n.box", group=_GROUP, prims=(
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
        manifest_version=1, run_id="test-b3-full-shell", run_kind="resim",
        created_utc="2026-07-30T00:00:00Z", source_kind="synthetic",
        scenario="fixtures/test_b3.yaml", project=_PROJECT, pipeline="p1", seed=0,
        components=(ComponentBuildInfo(name="test", library_sha256="0" * 64, build_id="test-b3n"),),
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


def test_every_panel_type_opens_and_renders_together_offscreen(tmp_path, monkeypatch):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)

    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MainWindow(recording, project=_PROJECT)
    window.show()
    _pump_until_loaded(window)
    assert window.session is not None

    # BevPanel + LayersPanel + InspectorPanel + TimelineStrip + TransportBar
    # all construct in MainWindow.__init__ and are already exercised by the
    # load above; add one of each remaining peer-panel kind (a PlotPanel)
    # and select something so the inspector has real content too.
    monkeypatch.setattr(QtWidgets.QInputDialog, "getText", staticmethod(lambda *a, **k: ("test.marker", True)))
    window._on_add_plot("timeseries")
    assert len(window.plot_panels) == 1
    # A dock added via addDockWidget after the window is already shown needs
    # one event-loop pass before its own isVisible() reflects that (the same
    # "whole ancestor chain" timing Slice 7a's own offscreen tests found).
    QtWidgets.QApplication.processEvents()

    box_px = window.bev.viewport.to_px(10.0, 0.0)
    window.bev._label.clicked.emit(*box_px, QtCore.Qt.KeyboardModifier.NoModifier)
    assert window._selection == frozenset({"box"})

    # `AR-59` (2026-08-07): `inspector_panel` starts hidden by default now
    # (`sim_player.md` §3: "everything else... closed by default") -- open
    # it explicitly, the same as a real user clicking its View-menu entry,
    # so this test still proves it renders once open rather than asserting
    # the old "visible from the start" default this row corrected.
    window.inspector_panel.show()
    QtWidgets.QApplication.processEvents()

    # Every panel actually rendered a real, non-null frame.
    assert not window.bev.pixmap().isNull()
    assert not window.timeline_strip.pixmap().isNull()
    assert not window.plot_panels[0].pixmap().isNull()

    # And every dock is a real, visible widget in the shell.
    for panel in (window.bev, window.layers_panel, window.inspector_panel,
                  window.timeline_strip, window.plot_panels[0]):
        assert panel.isVisible()
    assert window.transport_bar.isVisible()

    # Scrubbing still works with every panel open.
    window.transport_bar.step(2)
    assert window._current_tick == 2
