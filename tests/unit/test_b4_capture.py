# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B4 `render/capture.py` tests: `UT-B4-1`..`UT-B4-6`
(docs/sim_implementation_plan.md)."""

from __future__ import annotations

import json

import pytest

from adas_sim.session.session import Session
from adas_sim.session.tick import Pose2D, PortValue, Tick
from adas_sim.io.base import ComponentBuildInfo, RunManifest
from adas_sim.config.project import ProjectModel
from adas_sim.render import capture
from adas_sim.scene import registry as scene_registry
from adas_sim.scene.registry import layer_provider
from adas_sim.scene.types import Layer, Prim, Scene
from adas_sim.player.panels.viewport import Viewport

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


@layer_provider("test.b4.needs_bundle_dir", group="test-b4")
def _needs_bundle_dir_layer(ctx):
    """Mirrors a real component's own calibration-reading pattern (e.g.
    `df/sim/layers/bsd.py`'s `_bsd_calibration`): a prim only when
    `ctx.model.bundle_dir` is populated, so a test can tell whether
    `snapshot()`/`export_clip()` actually threaded a plugin-root-resolved
    `ProjectModel` through, rather than silently re-resolving a checkout
    default that has no `bundle_dir` at all."""
    if ctx.model.bundle_dir is None:
        return ()
    return (Layer(id="test.b4.needs_bundle_dir", group="test-b4", prims=(
        Prim(kind="box", cx_m=0.0, cy_m=0.0, length_m=1.0, width_m=1.0, yaw_rad=0.0, style="object.label"),
    )),)

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


@layer_provider("test.b4.hidden_by_default", group="test-b4")
def _hidden_layer(ctx):
    del ctx
    return (Layer(
        id="test.b4.hidden_by_default", group="test-b4", default_on=False, prims=(
            Prim(kind="circle", cx_m=5.0, cy_m=5.0, r_m=1.0, style="sensor.fov"),
        ),
    ),)


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


def test_snapshot_with_no_explicit_selection_matches_the_guis_own_default(tmp_path):
    """`AR-58`: `layer_selection=None` used to mean "draw
    literally every layer the Scene carries" -- so a layer the live window
    hides by default (`Layer.default_on=False`) still dominated a headless
    snapshot, and the sidecar recorded `"layers": null`, unable to say
    which ones. `None` now resolves through `LayerTreeState` (the GUI's
    own class) the same way a fresh, nothing-clicked `LayersPanel` would."""
    out = tmp_path / "fig.png"
    capture.snapshot(_session(), 0, _viewport(), None, out)

    sidecar = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert sidecar["layers"] is not None  # never the unresolved "null" that named neither side
    assert "test.b4.box" in sidecar["layers"]
    assert "test.b4.hidden_by_default" not in sidecar["layers"]


def test_snapshot_with_an_explicit_selection_still_overrides_the_default(tmp_path):
    """A caller that DOES pass a real selection is unaffected -- `AR-58`
    only changes what `None` means, never overrides an explicit choice,
    including one that deliberately includes a `default_on=False` layer."""
    out = tmp_path / "fig.png"
    capture.snapshot(_session(), 0, _viewport(), frozenset({"test.b4.hidden_by_default"}), out)

    sidecar = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert sidecar["layers"] == ["test.b4.hidden_by_default"]


def test_sidecar_records_bundle_origin(tmp_path):
    """UT-B4-5 (`R-SIM-3a`): a picture rendered from a checkout is
    distinguishable from one rendered from the embedded bundle."""
    out = tmp_path / "fig.png"
    capture.snapshot(_session(), 0, _viewport(), frozenset({"test.b4.box"}), out)

    sidecar = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert sidecar["bundle_origin"] == "checkout"  # no recording/library bundle passed in
    assert sidecar["bundle_sha256"]


def test_snapshot_threads_a_given_model_through_instead_of_re_resolving(tmp_path, monkeypatch):
    """`UT-B4-6`. Regression: `snapshot()` used to always call `build_scene(...)` with
    no `model=`, so it silently re-resolved a checkout-default `ProjectModel`
    even when the caller had already resolved one with a `library_dir=`
    (e.g. `cli/render.py --plugin-root`). That fell a component's own
    calibration-reading layer code back to a source-checkout path a
    DEPLOYED copy does not have, crashing with `FileNotFoundError`
    (`sim_implementation_plan.md` S-C8's gate). Proven here without a real
    component: a test-only layer only produces a prim when
    `ctx.model.bundle_dir` is populated, so a `model=` that was silently
    dropped shows up as a missing layer, not a crash -- a clearer failure
    for this test than reproducing the exact exception.

    **The registry is isolated to this file's own providers**, restored by
    `monkeypatch` on teardown: `build_scene` calls every GLOBALLY registered
    provider (`scene.registry` is process-wide, `R-VAR-2`), and any real
    component's own layer (e.g. `df.sim.layers.bsd`, imported by an
    unrelated test elsewhere in this same session) would see this test's
    `bundle_dir` too and crash on a bundle shaped for this test only, not
    for that component's own calibration keys -- exactly the
    order-dependent collision `test_c8_relocatability_installed.py`'s own
    docstring names and sidesteps with a fresh subprocess instead."""
    monkeypatch.setattr(scene_registry, "_PROVIDERS", {
        k: v for k, v in scene_registry._PROVIDERS.items() if v.group in ("test-b4",)
    })
    bundle_dir = _make_bundle_dir(tmp_path)
    model = ProjectModel.resolve(library_dir=bundle_dir, project="fx")
    assert model.bundle_dir == bundle_dir  # sanity: the fixture is bundle-shaped

    # `layer_selection=None`: the sidecar's own "layers" list is then
    # `LayerTreeState.sync(scene.layers)`'s output, which only names a
    # layer that the SCENE actually produced -- an explicit selection
    # would just echo the request back regardless of what rendered.
    out = tmp_path / "fig.png"
    capture.snapshot(_session(), 0, _viewport(), None, out, model=model)
    sidecar = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert sidecar["bundle_origin"] == "library"
    assert "test.b4.needs_bundle_dir" in sidecar["layers"]


def test_snapshot_with_no_model_still_resolves_a_default_unchanged(tmp_path):
    """The `model=None` default must stay exactly what it was before
    `model=` existed -- a checkout-resolved `ProjectModel`, `bundle_dir`
    `None` -- so every existing caller that never passes `model=` sees no
    behaviour change."""
    out = tmp_path / "fig.png"
    capture.snapshot(_session(), 0, _viewport(), None, out)
    sidecar = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert sidecar["bundle_origin"] == "checkout"
    assert "test.b4.needs_bundle_dir" not in sidecar["layers"]
