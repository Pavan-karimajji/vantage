# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Actor spawning (`S-C2` slice 5). Ported from
`modules/df/tools/carla/carla_bridge.py`, verbatim in behaviour. `carla` is
imported inside each function (see `world.py`'s own docstring)."""

from __future__ import annotations

from adas_sim.sources.carla.actor_behaviour import _lateral_world_offset


def spawn_kinematic_ego(world, cfg: dict):
    """Spawns at a real map spawn point, snapped to the lane centerline --
    arbitrary hand-picked coordinates aren't guaranteed to be on the road
    network or collision-free.

    Optional `spawn_offset_m` walks the ego spawn point along the road
    centerline via `waypoint.next()`/`.previous()` before snapping --
    negative moves upstream (behind), same convention as
    `spawn_kinematic_at`'s `long_offset_m` for actors."""
    blueprint = world.get_blueprint_library().find(cfg["blueprint"])
    spawn_points = world.get_map().get_spawn_points()
    transform = spawn_points[cfg.get("spawn_point_index", 0)]
    waypoint = world.get_map().get_waypoint(transform.location)
    offset_m = cfg.get("spawn_offset_m", 0.0)
    if offset_m > 0.0:
        candidates = waypoint.next(offset_m)
        if not candidates:
            raise RuntimeError(f"No road waypoint {offset_m}m ahead of ego spawn point.")
        waypoint = candidates[0]
    elif offset_m < 0.0:
        candidates = waypoint.previous(-offset_m)
        if not candidates:
            raise RuntimeError(f"No road waypoint {-offset_m}m behind ego spawn point.")
        waypoint = candidates[0]
    transform = waypoint.transform
    # Small clearance to avoid a spawn-time collision with the road mesh --
    # NOT 0.5m: these actors are kinematic (physics disabled, no gravity),
    # so whatever height they spawn at is what they visually stay at
    # forever -- 0.5m looks like the vehicle floating.
    transform.location.z += 0.05
    actor = world.spawn_actor(blueprint, transform)
    actor.set_simulate_physics(False)
    return actor


def spawn_kinematic_at(world, ego, blueprint_id: str, long_offset_m: float, lateral_offset_m: float, speed_mps: float):
    """Spawns an actor `long_offset_m` ahead (negative = behind) of `ego`
    along the road centerline, then shifted `lateral_offset_m` sideways in
    OUR +y-left convention -- generalises a lead-only spawn to place an
    actor anywhere in the zone. `waypoint.next()`/`.previous()` guarantee
    the base point faces the same lane direction as the road; the lateral
    shift is applied in that point's own heading (not ego's original one),
    so it stays road-aligned through a curve. `speed_mps` isn't needed to
    spawn (the actor is teleported every tick by `LaneAdvancer`); kept in
    the signature for parity with the original."""
    blueprint = world.get_blueprint_library().find(blueprint_id)
    ego_waypoint = world.get_map().get_waypoint(ego.get_location())
    if long_offset_m > 0.0:
        candidates = ego_waypoint.next(long_offset_m)
    elif long_offset_m < 0.0:
        candidates = ego_waypoint.previous(-long_offset_m)
    else:
        candidates = [ego_waypoint]
    if not candidates:
        raise RuntimeError(f"No road waypoint {long_offset_m}m from ego spawn point.")
    transform = candidates[0].transform
    dx, dy = _lateral_world_offset(transform.rotation.yaw, lateral_offset_m)
    transform.location.x += dx
    transform.location.y += dy
    transform.location.z += 0.05  # see spawn_kinematic_ego's comment
    actor = world.try_spawn_actor(blueprint, transform)
    if actor is None:
        raise RuntimeError(
            f"Could not spawn '{blueprint_id}' at long_offset={long_offset_m}m, "
            f"lateral_offset={lateral_offset_m}m -- spawn point blocked.")
    actor.set_simulate_physics(False)
    return actor


def spawn_kinematic_ahead(world, ego, cfg: dict):
    """Thin alias -- the old lead-only call shape, straight ahead."""
    return spawn_kinematic_at(world, ego, cfg["blueprint"], cfg["initial_gap_m"], 0.0, cfg["speed_mps"])
