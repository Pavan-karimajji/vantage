# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-A3 `scene/types.py` tests: UT-A3-1, UT-A3-3, UT-A3-11, UT-A3-12, UT-A3-13
(docs/sim_implementation_plan.md)."""

from __future__ import annotations

import dataclasses

import pytest

from adas_sim.diagnostics.errors import AuthoringError, ContractError
from adas_sim.scene.types import MAX_INLINE_PRIM_ELEMENTS, BulkRef, Layer, Prim, Scene

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


def test_layer_rejects_a_prim_exceeding_the_inline_budget():
    """UT-A3-12: a Prim inlining more than `MAX_INLINE_PRIM_ELEMENTS` is a
    `ContractError` naming the layer, the prim kind and the count
    (`NR-SIM-43`)."""
    too_many_points = tuple((float(i), 0.0) for i in range(MAX_INLINE_PRIM_ELEMENTS + 1))
    big_prim = Prim(kind="points", points_m=too_many_points, style="truth.trace")
    with pytest.raises(ContractError) as excinfo:
        Layer(id="sim.test.cloud", group="sim", prims=(big_prim,))
    err = excinfo.value
    assert "sim.test.cloud" in err.where
    assert "points" in err.found
    assert str(MAX_INLINE_PRIM_ELEMENTS + 1) in err.found


def test_layer_accepts_a_prim_referencing_bulk_data_instead_of_inlining_it():
    """UT-A3-12 (converse): a `BulkRef` is a coordinate into the recording,
    not a second copy of the payload, so it sidesteps the inline budget
    entirely -- this is what `NR-SIM-43` means by "referenced, not inlined"."""
    ref = BulkRef(topic="df/point_cloud", log_time_ns=123_000_000,
                  count=100_000, encoding="f32[3]")
    prim = Prim(kind="points", bulk=ref, style="truth.trace")
    layer = Layer(id="sim.test.cloud", group="sim", prims=(prim,))
    assert layer.prims[0].bulk == ref


def test_layer_with_derived_false_rejects_a_derived_prim():
    """UT-A3-13: a `Layer(derived=False)` may not contain a `Prim(derived=True)`
    (`OD-6`) -- stops a mixed layer claiming to be fully SUT-published."""
    prim = Prim(kind="polygon", points_m=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0)),
                style="object.ghost", derived=True)
    with pytest.raises(AuthoringError) as excinfo:
        Layer(id="sim.test.mixed", group="sim", prims=(prim,), derived=False)
    assert "sim.test.mixed" in excinfo.value.where


def test_layer_with_derived_true_may_legitimately_mix_real_and_derived_prims():
    """UT-A3-13 (converse): a layer legitimately mixes SUT-published and
    reconstructed geometry -- `Layer.derived=True` is exactly that case, and
    is not required to make every one of its prims `derived=True` too."""
    real_prim = Prim(kind="text", x_m=0.0, y_m=0.0, text="warning", style="status.warning")
    derived_prim = Prim(kind="polygon", points_m=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0)),
                         style="object.ghost", derived=True)
    layer = Layer(id="sim.test.mixed", group="sim", prims=(real_prim, derived_prim), derived=True)
    assert layer.prims[0].derived is False
    assert layer.prims[1].derived is True


def test_an_error_group_layer_must_be_derived():
    """`S-D4`'s ground_truth/perception/perception.error group convention,
    generalised to the `*.error` suffix rather than one literal string: an
    error group's own layer is always a reconstructed comparison between
    two separate sources, never a value any single port published
    (`R-SIM-7`) -- so `Layer(group="perception.error", derived=False)` is
    refused, not merely discouraged by naming."""
    with pytest.raises(AuthoringError) as excinfo:
        Layer(id="sim.test.perception_error", group="perception.error", derived=False)
    assert "perception.error" in str(excinfo.value)


def test_a_differently_named_error_group_layer_must_also_be_derived():
    """The rule is keyed to the `.error` suffix, not the literal
    `"perception.error"` string -- if `perception-core` splits into
    computer-vision + fusion (`FR-SIM-71`), the real error group becomes
    `"fusion.error"`, and the rule must not silently stop applying at
    exactly the moment the decomposition it exists to survive happens."""
    with pytest.raises(AuthoringError) as excinfo:
        Layer(id="sim.test.fusion_error", group="fusion.error", derived=False)
    assert "fusion.error" in str(excinfo.value)


def test_an_error_group_layer_marked_derived_is_accepted():
    """Converse of the above: the same group with `derived=True` is exactly
    the marked stopgap `R-SIM-7` asks for, and constructs without error."""
    layer = Layer(id="sim.test.perception_error", group="perception.error", derived=True)
    assert layer.group == "perception.error"
    assert layer.derived is True


def test_an_unrelated_group_is_not_forced_derived():
    """The rule fires for a `.error`-suffixed group specifically, not for
    every group -- an ordinary group (e.g. real ground-truth or perception
    output, which genuinely is a published value) stays `derived=False`
    freely."""
    for group in ("ground_truth", "perception", "sim"):
        layer = Layer(id=f"sim.test.{group}", group=group, derived=False)
        assert layer.derived is False
