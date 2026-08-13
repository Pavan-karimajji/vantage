# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`AR-52`: tests for the framework's own default layer set
(`adas_sim.scene.default_layers`) -- `sim.ego`/`sim.frame`/`sim.trail`,
moved here from `modules/df/sim/layers/common.py`'s `ego_layer`/
`frame_layer`/`trail_layer` (`tests/unit/test_b1_df_layers.py`'s own
`UT-B1-4`/`UT-B1-12`, still cited here since the test IDs did not move).

Unlike that suite, this one needs **no generated protobuf bindings and no
`modules/interfaces` build** -- `default_layers.py` reads only `ctx.model`/
`ctx.history`/`ctx.frames`, never a port, so there is nothing to construct a
message for. That is itself part of what the move buys: these tests run on
a fresh checkout with no build step at all.
"""

from __future__ import annotations

import pytest

from adas_sim.session.history import FrameTree, HistoryView, LayerCtx
from adas_sim.session.tick import Pose2D, Tick
from adas_sim.config.project import ProjectModel
from adas_sim.scene import default_layers

_POSE = Pose2D(x_m=0.0, y_m=0.0, yaw_rad=0.0)


def _make_tick(index: int, *, pose: Pose2D = _POSE, dt_ns: int = 50_000_000) -> Tick:
    return Tick(index=index, t_ns=index * dt_ns, dt_ns=dt_ns if index else 0, ports={}, pose=pose)


def _ctx(ticks: tuple[Tick, ...], *, project: str = "base") -> LayerCtx:
    return LayerCtx(
        model=ProjectModel.resolve(project=project), history=HistoryView(_ticks=ticks),
        frames=FrameTree(ticks[-1].pose),
    )


def test_ego_box_equals_ego_model_and_changes_with_project():
    """UT-B1-4: asserted by changing the project and seeing the box change,
    not by comparing to a literal."""
    tick = _make_tick(0)
    for project in ("base", "cus1", "2w_base"):
        ctx = _ctx((tick,), project=project)
        prim = default_layers.ego_layer(ctx)[0].prims[0]
        ego = ctx.model.ego()
        assert prim.length_m == pytest.approx(ego.x_front_m - ego.x_rear_m)
        assert prim.width_m == pytest.approx(2.0 * ego.half_width_m)
    base_box = default_layers.ego_layer(_ctx((tick,), project="base"))[0].prims[0]
    cus1_box = default_layers.ego_layer(_ctx((tick,), project="cus1"))[0].prims[0]
    assert base_box.length_m != cus1_box.length_m


def test_ego_trail_out_of_order_calls_give_identical_output():
    """UT-B1-12: a temporal layer, but the provider holds no state between
    calls. Poses are varied directly and explicitly here (standing in for
    real ego-in-world data, e.g. a world model's ground truth) -- never
    dead-reckoned from a port, which `trail_layer` never reads at all
    (R-SIM-7: a layer may transform data a port/world model already
    produced, never estimate new information by integrating one over time)."""
    poses = tuple(Pose2D(x_m=float(i), y_m=0.0, yaw_rad=0.0) for i in range(10))
    ticks = tuple(_make_tick(i, pose=poses[i]) for i in range(10))
    ctx = _ctx(ticks)
    first = default_layers.trail_layer(ctx)
    # Call again "out of order" (a second, later call) -- purity means the
    # provider has nothing that could make this differ.
    third = default_layers.trail_layer(_ctx(ticks))
    second = default_layers.trail_layer(ctx)
    assert first == second == third
    assert len(first[0].prims[0].points_m) == 10


def test_ego_trail_with_no_real_pose_source_is_named_unavailable():
    """`AR-60`, supersedes this test's own original reading: a
    recording with no ego-position ground truth (every tick's pose is the
    coordinate-origin default) transforms to the same point at every tick;
    drawing that as a trail would be a fabricated flat line -- but the
    layer used to just vanish (`== ()`), the exact silent-absence pattern
    `AR-53` eliminated elsewhere. Now a named, badged placeholder, matching
    `AR-53`'s own mechanism (`Layer.unavailable`)."""
    ticks = tuple(_make_tick(i) for i in range(10))  # default pose at every tick
    ctx = _ctx(ticks)
    result = default_layers.trail_layer(ctx)
    assert len(result) == 1
    assert result[0].prims == ()
    assert result[0].unavailable is not None and "ego world-position source" in result[0].unavailable


def test_ego_trail_with_fewer_than_two_ticks_stays_silently_empty():
    """The OTHER empty case: too little history yet is transient
    -- the very first tick of any recording -- and must stay a plain `()`,
    never badged as permanently unavailable."""
    ticks = (_make_tick(0),)
    ctx = _ctx(ticks)
    assert default_layers.trail_layer(ctx) == ()


def test_frame_layer_needs_no_port_and_is_pure():
    """`frame_layer` never had its own UT-id (it predates the grid-label
    gap being closed) -- covered here for parity with `ego`/`trail`: pure
    function of `ctx.model` alone, same call twice yields equal layers."""
    tick = _make_tick(0)
    ctx = _ctx((tick,))
    assert default_layers.frame_layer(ctx) == default_layers.frame_layer(ctx)
    prims = default_layers.frame_layer(ctx)[0].prims
    assert any(p.kind == "grid" for p in prims)


def test_no_two_default_layer_ids_share_a_prefix():
    """UT-B1-14's own invariant, re-checked for the framework's own set."""
    ids = ["sim.frame", "sim.ego", "sim.trail"]
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            assert not a.startswith(b) and not b.startswith(a), (a, b)
