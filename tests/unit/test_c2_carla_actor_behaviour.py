# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C2 slice 5: `UT-C2-2` (lane-advance heading ramp + yaw-rate averaging
against a mocked world), `UT-C2-3` (angle difference across the ±180deg
seam), `UT-C2-4` (lateral-profile phases incl. `raised_cosine` displacement
= `rate * duration / 2`)."""

from __future__ import annotations

import math

import pytest

from adas_sim.sources.carla.actor_behaviour import (
    LaneAdvancer, LateralProfile, _angle_diff_deg, build_lateral_profiles, lateral_rates,
)


# ---------------------------------------------------------------------------
# UT-C2-3 -- angle difference across the +/-180deg seam
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "new_deg, old_deg, expected_deg",
    [
        (10.0, 5.0, 5.0),
        (5.0, 10.0, -5.0),
        (179.0, -179.0, -2.0),   # crossing the seam the "short way" -- 2 deg apart, not 358
        (-179.0, 179.0, 2.0),
        (0.0, 350.0, 10.0),
        (350.0, 0.0, -10.0),
        (180.0, 0.0, -180.0),    # exactly antipodal -- the modulo formula's own boundary,
                                 # +180 and -180 are the same angle either way
    ],
)
def test_angle_diff_deg_wraps_to_the_shortest_signed_path(new_deg, old_deg, expected_deg):
    assert _angle_diff_deg(new_deg, old_deg) == pytest.approx(expected_deg)


# ---------------------------------------------------------------------------
# UT-C2-4 -- lateral-profile phases, incl. raised_cosine displacement
# ---------------------------------------------------------------------------


def test_const_phase_rate_is_constant_across_its_duration():
    profile = LateralProfile([{"name": "p", "rate_mps": 1.5, "duration_s": 4.0}])
    assert profile.rate_mps(0.0) == pytest.approx(1.5)
    assert profile.rate_mps(3.9) == pytest.approx(1.5)
    assert profile.phase_name(1.0) == "p"


def test_profile_falls_through_to_done_after_its_last_phase():
    profile = LateralProfile([{"name": "p", "rate_mps": 1.0, "duration_s": 1.0}])
    assert profile.rate_mps(1.5) == 0.0
    assert profile.phase_name(1.5) == "done"


def test_raised_cosine_phase_starts_and_ends_at_zero_rate():
    profile = LateralProfile([{"name": "p", "rate_mps": 2.0, "duration_s": 5.0, "shape": "raised_cosine"}])
    assert profile.rate_mps(0.0) == pytest.approx(0.0, abs=1e-9)
    assert profile.rate_mps(5.0 - 1e-9) == pytest.approx(0.0, abs=1e-4)


def test_raised_cosine_displacement_equals_rate_times_duration_over_two():
    """The physically-derived invariant: integrating
    `rate_mps * (1 - cos(2*pi*progress)) / 2` over one full phase equals
    `rate_mps * duration_s / 2`."""
    rate_mps, duration_s = 1.4, 5.0
    profile = LateralProfile([{"name": "p", "rate_mps": rate_mps, "duration_s": duration_s, "shape": "raised_cosine"}])

    steps = 100_000
    dt = duration_s / steps
    displacement = sum(profile.rate_mps(i * dt) * dt for i in range(steps))

    assert displacement == pytest.approx(rate_mps * duration_s / 2.0, rel=1e-3)


def test_build_and_sample_lateral_profiles_from_actor_cfgs():
    actor_cfgs = [
        {"name": "target", "lateral_profile": [{"name": "p", "rate_mps": 0.5, "duration_s": 10.0}]},
        {"name": "no_profile"},
    ]
    profiles = build_lateral_profiles(actor_cfgs)

    assert set(profiles) == {"target"}
    rates = lateral_rates(profiles, actor_cfgs, elapsed_s=1.0)
    assert rates == {"target": pytest.approx(0.5), "no_profile": 0.0}


# ---------------------------------------------------------------------------
# UT-C2-2 -- LaneAdvancer: heading ramp + yaw-rate averaging, against a
# duck-typed fake carla.World/carla.Actor (no live server, no carla package)
# ---------------------------------------------------------------------------


class _Location:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = x, y, z


class _Rotation:
    def __init__(self, yaw=0.0):
        self.yaw = yaw
        self.pitch = 0.0
        self.roll = 0.0


class _Transform:
    def __init__(self, location=None, rotation=None):
        self.location = location or _Location()
        self.rotation = rotation or _Rotation()


class _Waypoint:
    def __init__(self, transform):
        self.transform = transform


class _FakeActor:
    def __init__(self, actor_id, transform):
        self.id = actor_id
        self._transform = transform

    def get_transform(self):
        return self._transform

    def set_transform(self, transform):
        self._transform = transform

    def get_location(self):
        return self._transform.location


class _FakeWorld:
    """`get_map().get_waypoint(...)` always answers with `self.heading_deg`
    -- the test drives the "road's" heading directly rather than modelling
    real waypoint geometry, which is exactly what "against a mocked world"
    means for `LaneAdvancer`'s own heading-refresh/ramp/yaw-rate logic."""

    def __init__(self):
        self.heading_deg = 0.0

    def get_map(self):
        return self

    def get_waypoint(self, _location):
        return _Waypoint(_Transform(rotation=_Rotation(yaw=self.heading_deg)))


