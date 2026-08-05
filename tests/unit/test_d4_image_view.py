# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D4 `render/image_view.py` tests (`docs/sim_implementation_plan.md`):
`UT-D4-1` (projection round-trips for a known intrinsic/extrinsic pair),
`UT-D4-2` (a `Box` with `height` projects to a 3D box, from the SAME
`Prim` the BEV draws), `UT-D4-3` (a pixel-valued and a metre-valued field
never share a bare name), `UT-D4-4` (a perception-scale layer references
rather than inlines -- the S-A3/S-B2 mechanism, already tested, proven at
perception scale here).

`ST-D4-1`/`ST-D4-2` (the two-component pipeline invariant) stay correctly
un-attempted -- the stage's own "Gating" note says they need a second real
PERCEPTION component, which does not exist (`perception-core` has no real
Conan package, `R-SIL-2`); `vdy`'s existence does not change that, it is
not a perception component.
"""

from __future__ import annotations

import dataclasses
import sys

import pytest

from adas_sim.model.cameras import CameraModel
from adas_sim.render.image_view import ProjectedPoint, project_box, project_point, unproject_pixel
from adas_sim.scene.types import BulkRef, Layer, MAX_INLINE_PRIM_ELEMENTS, Prim, Scene
from adas_sim.core.errors import ContractError


def _camera(**overrides) -> CameraModel:
    defaults = dict(
        camera_id="front", pose_x_m=1.5, pose_y_m=0.3, pose_z_m=1.4,
        pose_yaw_deg=15.0, pose_pitch_deg=-5.0, pose_roll_deg=2.0,
        focal_length_x_px=900.0, focal_length_y_px=850.0,
        principal_point_x_px=640.0, principal_point_y_px=360.0,
        image_width_px=1280, image_height_px=720,
    )
    defaults.update(overrides)
    return CameraModel(**defaults)


def test_projection_round_trips_for_a_known_intrinsic_extrinsic_pair():
    """UT-D4-1."""
    camera = _camera()
    original = (12.3, -2.1, 0.8)
    projected = project_point(camera, *original)
    assert projected is not None

    recovered = unproject_pixel(camera, projected.u_px, projected.v_px, projected.depth_m)
    assert recovered == pytest.approx(original, abs=1e-9)


def test_a_point_straight_ahead_at_camera_height_lands_at_the_principal_point():
    """A sanity check independent of the round-trip identity: a point
    directly ahead of an unrotated camera, at the camera's own height,
    projects to exactly (principal_point_x_px, principal_point_y_px)."""
    camera = _camera(
        pose_x_m=2.0, pose_y_m=0.0, pose_z_m=1.2, pose_yaw_deg=0.0, pose_pitch_deg=0.0, pose_roll_deg=0.0,
    )
    projected = project_point(camera, 10.0, 0.0, 1.2)
    assert projected == pytest.approx(ProjectedPoint(u_px=640.0, v_px=360.0, depth_m=8.0), abs=1e-9)


def test_a_point_behind_the_camera_returns_none_never_a_fabricated_pixel():
    camera = _camera(pose_x_m=2.0, pose_y_m=0.0, pose_z_m=1.2, pose_yaw_deg=0.0, pose_pitch_deg=0.0, pose_roll_deg=0.0)
    assert project_point(camera, -5.0, 0.0, 1.2) is None


def test_a_box_with_height_projects_to_eight_corners_from_the_same_prim():
    """UT-D4-2. The `Prim` passed in is exactly the one `render/bev.py`
    would draw in the top-down view -- no second geometry is derived."""
    camera = _camera(pose_x_m=0.0, pose_y_m=0.0, pose_z_m=1.5, pose_yaw_deg=0.0, pose_pitch_deg=0.0, pose_roll_deg=0.0)
    box = Prim(kind="box", cx_m=10.0, cy_m=0.0, length_m=4.5, width_m=1.8, yaw_rad=0.0, height_m=1.5, style="object.default")

    corners = project_box(camera, box)

    assert len(corners) == 8
    assert all(corner is not None for corner in corners)
    # All eight corners of a box 10 m ahead, well within the image, must be
    # distinct pixels -- proves this isn't accidentally projecting one
    # degenerate point eight times.
    unique_pixels = {(round(c.u_px, 3), round(c.v_px, 3)) for c in corners}
    assert len(unique_pixels) == 8


def test_project_box_refuses_a_non_box_prim_naming_the_kind():
    camera = _camera()
    text_prim = Prim(kind="text", x_m=0.0, y_m=0.0, text="hi", style="object.label")
    with pytest.raises(ValueError, match="text"):
        project_box(camera, text_prim)


def test_pixel_and_metre_fields_never_share_a_bare_name():
    """UT-D4-3. Structural, not a runtime behaviour: `ProjectedPoint`'s own
    fields are `_px`/`_m` suffixed, and none of them bare-collides with
    `CameraModel`'s or `Prim`'s own metre-valued field names."""
    projected_fields = {f.name for f in dataclasses.fields(ProjectedPoint)}
    assert projected_fields == {"u_px", "v_px", "depth_m"}
    for name in projected_fields:
        assert name.endswith("_px") or name.endswith("_m"), name

    camera_metre_fields = {
        f.name for f in dataclasses.fields(CameraModel) if f.name.endswith("_m")
    }
    # No bare stem (the part before the unit suffix) is shared between a
    # _px field and a _m field -- "depth" vs "pose_x" etc. never collide,
    # and if a future field ever did, this catches it here rather than in
    # a viewer silently mixing pixels and metres in one plot.
    pixel_stems = {name.removesuffix("_px") for name in projected_fields if name.endswith("_px")}
    metre_stems = {name.removesuffix("_m") for name in camera_metre_fields}
    assert pixel_stems.isdisjoint(metre_stems)


def test_perception_scale_layer_references_a_100000_point_cloud_instead_of_inlining(monkeypatch):
    """UT-D4-4: the S-A3 budget mechanism (`Layer.__post_init__`,
    `MAX_INLINE_PRIM_ELEMENTS`), already tested at unit scale in
    test_a3_types.py, proven here at the perception scale the rule exists
    for -- a 100,000-point cloud MUST be referenced via BulkRef, never
    inlined, and the resulting Scene stays a few hundred bytes regardless."""
    huge_point_count = 100_000
    assert huge_point_count > MAX_INLINE_PRIM_ELEMENTS  # the claim only means something if this holds

    bulk_prim = Prim(
        kind="points", style="object.default",
        bulk=BulkRef(topic="perception.detections", log_time_ns=1_000_000, field="points_m", count=huge_point_count),
    )
    layer = Layer(id="perception.cloud", group="perception", prims=(bulk_prim,))
    scene = Scene(layers=(layer,))
    assert scene.layers[0].prims[0].points_m is None  # never inlined
    assert scene.layers[0].prims[0].bulk.count == huge_point_count

    # An inlined attempt at the same scale is refused, naming the count
    # (mirrors test_a3_types.py's own assertion, at this stage's own scale).
    with pytest.raises(ContractError):
        Layer(
            id="perception.cloud.bad", group="perception",
            prims=(Prim(kind="points", points_m=tuple((float(i), 0.0) for i in range(huge_point_count)), style="object.default"),),
        )

    # The Scene object itself stays tiny -- a BulkRef is a handful of
    # scalars, not 100,000 point copies (NR-SIM-43's own "small geometry
    # only" claim, checked as an actual byte figure here).
    assert sys.getsizeof(scene) + sys.getsizeof(layer) + sys.getsizeof(bulk_prim) < 2000
