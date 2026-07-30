# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B4 `render/capture.py` tests: `UT-B4-1`..`UT-B4-5`
(docs/sim_implementation_plan.md)."""

from __future__ import annotations

import json

import pytest

from adas_sim.core.session import Session
from adas_sim.core.tick import Pose2D, PortValue, Tick
from adas_sim.io.base import ComponentBuildInfo, RunManifest
from adas_sim.render import capture
from adas_sim.scene.registry import layer_provider
from adas_sim.scene.types import Layer, Prim, Scene
from adas_sim.view.viewport import Viewport

_ORIGIN_POSE = Pose2D(x_m=0.0, y_m=0.0, yaw_rad=0.0)

_EXPECTED_SIDECAR_KEYS = (
    "run_id", "tick", "t_ns", "project", "bundle_sha256", "bundle_origin",
    "scenario", "pipeline", "components", "viewport", "layers", "theme",
    "scene_version", "tool_version",
)


@layer_provider("test.b4.box", group="test-b4")
def _box_layer(ctx):
    del ctx
    return (Layer(id="test.b4.box", group="test-b4", prims=(
        Prim(kind="box", cx_m=1.0, cy_m=0.0, length_m=2.0, width_m=1.0, yaw_rad=0.0, style="object.label"),
    )),)


def _session() -> Session:
    tick = Tick(index=0, t_ns=50_000_000, dt_ns=0,
                ports={"p": PortValue(name="p", message=b"", origin="measured")}, pose=_ORIGIN_POSE)
    manifest = RunManifest(
        manifest_version=1, run_id="20260730T000000Z-deadbeef", run_kind="resim",
        created_utc="2026-07-30T00:00:00Z", source_kind="synthetic",
        scenario="fixtures/test_b4.yaml", project="base", pipeline="p1", seed=0,
        components=(ComponentBuildInfo(name="test", library_sha256="0" * 64, build_id="b1"),),
    )
    return Session(run_id=manifest.run_id, name="s", ticks=(tick,), meta=manifest)


def _viewport() -> Viewport:
    return Viewport(size_px=(64, 48), scale_px_per_m=10.0)


def test_snapshot_writes_exactly_two_files(tmp_path):
    """UT-B4-1 (happy path)."""
    out = tmp_path / "fig.png"
    capture.snapshot(_session(), 0, _viewport(), frozenset({"test.b4.box"}), out)

    written = sorted(p.name for p in tmp_path.iterdir())
    assert written == ["fig.json", "fig.png"]


def test_snapshot_writes_neither_file_if_the_pair_cannot_complete(tmp_path, monkeypatch):
    """UT-B4-1 (failure path): a half-written pair is worse than none."""
    out = tmp_path / "fig.png"
    real_replace = capture.os.replace
    calls = []

    def _flaky_replace(src, dst):
        calls.append(dst)
        if len(calls) == 2:  # the sidecar's own rename -- after the image already moved
            raise OSError("simulated disk failure")
        return real_replace(src, dst)

    monkeypatch.setattr(capture.os, "replace", _flaky_replace)
    with pytest.raises(OSError):
        capture.snapshot(_session(), 0, _viewport(), frozenset({"test.b4.box"}), out)

    assert list(tmp_path.iterdir()) == []


def test_sidecar_contains_every_documented_field(tmp_path):
    """UT-B4-2: a missing field fails by name, not by count."""
    out = tmp_path / "fig.png"
    capture.snapshot(_session(), 0, _viewport(), frozenset({"test.b4.box"}), out)

    sidecar = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    for key in _EXPECTED_SIDECAR_KEYS:
        assert key in sidecar, f"sidecar missing {key!r}"


def test_write_pair_shape_is_the_same_regardless_of_image_source(tmp_path):
    """UT-B4-3: `write_pair` is the one path a BEV snapshot and a plot-panel
    capture both go through -- proven here with two different `Scene`s
    standing in for two different panel types, not two write routines."""
    bev_scene = Scene(layers=(Layer(id="df.common.ego", group="df", prims=()),))
    plot_scene = Scene(layers=(Layer(id="view.plots.xy", group="plots", prims=()),))
    session = _session()
    viewport = _viewport()

    bev_sidecar = capture.sidecar_dict(session, 0, bev_scene, viewport, frozenset({"df.common.ego"}), "dark", "base")
    plot_sidecar = capture.sidecar_dict(session, 0, plot_scene, viewport, frozenset({"view.plots.xy"}), "dark", "base")

    capture.write_pair(b"bev-bytes", bev_sidecar, tmp_path / "bev.png")
    capture.write_pair(b"plot-bytes", plot_sidecar, tmp_path / "plot.png")

    assert set(bev_sidecar) == set(plot_sidecar) == set(_EXPECTED_SIDECAR_KEYS)
    assert (tmp_path / "bev.png").read_bytes() == b"bev-bytes"
    assert (tmp_path / "plot.png").read_bytes() == b"plot-bytes"


def test_sidecar_run_id_matches_the_session(tmp_path):
    """UT-B4-4 (`N-9`): given any one artefact you can find the other five."""
    session = _session()
    out = tmp_path / "fig.png"
    capture.snapshot(session, 0, _viewport(), frozenset({"test.b4.box"}), out)

    sidecar = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert sidecar["run_id"] == session.run_id


def test_sidecar_records_bundle_origin(tmp_path):
    """UT-B4-5 (`R-SIM-3a`): a picture rendered from a checkout is
    distinguishable from one rendered from the embedded bundle."""
    out = tmp_path / "fig.png"
    capture.snapshot(_session(), 0, _viewport(), frozenset({"test.b4.box"}), out)

    sidecar = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert sidecar["bundle_origin"] == "checkout"  # no recording/library bundle passed in
    assert sidecar["bundle_sha256"]