def test_yaw_rate_is_zero_before_any_heading_refresh_has_a_prior_sample():
    world = _FakeWorld()
    actor = _FakeActor(1, _Transform())
    advancer = LaneAdvancer()

    advancer.advance(world, actor, speed_mps=10.0, dt_s=1.0)  # first call always refreshes; no prior heading yet

    assert advancer.yaw_rate_rad_s(1) == 0.0


def test_yaw_rate_is_the_negated_average_rate_over_the_refresh_interval():
    """CARLA's yaw is left-handed (+y = right); a positive CARLA heading
    delta (a rightward turn) must read as a NEGATIVE yaw_rate in our
    +y-left, positive-turns-left convention."""
    world = _FakeWorld()
    actor = _FakeActor(1, _Transform())
    advancer = LaneAdvancer()

    world.heading_deg = 0.0
    advancer.advance(world, actor, speed_mps=10.0, dt_s=1.0)  # refresh #1: no prior heading, still no yaw_rate

    world.heading_deg = 30.0  # the "road" turns right by 30deg over this 1s interval
    advancer.advance(world, actor, speed_mps=10.0, dt_s=1.0)  # refresh #2: old=0, new=30, elapsed_s=1.0

    assert advancer.yaw_rate_rad_s(1) == pytest.approx(math.radians(-30.0))


def test_heading_ramps_across_multiple_ticks_rather_than_snapping():
    """A slower actor spans several ticks between REFRESH_DISTANCE_M
    (2.0m) samples -- the applied heading must ramp toward the newly
    sampled target linearly, not jump to it in one tick (the
    "heading-jerk fix")."""
    world = _FakeWorld()
    actor = _FakeActor(1, _Transform())
    advancer = LaneAdvancer()
    speed_mps, dt_s = 2.0, 0.5  # step_m = 1.0/tick; refresh every 2 ticks

    world.heading_deg = 0.0
    advancer.advance(world, actor, speed_mps, dt_s)  # tick 1: first-ever refresh, heading -> 0
    advancer.advance(world, actor, speed_mps, dt_s)  # tick 2: distance_since=1.0m, no refresh yet

    world.heading_deg = 10.0  # the road ahead turns
    advancer.advance(world, actor, speed_mps, dt_s)  # tick 3: distance_since=2.0m -- refreshes to 10deg
    halfway_yaw = actor.get_transform().rotation.yaw
    assert halfway_yaw == pytest.approx(5.0)  # ramping, not snapped to 10 immediately

    advancer.advance(world, actor, speed_mps, dt_s)  # tick 4: continues ramping
    assert actor.get_transform().rotation.yaw == pytest.approx(10.0)  # reaches the target
