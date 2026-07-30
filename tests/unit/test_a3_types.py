# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-A3 `scene/types.py` tests: UT-A3-1, UT-A3-3, UT-A3-11
(docs/sim_implementation_plan.md)."""

from __future__ import annotations

import dataclasses

import pytest

from adas_sim.core.errors import AuthoringError
from adas_sim.scene.types import Layer, Prim, Scene

#: One valid construction per catalogue kind (sim_visualization_spec.md §2).
ONE_PER_KIND: dict[str, Prim] = {
    "polyline": Prim(kind="polyline", points_m=((0.0, 0.0), (1.0, 1.0)), style="frame.grid"),
    "polygon": Prim(kind="polygon", points_m=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0)), style="sensor.blind"),
    "box": Prim(kind="box", cx_m=0.0, cy_m=0.0, length_m=4.5, width_m=1.8, yaw_rad=0.0, style="ego.body"),
    "circle": Prim(kind="circle", cx_m=0.0, cy_m=0.0, r_m=5.0, style="sensor.range_ring"),
    "ellipse": Prim(kind="ellipse", cx_m=0.0, cy_m=0.0, a_m=2.0, b_m=1.0, yaw_rad=0.0, style="object.ghost"),
    "points": Prim(kind="points", points_m=((1.0, 2.0),), marker="dot", style="truth.trace"),
    "arrow": Prim(kind="arrow", x_m=0.0, y_m=0.0, dx_m=1.0, dy_m=0.0, style="measure.annotation"),
    "text": Prim(kind="text", x_m=0.0, y_m=0.0, text="hello", style="object.label"),
    "grid": Prim(kind="grid", spacing_m=5.0, extent_m=50.0, style="frame.grid"),
    "heatmap": Prim(kind="heatmap", x0_m=0.0, y0_m=0.0, cell_dx_m=0.5, cell_dy_m=0.5,
                     values=((1.0, 2.0), (3.0, 4.0)), style="status.warning"),
    "image": Prim(kind="image", frame="image:cam0", data=b"\x00\x01", format="raw8", style="object.label"),
}


@pytest.mark.parametrize("kind", sorted(ONE_PER_KIND))
def test_every_prim_kind_constructs_and_is_immutable(kind):
    """UT-A3-1."""
    prim = ONE_PER_KIND[kind]
    assert prim.kind == kind
    with pytest.raises(dataclasses.FrozenInstanceError):
        prim.z = 99


def test_prim_with_no_frame_defaults_to_ego():
    """UT-A3-3."""
    prim = Prim(kind="circle", cx_m=0.0, cy_m=0.0, r_m=1.0)
    assert prim.frame == "ego"


def test_prim_with_unknown_frame_raises_naming_known_frames():
    """UT-A3-3."""
    with pytest.raises(AuthoringError) as excinfo:
        Prim(kind="circle", cx_m=0.0, cy_m=0.0, r_m=1.0, frame="nonsense")
    err = excinfo.value
    assert "ego" in err.expected and "world" in err.expected


def test_prim_with_hex_literal_style_raises():
    """UT-A3-11: no Prim field accepts a colour value -- a hex string is not
    a semantic token."""
    with pytest.raises(AuthoringError):
        Prim(kind="circle", cx_m=0.0, cy_m=0.0, r_m=1.0, style="#ff0000")


def test_prim_with_semantic_style_token_is_accepted():
    """UT-A3-11 (converse): a real dotted-namespace token is never mistaken
    for a colour."""
    prim = Prim(kind="circle", cx_m=0.0, cy_m=0.0, r_m=1.0, style="sensor.range_ring")
    assert prim.style == "sensor.range_ring"


def test_prim_fields_without_a_pick_id_raises():
    """S-B3 slice 5: `fields` with nothing to attach it to is dead data --
    the inspector resolves by `pick_id` (`sim_visualization_spec.md` §7.2)."""
    with pytest.raises(AuthoringError) as excinfo:
        Prim(kind="circle", cx_m=0.0, cy_m=0.0, r_m=1.0, style="object.label",
             fields=(("dist_x", "3.20 m"),))
    assert "pick_id" in excinfo.value.found


def test_prim_fields_with_a_pick_id_is_accepted():
    prim = Prim(kind="circle", cx_m=0.0, cy_m=0.0, r_m=1.0, style="object.label",
                pick_id="object.7", fields=(("dist_x", "3.20 m"), ("dist_y", "-1.10 m")))
    assert prim.fields == (("dist_x", "3.20 m"), ("dist_y", "-1.10 m"))


def test_layer_and_scene_are_immutable_dataclasses():
    layer = Layer(id="sim.test", group="sim", prims=(ONE_PER_KIND["box"],))
    with pytest.raises(dataclasses.FrozenInstanceError):
        layer.id = "other"
    scene = Scene(layers=(layer,))
    with pytest.raises(dataclasses.FrozenInstanceError):
        scene.t_s = 1.0
