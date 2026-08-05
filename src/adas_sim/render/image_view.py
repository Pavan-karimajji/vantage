# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Projects `Scene` prims onto a camera frame (`S-D4`, `sim_visualization_spec.md`
§11.4): "a `Box` with a `height` becomes a projected 3D box; a `Polyline`
becomes a projected polyline. Because it is the same prim the BEV drew, the
two views cannot disagree."

**Coordinates, stated explicitly (`N-4`).** Ego frame is `R-COORD-1`: origin
at the rear axle, `+x` forward, `+y` left, `+z` up (right-handed). A
`CameraModel`'s pose/orientation (`model/cameras.py`) places the camera IN
that frame. Internally this module converts into the standard computer-
vision camera frame (`+x` right, `+y` down, `+z` forward, into the scene)
only for the pinhole step -- never exposed outside this module. Every
metre-valued input keeps its `_m` suffix; every pixel-valued output is a
field on `ProjectedPoint`, itself suffixed `_px` -- **a pixel and a metre
never share a bare name** (`UT-D4-3`, the defect `N-4` exists for).

**Must not** (this stage's own words): let the downstream component learn
where its input came from -- irrelevant here (this module only ever reads a
`Prim`'s own declared geometry, never a stage's `mode`/`impl`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from adas_sim.model.cameras import CameraModel
from adas_sim.scene.types import Prim


@dataclass(frozen=True, slots=True)
class ProjectedPoint:
    """One ego-frame metre point, projected into `camera`'s image plane.
    `None` fields (via `project_point` returning `None` entirely) mean
    behind the camera -- there is no "negative depth" pixel to report."""

    u_px: float
    v_px: float
    depth_m: float

    def __repr__(self) -> str:
        return f"<ProjectedPoint u_px={self.u_px:.1f} v_px={self.v_px:.1f} depth_m={self.depth_m:.2f}>"


def _orientation_matrix(camera: CameraModel) -> np.ndarray:
    """The camera's orientation IN ego-style axes (still `+x` forward,
    `+y` left, `+z` up locally) -- intrinsic yaw (about ego `+z`) then pitch
    (about the once-yawed `+y`) then roll (about the twice-rotated `+x`),
    a standard aerospace ZYX composition. Chosen for internal consistency
    (`project_point`/`unproject_pixel` invert exactly, `UT-D4-1`) -- no
    external reference this needs to match, since nothing outside this
    module ever sees these intermediate axes."""
    yaw = math.radians(camera.pose_yaw_deg)
    pitch = math.radians(camera.pose_pitch_deg)
    roll = math.radians(camera.pose_roll_deg)
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cr, sr = math.cos(roll), math.sin(roll)
    r_yaw = np.array([[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]])
    r_pitch = np.array([[cp, 0.0, sp], [0.0, 1.0, 0.0], [-sp, 0.0, cp]])
    r_roll = np.array([[1.0, 0.0, 0.0], [0.0, cr, -sr], [0.0, sr, cr]])
    return r_yaw @ r_pitch @ r_roll


def project_point(camera: CameraModel, x_m: float, y_m: float, z_m: float) -> ProjectedPoint | None:
    """One ego-frame metre point -> `camera`'s pixel plane. `None` when the
    point is behind the camera (`depth <= 0` in the camera's own forward
    axis) -- there is no meaningful pixel for that, never a fabricated one
    (`NR-SIM-4`)."""
    rotation = _orientation_matrix(camera)
    ego_point = np.array([x_m - camera.pose_x_m, y_m - camera.pose_y_m, z_m - camera.pose_z_m])
    local = rotation.T @ ego_point  # ego-style axes, camera-local origin

    # ego-style (x-forward, y-left, z-up) -> CV camera axes (x-right, y-down, z-forward)
    x_cv = -local[1]
    y_cv = -local[2]
    z_cv = local[0]
    if z_cv <= 0.0:
        return None

    u_px = camera.focal_length_x_px * (x_cv / z_cv) + camera.principal_point_x_px
    v_px = camera.focal_length_y_px * (y_cv / z_cv) + camera.principal_point_y_px
    return ProjectedPoint(u_px=u_px, v_px=v_px, depth_m=z_cv)


def unproject_pixel(camera: CameraModel, u_px: float, v_px: float, depth_m: float) -> tuple[float, float, float]:
    """The exact inverse of `project_point` -- given a pixel and its known
    depth, the ego-frame metre point that projects there (`UT-D4-1`'s own
    round-trip). Needs `depth_m` because a single pixel alone is a ray, not
    a point -- the same reason any monocular projection is lossy without an
    independently-known depth."""
    x_cv = (u_px - camera.principal_point_x_px) * depth_m / camera.focal_length_x_px
    y_cv = (v_px - camera.principal_point_y_px) * depth_m / camera.focal_length_y_px
    z_cv = depth_m

    local = np.array([z_cv, -x_cv, -y_cv])  # CV camera axes -> ego-style axes
    rotation = _orientation_matrix(camera)
    ego_point = rotation @ local + np.array([camera.pose_x_m, camera.pose_y_m, camera.pose_z_m])
    return float(ego_point[0]), float(ego_point[1]), float(ego_point[2])


def _box_corners_m(prim: Prim) -> list[tuple[float, float, float]]:
    """The 8 corners of a `kind="box"` `Prim`'s own declared geometry --
    ground-based (`z` in `[0, height_m]`, `Prim` carries no `cz_m`), centred
    at `(cx_m, cy_m)`, rotated by `yaw_rad` about ego `+z`. The SAME fields
    `render/bev.py` already draws from -- this function invents no new
    geometry, only reads what the `Prim` already declares (`UT-D4-2`)."""
    cx, cy = prim.cx_m or 0.0, prim.cy_m or 0.0
    half_length, half_width = (prim.length_m or 0.0) / 2.0, (prim.width_m or 0.0) / 2.0
    height = prim.height_m or 0.0
    yaw = prim.yaw_rad or 0.0
    cos_yaw, sin_yaw = math.cos(yaw), math.sin(yaw)

    corners = []
    for dx in (-half_length, half_length):
        for dy in (-half_width, half_width):
            for dz in (0.0, height):
                x = cx + dx * cos_yaw - dy * sin_yaw
                y = cy + dx * sin_yaw + dy * cos_yaw
                corners.append((x, y, dz))
    return corners


def project_box(camera: CameraModel, prim: Prim) -> list[ProjectedPoint | None]:
    """The 8 projected corners of a `kind="box"` `Prim`, in `_box_corners_m`'s
    own order -- `None` entries mark a corner behind the camera (never
    dropped silently, so a caller can tell "partially behind" from "fully
    visible"). Raises if `prim.kind != "box"`, naming what was given
    (`N-8`) -- this function has nothing to project for any other kind."""
    if prim.kind != "box":
        raise ValueError(f"project_box expects a 'box' Prim, found kind={prim.kind!r}")
    return [project_point(camera, x, y, z) for x, y, z in _box_corners_m(prim)]
