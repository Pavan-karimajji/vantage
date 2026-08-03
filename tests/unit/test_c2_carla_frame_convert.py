# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C2 slice 5: `UT-C2-1` -- frame conversion, the existing sign
conventions re-asserted (world to ego, right-to-left flip, `R-COORD-1`)."""

from __future__ import annotations

import math

import pytest

from adas_sim.sources.carla.frame_convert import to_ego_frame


def test_target_directly_ahead_of_ego_facing_same_heading():
    rel = to_ego_frame(0.0, 0.0, 0.0, 10.0, 0.0, 20.0, 0.0, 5.0, 0.0)
    assert rel.dist_x == pytest.approx(20.0)
    assert rel.dist_y == pytest.approx(0.0)
    assert rel.vrel_x == pytest.approx(-5.0)  # closing: target slower than ego
    assert rel.vrel_y == pytest.approx(0.0)


def test_carla_right_becomes_our_left_negative():
    """CARLA's world-frame +y is RIGHT; our ego-frame +y is LEFT
    (`R-COORD-1`) -- a target at world (0, 5) directly right of an
    ego facing +x must read a NEGATIVE ego-frame dist_y."""
    rel = to_ego_frame(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 5.0, 0.0, 0.0)
    assert rel.dist_y == pytest.approx(-5.0)


def test_target_behind_ego_reads_negative_dist_x():
    rel = to_ego_frame(0.0, 0.0, 0.0, 0.0, 0.0, -10.0, 0.0, 0.0, 0.0)
    assert rel.dist_x == pytest.approx(-10.0)


def test_ego_heading_rotation_is_respected():
    """Ego facing +90deg (world +y): a target ahead in ego's own frame is
    directly along world +y."""
    rel = to_ego_frame(0.0, 0.0, 90.0, 0.0, 0.0, 0.0, 10.0, 0.0, 0.0)
    assert rel.dist_x == pytest.approx(10.0)
    assert rel.dist_y == pytest.approx(0.0, abs=1e-9)


def test_relative_velocity_is_target_minus_ego_projected_onto_ego_heading():
    rel = to_ego_frame(0.0, 0.0, 0.0, 5.0, 0.0, 10.0, 0.0, 5.0, 0.0)
    assert rel.vrel_x == pytest.approx(0.0)  # same speed -- neither closing nor opening


def test_diagonal_target_matches_hand_computed_projection():
    ego_yaw_deg = 45.0
    rel = to_ego_frame(0.0, 0.0, ego_yaw_deg, 0.0, 0.0, 10.0, 10.0, 0.0, 0.0)
    yaw_rad = math.radians(ego_yaw_deg)
    forward = (math.cos(yaw_rad), math.sin(yaw_rad))
    expected_dist_x = 10.0 * forward[0] + 10.0 * forward[1]
    assert rel.dist_x == pytest.approx(expected_dist_x)
    assert rel.dist_y == pytest.approx(0.0, abs=1e-9)  # directly ahead along the 45deg heading
