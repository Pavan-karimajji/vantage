# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 system test: a scoped precursor to `ST-B3-2`. Proves the window,
threading and the BEV panel render a real frame under an offscreen platform
(P-7) end to end -- construction through the async load. Full `ST-B3-2`
("the full panel set opens ... on both platforms") closes once the
layers/inspector/timeline/plots/measure panels from later S-B3 slices exist;
this test does not claim that yet.

Self-contained (no `modules/df` dependency): writes its own tiny recording
with a topic name that cannot match any real component's `requires=` (a
process-wide pytest run has already imported `modules/df/sim/layers` by the
time this test runs, via the S-B1 tests -- `tests/fixtures/tiny.mcap`'s own
`/source/*` topic names collide with `df`'s gated ports on purpose for other
tests, so this file deliberately does not reuse it), and registers its own
trivial layer provider -- the same "framework's own suite is self-contained"
discipline the S-A1..S-A4 goldens use.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
from PySide6 import QtCore, QtWidgets  # noqa: E402

QtCore.QStandardPaths.setTestModeEnabled(True)  # P-7: never touch the real user profile in tests

from adas_sim.io.base import ComponentBuildInfo, Provenance, RunManifest, TopicInfo  # noqa: E402
from adas_sim.plugins.registry import writer_for  # noqa: E402
import adas_sim.io.mcap  # noqa: E402,F401 -- registers the ".mcap" codec
from adas_sim.player.shell.qt_window import MainWindow, set_high_dpi_policy  # noqa: E402
from adas_sim.scene.registry import layer_provider  # noqa: E402
from adas_sim.scene.types import Layer, Prim  # noqa: E402

_TICK_COUNT = 5
_DT_NS = 50_000_000


@layer_provider("test.b3.ego", group="test")
def _fixed_ego_layer(ctx):
    del ctx
    return (Layer(id="test.b3.ego", group="test", prims=(
        Prim(kind="box", cx_m=0.0, cy_m=0.0, length_m=4.5, width_m=1.8, style="ego.body"),
    )),)


def _write_synthetic_recording(out_path) -> None:
    manifest = RunManifest(
        manifest_version=1, run_id="test-b3-offscreen", run_kind="resim",
        created_utc="2026-07-29T00:00:00Z", source_kind="synthetic",
        scenario="fixtures/test_b3.yaml", project="base", pipeline="none", seed=0,
        components=(ComponentBuildInfo(name="test", library_sha256="0" * 64, build_id="test-b3"),),
    )
    #: `/test/marker` deliberately names no real component's port -- df's
    #: `objects_layer`/`hud_layer` (`requires=("source.gen_object_list",)` /
    #: `("source.veh_dyn",)`) must stay gated off here, not crash on a byte
    #: payload that isn't the protobuf message they expect.
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


def test_window_loads_and_renders_a_non_blank_frame_offscreen(tmp_path):
    recording = tmp_path / "test_b3.mcap"
    _write_synthetic_recording(recording)

    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MainWindow(recording)

    _pump_until_loaded(window)

    assert window.session is not None, "session never finished loading"
    assert len(window.session) == _TICK_COUNT

    pixmap = window.bev.pixmap()
    assert pixmap is not None and not pixmap.isNull()
    assert pixmap.width() > 0 and pixmap.height() > 0


def test_layers_panel_populates_and_toggling_changes_the_frame(tmp_path):
    """The layers dock (Slice 2) end to end: it discovers the one layer this
    recording's Scene carries, and hiding it actually changes what the BEV
    panel shows -- not just what `LayerTreeState` reports."""
    recording = tmp_path / "test_b3.mcap"
    _write_synthetic_recording(recording)

    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MainWindow(recording)
    _pump_until_loaded(window)
    assert window.session is not None

    assert "test" in window.layers_state.groups()
    assert window.layers_state.is_visible("test.b3.ego") is True
    image_shown = window.bev.pixmap().toImage()

    window.layers_state.set_group_visible("test", False)
    window.render_tick(0)
    image_hidden = window.bev.pixmap().toImage()
    assert image_hidden != image_shown, "hiding the only layer did not change the rendered frame"

    window.layers_state.set_group_visible("test", True)
    window.render_tick(0)
    image_restored = window.bev.pixmap().toImage()
    assert image_restored == image_shown, "re-showing the layer did not restore the original frame"
