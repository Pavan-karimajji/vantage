# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Chase-view spectator camera (`S-C2` slice 5). Ported from
`modules/df/tools/carla/carla_bridge.py`, verbatim in behaviour -- shared by
a live viewport and a recorded chase-view video feed, same view, two
consumers. `carla` is imported inside the function (see `world.py`'s own
docstring)."""

from __future__ import annotations

import math


def compute_chase_transform(ego_actor, focus_actor=None):
    """Close behind/above ego (ego's own perspective, not an aerial/drone
    shot), aimed toward the midpoint between ego and `focus_actor` rather
    than purely along ego's heading, so the focus actor stays framed too
    even from this close position. Fixed, modest offset -- does not scale
    with the gap.

    `focus_actor=None` frames ego alone, looking along its own heading --
    the single-vehicle case a multi-actor scenario's chase view falls back
    to."""
    import carla

    ego_t = ego_actor.get_transform()
    ego_loc = ego_t.location

    yaw_rad = math.radians(ego_t.rotation.yaw)
    back_off_m = 7.0
    height_m = 3.0
    camera_loc = carla.Location(
        x=ego_loc.x - back_off_m * math.cos(yaw_rad),
        y=ego_loc.y - back_off_m * math.sin(yaw_rad),
        z=ego_loc.z + height_m,
    )

    if focus_actor is not None:
        focus_loc = focus_actor.get_transform().location
        target = carla.Location(
            x=(ego_loc.x + focus_loc.x) / 2.0,
            y=(ego_loc.y + focus_loc.y) / 2.0,
            z=(ego_loc.z + focus_loc.z) / 2.0,
        )
    else:
        target = carla.Location(
            x=ego_loc.x + math.cos(yaw_rad), y=ego_loc.y + math.sin(yaw_rad), z=ego_loc.z)

    dx, dy, dz = target.x - camera_loc.x, target.y - camera_loc.y, target.z - camera_loc.z
    horizontal_dist = math.hypot(dx, dy)
    look_yaw = math.degrees(math.atan2(dy, dx))
    look_pitch = math.degrees(math.atan2(dz, horizontal_dist))

    return carla.Transform(camera_loc, carla.Rotation(pitch=look_pitch, yaw=look_yaw))


def follow_with_spectator(world, ego_actor, focus_actor=None) -> None:
    world.get_spectator().set_transform(compute_chase_transform(ego_actor, focus_actor))
