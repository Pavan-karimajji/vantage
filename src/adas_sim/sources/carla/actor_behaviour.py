# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Declarative per-tick actor behaviour for the CARLA source (`S-C2` slice
5). Ported from `modules/df/tools/carla/{actor_behaviour,carla_bridge}.py`,
merged into one module since both are engine machinery over the same actor
state -- verbatim in behaviour, not a rewrite (`R-STYLE-2`). Component-
agnostic already: nothing here names a driving function.

## Lateral profile

An actor declares an ordered phase list; the source asks for a rate each
tick and displaces the actor perpendicular to its heading by `rate * dt`.

    actors:
      - name: target
        lateral_offset_m: -6.0
        lateral_profile:
          - { name: converge, rate_mps: +0.25, duration_s: 8.0 }
          - { name: hold,     rate_mps:  0.0,  duration_s: 2.0 }
          - { name: diverge,  rate_mps: -0.25, duration_s: 10.0 }

A phase may also declare `shape: raised_cosine`, which ramps the rate as
`rate_mps * (1 - cos(2*pi*progress)) / 2` instead of holding it constant --
zero lateral acceleration except at phase edges (a constant-rate slide)
produces no yaw rate and therefore no curvature for a rear-safety function
to warp on, so a raised-cosine phase is what makes that class of scenario
possible at all. The raised cosine gives

    lateral velocity  0 -> peak -> 0        (smooth, no step)
    lateral accel     a full-period sine
    displacement      rate_mps * duration_s / 2

`rate_mps` is **signed in the project convention: +y is left** (`R-COORD-1`).
It is deliberately not expressed as "converge/diverge with an inferred
sign": inferring inward from the sign of `lateral_offset_m` works for a
target on the ego's right and silently inverts for one on its left, and is
undefined for a target starting at `lateral_offset_m: 0`. `name` is free
text used only in the log line.

After the last phase the rate is 0.0, so a profile shorter than the
scenario's own duration simply stops moving laterally.
"""

from __future__ import annotations

import math


class LateralProfile:
    """An ordered list of (rate, duration) phases, sampled by elapsed time."""

    def __init__(self, phases: list, actor_name: str = ""):
        if not isinstance(phases, list) or not phases:
            raise ValueError(
                f"lateral_profile for actor {actor_name!r} must be a non-empty list of phases")
        self.phases = []
        for index, phase in enumerate(phases):
            if "rate_mps" not in phase or "duration_s" not in phase:
                raise ValueError(
                    f"lateral_profile phase {index} for actor {actor_name!r} needs both "
                    f"'rate_mps' and 'duration_s', got {sorted(phase)}")
            shape = str(phase.get("shape", "const"))
            if shape not in ("const", "raised_cosine"):
                raise ValueError(
                    f"lateral_profile phase {index} for actor {actor_name!r}: unknown "
                    f"shape {shape!r}, expected 'const' or 'raised_cosine'")
            self.phases.append((str(phase.get("name", f"phase{index}")),
                                float(phase["rate_mps"]), float(phase["duration_s"]), shape))
        self.actor_name = actor_name

    def _sample(self, elapsed_s: float) -> tuple:
        remaining = elapsed_s
        for name, rate, duration, shape in self.phases:
            if remaining < duration:
                if shape == "raised_cosine" and duration > 0.0:
                    progress = remaining / duration
                    rate *= (1.0 - math.cos(2.0 * math.pi * progress)) / 2.0
                return name, rate
            remaining -= duration
        return "done", 0.0

    def rate_mps(self, elapsed_s: float) -> float:
        return self._sample(elapsed_s)[1]

    def phase_name(self, elapsed_s: float) -> str:
        return self._sample(elapsed_s)[0]


def build_lateral_profiles(actor_cfgs: list) -> dict:
    """{actor name: LateralProfile} for the actors that declare one. Actors
    without a `lateral_profile:` are absent from the dict, so a flat-YAML
    scenario builds nothing and behaves exactly as before."""
    profiles = {}
    for cfg in actor_cfgs:
        phases = cfg.get("lateral_profile")
        if phases:
            profiles[cfg["name"]] = LateralProfile(phases, cfg["name"])
    return profiles


def lateral_rates(profiles: dict, actor_cfgs: list, elapsed_s: float) -> dict:
    """Per-actor lateral rate for this tick -- 0.0 for every actor that has
    no profile, so the displacement path stays inert by default."""
    return {cfg["name"]: (profiles[cfg["name"]].rate_mps(elapsed_s)
                          if cfg["name"] in profiles else 0.0)
            for cfg in actor_cfgs}


def status_str(profiles: dict, elapsed_s: float) -> str:
    """Compact phase readout for a diagnostics log line."""
    if not profiles:
        return ""
    return " " + " ".join(
        f"{name}:{profile.phase_name(elapsed_s)}({profile.rate_mps(elapsed_s):+.2f})"
        for name, profile in profiles.items())


def _angle_diff_deg(new_deg: float, old_deg: float) -> float:
    """Signed shortest-path difference new-old, wrapped to (-180, 180] -- a
    plain subtraction breaks across the +/-180 degree seam CARLA's yaw uses."""
    return (new_deg - old_deg + 180.0) % 360.0 - 180.0


