# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B4 `render/clip.py` tests (docs/sim_implementation_plan.md), including
the `export_clip()` half of `UT-B4-6`.
`imageio[ffmpeg]` is the `video` extra (`pyproject.toml`) -- skipped, not
failed, where it is not installed."""

from __future__ import annotations

import json

import pytest

from adas_sim.session.session import Session
from adas_sim.session.tick import Pose2D, PortValue, Tick
from adas_sim.io.base import ComponentBuildInfo, RunManifest
from adas_sim.config.project import ProjectModel
from adas_sim.scene import registry as scene_registry
from adas_sim.scene.registry import layer_provider
from adas_sim.scene.types import Layer, Prim
from adas_sim.player.panels.viewport import Viewport

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


@layer_provider("test.b4c.hidden_by_default", group="test-b4c")
def _hidden_layer(ctx):
    del ctx
    return (Layer(
        id="test.b4c.hidden_by_default", group="test-b4c", default_on=False, prims=(
            Prim(kind="circle", cx_m=5.0, cy_m=5.0, r_m=1.0, style="sensor.fov"),
        ),
    ),)


@layer_provider("test.b4c.needs_bundle_dir", group="test-b4c")
def _needs_bundle_dir_layer(ctx):
    """Same regression shape as `test_b4_capture.py`'s own: a prim only
    when `ctx.model.bundle_dir` is populated, so a silently-dropped
    `model=` shows up as a missing layer across every frame."""
    if ctx.model.bundle_dir is None:
        return ()
    return (Layer(id="test.b4c.needs_bundle_dir", group="test-b4c", prims=(
        Prim(kind="box", cx_m=0.0, cy_m=0.0, length_m=1.0, width_m=1.0, yaw_rad=0.0, style="object.label"),
    )),)


_EGO_TEMPLATE = (
    "EGO_LENGTH_M: 4.5\n"
    "EGO_WIDTH_M: 1.8\n"
    "EGO_WHEELBASE_M: 2.7\n"
    "EGO_OVERHANG_FRONT_M: 0.9\n"
)


def _make_bundle_dir(root):
    bundle_dir = root / "library_bundle"
    (bundle_dir / "vehicle").mkdir(parents=True)
    (bundle_dir / "vehicle" / "ego_params.yaml").write_text(_EGO_TEMPLATE, encoding="utf-8")
    (bundle_dir / "manifest.yaml").write_text("project: fx\n", encoding="utf-8")
    return bundle_dir


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


def test_export_clip_with_no_explicit_selection_matches_the_guis_own_default(tmp_path):
    """`AR-58`: the same fix `snapshot()` got, for its `S-B4`
    sibling -- resolved once off the first tick (`capture.resolve_layer_
    selection`) and held fixed for every frame, so a `default_on=False`
    layer stays off for the whole clip, not flickering per tick."""
    out = tmp_path / "clip.mp4"
    clip.export_clip(_session(), 0.0, 0.1, Viewport(size_px=(64, 48)), None, out)

    sidecar = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert sidecar["layers"] is not None
    assert "test.b4c.box" in sidecar["layers"]
    assert "test.b4c.hidden_by_default" not in sidecar["layers"]


def test_export_clip_threads_a_given_model_through_instead_of_re_resolving(tmp_path, monkeypatch):
    """`UT-B4-6`'s `export_clip()` half. Regression, same bug class `test_b4_capture.py`'s own test guards:
    `export_clip()` used to call `build_scene(...)` per tick with no
    `model=` at all, so a plugin-root-resolved `ProjectModel` (`cli/render.py
    --plugin-root`, once added) was silently dropped for every frame of a
    clip, not just the first.

    **Registry isolated to this file's own providers** -- same reason
    `test_b4_capture.py`'s sibling test isolates it: `build_scene` calls
    every globally registered provider, and a real component's own layer
    (imported by an unrelated test elsewhere this session) would see this
    test's `bundle_dir` too and crash on a bundle shaped for this test
    only."""
    monkeypatch.setattr(scene_registry, "_PROVIDERS", {
        k: v for k, v in scene_registry._PROVIDERS.items() if v.group in ("test-b4c",)
    })
    bundle_dir = _make_bundle_dir(tmp_path)
    model = ProjectModel.resolve(library_dir=bundle_dir, project="fx")
    assert model.bundle_dir == bundle_dir

    out = tmp_path / "clip.mp4"
    clip.export_clip(_session(), 0.0, 0.1, Viewport(size_px=(64, 48)), None, out, model=model)

    sidecar = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert sidecar["bundle_origin"] == "library"
    assert "test.b4c.needs_bundle_dir" in sidecar["layers"]
