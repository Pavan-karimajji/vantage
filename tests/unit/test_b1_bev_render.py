# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B1 `render/bev.py` test: UT-B1-10 (docs/sim_implementation_plan.md).
`scene_bounds_m` (S-B3 slice 7a, "F to fit") and `anchor_points_m` (slice
11, ruler snap targets) reuse the same `_prim_bounds_m` this file already
exercises through `hit_test`."""

from __future__ import annotations

import numpy as np

from adas_sim.render.bev import anchor_points_m, hit_test, render_scene, scene_bounds_m
from adas_sim.scene.types import Layer, Prim, Scene
from adas_sim.view.viewport import Viewport


def _scene():
    # Positioned so no two prims' bounding boxes overlap (hit_test's bbox
    # approximation is imprecise for a diagonal line, see render/bev.py's
    # own note -- kept separated here rather than exercising that overlap).
    box = Prim(kind="box", cx_m=5.0, cy_m=-10.0, length_m=2.0, width_m=1.0, yaw_rad=0.0,
               style="ego.body", pick_id="box", z=1)
    circle = Prim(kind="circle", cx_m=10.0, cy_m=2.0, r_m=0.5, style="sensor.range_ring",
                  pick_id="circle", z=1)
    line = Prim(kind="polyline", points_m=((0.0, 0.0), (5.0, 5.0)), style="frame.grid",
                pick_id="line", z=1)
    unpickable = Prim(kind="box", cx_m=5.0, cy_m=-10.0, length_m=2.0, width_m=1.0, yaw_rad=0.0,
                       style="ego.body", z=0)  # no pick_id -- never a hit
    return Scene(layers=(Layer(id="sim.test", group="sim", prims=(box, circle, line, unpickable)),))


def test_hit_test_resolves_to_the_prim_actually_drawn_one_path_for_every_kind():
    """UT-B1-10: box, circle and polyline all resolve through the same
    `hit_test` call -- no per-kind hit-test function."""
    scene = _scene()
    vp = Viewport(size_px=(400, 400), scale_px_per_m=10.0, centre_m=(5.0, 0.0))

    assert hit_test(scene, vp, vp.to_px(5.0, -10.0)) == "box"
    assert hit_test(scene, vp, vp.to_px(10.0, 2.0)) == "circle"
    assert hit_test(scene, vp, vp.to_px(2.5, 2.5)) == "line"
    assert hit_test(scene, vp, vp.to_px(-50.0, -50.0)) is None


def test_hit_test_ignores_prims_with_no_pick_id():
    scene = Scene(layers=(Layer(id="sim.test", group="sim", prims=(
        Prim(kind="box", cx_m=0.0, cy_m=0.0, length_m=2.0, width_m=2.0, yaw_rad=0.0, style="ego.body"),
    )),))
    vp = Viewport(size_px=(400, 400), scale_px_per_m=10.0)
    assert hit_test(scene, vp, vp.to_px(0.0, 0.0)) is None


def test_scene_bounds_m_unions_every_visible_prims_bounds():
    scene = Scene(layers=(Layer(id="sim.test", group="sim", prims=(
        Prim(kind="box", cx_m=0.0, cy_m=0.0, length_m=2.0, width_m=2.0, yaw_rad=0.0, style="ego.body"),
        Prim(kind="circle", cx_m=10.0, cy_m=-5.0, r_m=1.0, style="sensor.range_ring"),
    )),))
    assert scene_bounds_m(scene) == (-1.0, -6.0, 11.0, 1.0)


def test_scene_bounds_m_is_none_for_an_empty_scene():
    assert scene_bounds_m(Scene(layers=())) is None


def test_scene_bounds_m_respects_layer_selection():
    scene = Scene(layers=(
        Layer(id="sim.a", group="sim", prims=(
            Prim(kind="box", cx_m=0.0, cy_m=0.0, length_m=2.0, width_m=2.0, yaw_rad=0.0, style="ego.body"),
        )),
        Layer(id="sim.b", group="sim", prims=(
            Prim(kind="circle", cx_m=100.0, cy_m=100.0, r_m=1.0, style="sensor.range_ring"),
        )),
    ))
    assert scene_bounds_m(scene, frozenset({"sim.a"})) == (-1.0, -1.0, 1.0, 1.0)


def test_anchor_points_m_returns_corners_and_centre_for_a_pickable_prim():
    scene = Scene(layers=(Layer(id="sim.test", group="sim", prims=(
        Prim(kind="box", cx_m=5.0, cy_m=0.0, length_m=2.0, width_m=2.0, yaw_rad=0.0,
             style="ego.body", pick_id="box"),
    )),))
    anchors = anchor_points_m(scene)
    assert set(anchors) == {(4.0, -1.0), (4.0, 1.0), (6.0, -1.0), (6.0, 1.0), (5.0, 0.0)}


def test_anchor_points_m_ignores_prims_with_no_pick_id():
    scene = Scene(layers=(Layer(id="sim.test", group="sim", prims=(
        Prim(kind="box", cx_m=0.0, cy_m=0.0, length_m=2.0, width_m=2.0, yaw_rad=0.0, style="ego.body"),
    )),))
    assert anchor_points_m(scene) == ()


def test_render_scene_draws_overlay_prims_on_top():
    scene = Scene(layers=())
    vp = Viewport(size_px=(200, 200), scale_px_per_m=10.0)
    blank = render_scene(scene, vp, "dark")
    with_overlay = render_scene(scene, vp, "dark", overlay_prims=(
        Prim(kind="polyline", points_m=((0.0, 0.0), (5.0, 5.0)), style="measure.ruler"),
    ))
    assert not np.array_equal(blank, with_overlay)


def test_render_scene_draws_hud_lines():
    scene = Scene(layers=())
    vp = Viewport(size_px=(200, 200), scale_px_per_m=10.0)
    blank = render_scene(scene, vp, "dark")
    with_hud = render_scene(scene, vp, "dark", hud_lines=("scale 10.0 px/m", "t = 1.00s"))
    assert not np.array_equal(blank, with_hud)


def test_render_scene_draws_a_stale_banner():
    scene = Scene(layers=())
    vp = Viewport(size_px=(200, 200), scale_px_per_m=10.0)
    blank = render_scene(scene, vp, "dark")
    with_banner = render_scene(scene, vp, "dark", stale_banner="STALE: a, b")
    assert not np.array_equal(blank, with_banner)


def test_render_scene_hud_lines_stay_fixed_regardless_of_viewport_pan():
    """Screen-space, not world-space: the same HUD text at two different
    viewport centres (a pan) renders identically -- unlike a Prim, which
    would move."""
    scene = Scene(layers=())
    vp_a = Viewport(size_px=(200, 200), scale_px_per_m=10.0, centre_m=(0.0, 0.0))
    vp_b = Viewport(size_px=(200, 200), scale_px_per_m=10.0, centre_m=(50.0, 50.0))
    frame_a = render_scene(scene, vp_a, "dark", hud_lines=("fixed text",))
    frame_b = render_scene(scene, vp_b, "dark", hud_lines=("fixed text",))
    assert np.array_equal(frame_a, frame_b)