def _lateral_world_offset(yaw_deg: float, lateral_offset_m: float) -> tuple:
    """World-frame (dx, dy) that shifts a point sideways by `lateral_offset_m`
    in OUR +y-left convention (`R-COORD-1`), given a CARLA yaw in degrees."""
    yaw_rad = math.radians(yaw_deg)
    right = (-math.sin(yaw_rad), math.cos(yaw_rad))
    return (-right[0] * lateral_offset_m, -right[1] * lateral_offset_m)


def velocity_world(yaw_deg: float, speed_mps: float, lateral_rate_mps: float = 0.0) -> tuple:
    """World-frame velocity of an actor travelling `speed_mps` along its
    heading and `lateral_rate_mps` sideways in OUR +y-left convention. The
    lateral term must match `LaneAdvancer.advance`'s own displacement
    exactly, or the reported relative velocity and the actor's real motion
    disagree."""
    yaw_rad = math.radians(yaw_deg)
    forward = (math.cos(yaw_rad), math.sin(yaw_rad))
    left = (math.sin(yaw_rad), -math.cos(yaw_rad))   # = -right, see _lateral_world_offset
    return (speed_mps * forward[0] + lateral_rate_mps * left[0],
            speed_mps * forward[1] + lateral_rate_mps * left[1])


