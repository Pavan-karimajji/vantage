# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B1 `render/bev.py` test: UT-B1-10 (docs/sim_implementation_plan.md)."""

from __future__ import annotations

from adas_sim.render.bev import hit_test
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
