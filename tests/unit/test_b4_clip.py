# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B4 `render/clip.py` tests (docs/sim_implementation_plan.md).
`imageio[ffmpeg]` is the `video` extra (`pyproject.toml`) -- skipped, not
failed, where it is not installed."""

from __future__ import annotations

import json

import pytest

from adas_sim.core.session import Session
from adas_sim.core.tick import Pose2D, PortValue, Tick
from adas_sim.io.base import ComponentBuildInfo, RunManifest
from adas_sim.scene.registry import layer_provider
from adas_sim.scene.types import Layer, Prim
from adas_sim.view.viewport import Viewport

pytest.importorskip("imageio")

from adas_sim.render import clip  # noqa: E402

_ORIGIN_POSE = Pose2D(x_m=0.0, y_m=0.0, yaw_rad=0.0)
_DT_NS = 50_000_000
_TICK_COUNT = 6


@layer_provider("test.b4c.box", group="test-b4c")
def _box_layer(ctx):
    del ctx
    return (Layer(id="test.b4c.box", group="test-b4c", prims=(
        Prim(kind="box", cx_m=1.0, cy_m=0.0, length_m=2.0, width_m=1.0, yaw_rad=0.0, style="object.label"),
    )),)


def _session() -> Session:
    ticks = tuple(
        Tick(index=i, t_ns=i * _DT_NS, dt_ns=_DT_NS if i else 0,
             ports={"p": PortValue(name="p", message=b"", origin="measured")}, pose=_ORIGIN_POSE)
        for i in range(_TICK_COUNT)
    )
    manifest = RunManifest(
        manifest_version=1, run_id="20260730T000000Z-c11pc11p", run_kind="resim",
        created_utc="2026-07-30T00:00:00Z", source_kind="synthetic",
        scenario="fixtures/test_b4_clip.yaml", project="base", pipeline="p1", seed=0,
        components=(ComponentBuildInfo(name="test", library_sha256="0" * 64, build_id="b1"),),
    )
    return Session(run_id=manifest.run_id, name="s", ticks=ticks, meta=manifest)


def test_export_clip_writes_an_mp4_and_a_sidecar(tmp_path):
    out = tmp_path / "clip.mp4"
    session = _session()
    clip.export_clip(session, 0.0, 0.25, Viewport(size_px=(64, 48)), frozenset({"test.b4c.box"}), out)

    assert out.is_file() and out.stat().st_size > 0
    sidecar = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert sidecar["run_id"] == session.run_id
    assert sidecar["clip_tick_count"] == 6
    assert sidecar["clip_t_start_s"] == pytest.approx(0.0)
    assert sidecar["clip_t_end_s"] == pytest.approx(0.25)


def test_export_clip_rejects_a_non_mp4_output(tmp_path):
    with pytest.raises(ValueError):
        clip.export_clip(_session(), 0.0, 0.1, Viewport(size_px=(64, 48)), None, tmp_path / "clip.mov")
