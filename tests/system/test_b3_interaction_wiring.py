# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 slice 4 system test: `UT-B3-13`/`UT-B3-14` wired through a real
`MainWindow`, not just `SceneCache` in isolation (`tests/unit/
test_b3_interaction.py` covers the cache mechanics headlessly). Proves the
whole path -- `render_tick(interaction=...)` -> `SceneCache`'s reactive tier
-> `LayerCtx.interaction` -> the provider -- actually delivers the cursor in
the layer's own frame, in metres, and that a non-reactive provider is
genuinely never re-run for it, not merely uninvalidated in a cache that
happens to be unobserved.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
from PySide6 import QtCore, QtWidgets  # noqa: E402

from adas_sim.session.history import Interaction  # noqa: E402
from adas_sim.io.base import ComponentBuildInfo, Provenance, RunManifest, TopicInfo  # noqa: E402
from adas_sim.plugins.registry import writer_for  # noqa: E402
import adas_sim.io.mcap  # noqa: E402,F401 -- registers the ".mcap" codec
import adas_sim.player.shell.qt_window as viewer_module  # noqa: E402
from adas_sim.player.shell.qt_window import MainWindow, set_high_dpi_policy  # noqa: E402
from adas_sim.scene.registry import layer_provider  # noqa: E402
from adas_sim.scene.types import Layer, Prim  # noqa: E402

_PROJECT = "base"
_TICK_COUNT = 3
_DT_NS = 50_000_000

static_calls: list[int] = []
reactive_cursors: list[tuple[float, float] | None] = []


@layer_provider("test.b3d.static", group="test")
def _static_layer(ctx):
    del ctx
    static_calls.append(1)
    return (Layer(id="test.b3d.static", group="test", prims=(
        Prim(kind="box", cx_m=0.0, cy_m=0.0, length_m=4.5, width_m=1.8, style="ego.body"),
    )),)


@layer_provider("test.b3d.reactive", group="test", reacts_to=("cursor",))
def _reactive_layer(ctx):
    cursor = ctx.interaction.cursor
    reactive_cursors.append(cursor)
    if cursor is None:
        return (Layer(id="test.b3d.reactive", group="test", prims=()),)
    cx_m, cy_m = cursor
    return (Layer(id="test.b3d.reactive", group="test", prims=(
        Prim(kind="circle", cx_m=cx_m, cy_m=cy_m, r_m=0.3, style="object.selected"),
    )),)


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    root = tmp_path / "config"
    monkeypatch.setattr(viewer_module, "_config_root", lambda: root)
    return root


def _write_synthetic_recording(out_path) -> None:
    manifest = RunManifest(
        manifest_version=1, run_id="test-b3-interaction", run_kind="resim",
        created_utc="2026-07-30T00:00:00Z", source_kind="synthetic",
        scenario="fixtures/test_b3.yaml", project=_PROJECT, pipeline="p1", seed=0,
        components=(ComponentBuildInfo(name="test", library_sha256="0" * 64, build_id="test-b3d"),),
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


def test_reactive_provider_updates_and_static_provider_does_not(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    static_calls.clear()
    reactive_cursors.clear()

    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MainWindow(recording, project=_PROJECT)
    _pump_until_loaded(window)
    assert window.session is not None

    # _on_loaded's own render_tick(0) already primed tick 0's static tier
    # (with the no-op default interaction) -- baseline against that rather
    # than assume the cache starts empty, and clear the module-level probes
    # so this test only asserts on what it does itself.
    build_calls_before = window._scene_cache.build_calls
    reactive_calls_before = window._scene_cache.reactive_build_calls
    static_calls.clear()
    reactive_cursors.clear()

    window.render_tick(0, interaction=Interaction(cursor=(1.0, 2.0)))
    assert window._scene_cache.build_calls == build_calls_before  # tick 0's static tier was already cached
    assert window._scene_cache.reactive_build_calls == reactive_calls_before + 1
    assert reactive_cursors[-1] == (1.0, 2.0)  # delivered in metres, unchanged -- no viewport in the path
    assert static_calls == []  # the static provider itself was never called again

    # Same interaction again: UT-B3-14 generalised -- neither tier reruns.
    window.render_tick(0, interaction=Interaction(cursor=(1.0, 2.0)))
    assert window._scene_cache.build_calls == build_calls_before
    assert window._scene_cache.reactive_build_calls == reactive_calls_before + 1

    # A real cursor change: UT-B3-13 -- the reactive provider re-renders...
    window.render_tick(0, interaction=Interaction(cursor=(9.0, 9.0)))
    assert window._scene_cache.reactive_build_calls == reactive_calls_before + 2
    assert reactive_cursors[-1] == (9.0, 9.0)
    # ...UT-B3-14 -- but the non-reactive provider was never called again.
    assert window._scene_cache.build_calls == build_calls_before
    assert static_calls == []