class LaneAdvancer:
    """Moves actors forward along their road lane.

    Two live-found bugs ruled out the two more obvious implementations:
    - A fixed-heading straight-line teleport drifts off a curving road and
      diverges from a stationary target instead of closing on it.
    - Calling `waypoint.next(distance)` every tick with the small per-tick
      distance (`speed_mps * dt_s`) does NOT move the actor exactly that
      far: it rounds up to the next *sampled* waypoint along the lane, and
      that per-call overshoot is roughly a fixed absolute amount, not
      proportional to the requested distance -- confirmed live: even with
      correct real-time pacing, the measured closing speed against a live
      server was consistently ~1.5-1.7x the configured `speed_mps`.

    Fix: position is advanced analytically (`distance * cos/sin(heading)`,
    exact, no snapping possible) every tick. `get_waypoint(location)` -- a
    nearest-point lookup, a different and much more precise operation than
    `.next(distance)`'s along-lane traversal -- is used only every
    `REFRESH_DISTANCE_M` to re-derive the target heading, correcting for
    road curvature before it can accumulate into meaningful drift.

    Heading-jerk fix: the newly-sampled target heading is NOT applied to
    the actor in one instant snap (a real, visible steering pop, confirmed
    live). Instead the applied heading ramps toward the target linearly,
    one tick at a time, converging on it by the next refresh. The reported
    yaw_rate (true average rate over the interval) is unchanged by this --
    only how the heading is applied between samples.
    """

    REFRESH_DISTANCE_M = 2.0

    def __init__(self):
        self._heading_deg = {}              # actor.id -> target heading from the last refresh (degrees)
        self._current_heading_deg = {}      # actor.id -> heading actually applied this tick (ramping toward target)
        self._ramp_rate_deg_s = {}          # actor.id -> CARLA-sign deg/s to ramp _current_heading_deg at
        self._distance_since_refresh = {}   # actor.id -> meters traveled since last heading refresh
        self._time_since_heading_change = {}  # actor.id -> seconds accumulated since heading last changed
        self._yaw_rate_deg_s = {}           # actor.id -> average yaw rate over the last refresh interval
        self._profile_heading_rad = {}      # actor.id -> heading offset from a lateral profile (our sign)
        self._profile_yaw_rate_rad_s = {}   # actor.id -> its time derivative, the steered yaw rate

    def advance(self, world, actor, speed_mps: float, dt_s: float,
                lateral_rate_mps: float = 0.0, yaw_with_lateral: bool = False) -> None:
        """`lateral_rate_mps` displaces the actor perpendicular to its own
        heading each tick, in OUR +y-left convention -- a genuine lateral
        velocity. It defaults to 0.0, so every caller that ignores it is
        unchanged.

        The rate must also reach `velocity_world()`, or the reported
        relative lateral velocity would stay ~0 while the actor visibly
        slides sideways.

        `world`/`actor` are CARLA types (`carla.World`/`carla.Actor`),
        accepted untyped here so this class stays testable against a
        duck-typed fake (`UT-C2-2`) with no `carla` package installed."""
        if speed_mps == 0.0 and lateral_rate_mps == 0.0:
            return
        step_m = speed_mps * dt_s
        self._time_since_heading_change[actor.id] = (
            self._time_since_heading_change.get(actor.id, 0.0) + dt_s)

        distance_since = self._distance_since_refresh.get(actor.id, math.inf)
        if distance_since >= self.REFRESH_DISTANCE_M:
            waypoint = world.get_map().get_waypoint(actor.get_location())
            new_heading_deg = waypoint.transform.rotation.yaw
            old_heading_deg = self._heading_deg.get(actor.id)
            elapsed_s = self._time_since_heading_change[actor.id]
            if old_heading_deg is not None and elapsed_s > 0.0:
                # Averaged over the time it took to travel REFRESH_DISTANCE_M,
                # not the single tick the refresh happened on -- heading is
                # genuinely piecewise-constant between refreshes, so this IS
                # the true average angular rate over that interval.
                carla_sign_rate_deg_s = _angle_diff_deg(new_heading_deg, old_heading_deg) / elapsed_s
                # Negated: CARLA's raw yaw is left-handed (+y = right), so a
                # positive CARLA heading delta is a rightward turn -- the
                # opposite of our +y-left convention. Same right-to-left
                # flip frame_convert.py applies to position/velocity.
                self._yaw_rate_deg_s[actor.id] = -carla_sign_rate_deg_s
                self._ramp_rate_deg_s[actor.id] = carla_sign_rate_deg_s
            self._heading_deg[actor.id] = new_heading_deg
            self._time_since_heading_change[actor.id] = 0.0
            distance_since = 0.0
            if actor.id not in self._current_heading_deg:
                self._current_heading_deg[actor.id] = new_heading_deg

        target_heading_deg = self._heading_deg[actor.id]
        heading_deg = self._current_heading_deg.get(actor.id, target_heading_deg)
        ramp_rate_deg_s = self._ramp_rate_deg_s.get(actor.id, 0.0)
        heading_deg += ramp_rate_deg_s * dt_s
        # Don't overshoot past the target between refreshes.
        remaining_deg = _angle_diff_deg(target_heading_deg, heading_deg)
        if remaining_deg * ramp_rate_deg_s < 0.0:
            heading_deg = target_heading_deg
        self._current_heading_deg[actor.id] = heading_deg

        transform = actor.get_transform()
        yaw_rad = math.radians(heading_deg)
        transform.location.x += step_m * math.cos(yaw_rad)
        transform.location.y += step_m * math.sin(yaw_rad)
        if lateral_rate_mps != 0.0:
            dx, dy = _lateral_world_offset(heading_deg, lateral_rate_mps * dt_s)
            transform.location.x += dx
            transform.location.y += dy

        # By default the heading stays the lane heading even while sliding
        # sideways: rotating a target would rotate its footprint too,
        # changing the very lateral extent a u-axis entry test measures.
        #
        # yaw_with_lateral=True is for the EGO: a lane change is steered, so
        # it carries a real heading offset atan2(v_lat, v_x) and hence a
        # real yaw rate -- and yaw_rate is the ONLY route by which the
        # ego's own manoeuvre reaches a rear-safety function (it is what
        # determines the curvature such a function warps its zone by).
        # Slide the ego without yawing it and a spurious-warp scenario
        # silently measures nothing at all.
        profile_heading_rad = 0.0
        if yaw_with_lateral and speed_mps != 0.0:
            profile_heading_rad = math.atan2(lateral_rate_mps, speed_mps)
        previous_rad = self._profile_heading_rad.get(actor.id, 0.0)
        self._profile_yaw_rate_rad_s[actor.id] = (
            (profile_heading_rad - previous_rad) / dt_s if dt_s > 0.0 else 0.0)
        self._profile_heading_rad[actor.id] = profile_heading_rad
        # Negated into CARLA's left-handed yaw, same flip as everywhere else.
        transform.rotation.yaw = heading_deg - math.degrees(profile_heading_rad)
        actor.set_transform(transform)

        self._distance_since_refresh[actor.id] = distance_since + abs(step_m)

    def yaw_rate_rad_s(self, actor_id: int) -> float:
        """Ground-truth average yaw rate over the actor's most recent
        heading-refresh interval (0.0 before its first refresh), in our
        +y-left sign convention (positive = turning left) -- already
        flipped from CARLA's raw left-handed heading.

        Includes the steered component from a `yaw_with_lateral` lateral
        profile: road curvature and the ego's own lane change both show up
        in yaw_rate on a real vehicle, and a rear-safety function cannot
        tell them apart."""
        return (math.radians(self._yaw_rate_deg_s.get(actor_id, 0.0))
                + self._profile_yaw_rate_rad_s.get(actor_id, 0.0))
