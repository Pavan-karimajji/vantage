# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-A2 `SensorModel` tests: UT-A2-6, UT-A2-9 (docs/sim_implementation_plan.md)."""

from __future__ import annotations

import pytest

from adas_sim.core.errors import AuthoringError
from adas_sim.model.sensors import parse_sensors

#: Real shape, real numbers, from modules/df/src/project/base/default.yaml's
#: bsd: section -- ported here as plain data, never as a "bsd" import (GT-1).
_TWO_SENSOR_FIXTURE = {
    "BSD_SENSOR_COUNT": 2,
    "BSD_SENSOR_0_POSE_X_M": -0.80,
    "BSD_SENSOR_0_POSE_Y_M": 0.78,
    "BSD_SENSOR_0_FOV_AZIMUTH_DEG": 60.0,
    "BSD_SENSOR_0_RANGE_MIN_M": 0.5,
    "BSD_SENSOR_0_SIDE": "LEFT",
    "BSD_SENSOR_1_POSE_X_M": -0.80,
    "BSD_SENSOR_1_POSE_Y_M": -0.78,
    "BSD_SENSOR_1_FOV_AZIMUTH_DEG": 60.0,
    "BSD_SENSOR_1_RANGE_MIN_M": 0.5,
    "BSD_SENSOR_1_SIDE": "RIGHT",
}


def test_sensor_model_yields_the_declared_count_with_pose_fov_range_side_populated():
    """UT-A2-6."""
    sensors = parse_sensors(_TWO_SENSOR_FIXTURE)
    assert len(sensors) == 2
    assert {s.sensor_id for s in sensors} == {"0", "1"}
    for sensor in sensors:
        assert "POSE_X_M" in sensor.fields
        assert "POSE_Y_M" in sensor.fields
        assert "FOV_AZIMUTH_DEG" in sensor.fields
        assert "RANGE_MIN_M" in sensor.fields
        assert "SIDE" in sensor.fields


def test_sensor_count_mismatch_raises_authoring_error():
    """UT-A2-6: a declared count that disagrees with what was actually found
    is exactly the "50 objects at the origin" defect R-SIM-3 exists to catch."""
    broken = dict(_TWO_SENSOR_FIXTURE)
    broken["BSD_SENSOR_COUNT"] = 3
    with pytest.raises(AuthoringError):
        parse_sensors(broken)


def test_a_case_differing_key_does_not_resolve():
    """UT-A2-6 / P-3: key comparison is exact, never case-folded -- on every
    platform, not just Linux."""
    sensors = parse_sensors(_TWO_SENSOR_FIXTURE)
    sensor_0 = next(s for s in sensors if s.sensor_id == "0")
    assert sensor_0.get("SIDE") == "LEFT"
    assert sensor_0.get("side") is None
    assert sensor_0.get("Side") is None


def test_sensor_model_is_prefix_independent():
    """UT-A2-9: a fixture using a different key prefix parses identically --
    the parser reads shape, not domain (GT-1)."""
    other_prefix_fixture = {
        key.replace("BSD_", "XYZ_", 1) if key.startswith("BSD_") else key: value
        for key, value in _TWO_SENSOR_FIXTURE.items()
    }
    bsd_sensors = parse_sensors(_TWO_SENSOR_FIXTURE)
    xyz_sensors = parse_sensors(other_prefix_fixture)
    assert [(s.sensor_id, s.fields) for s in bsd_sensors] == [(s.sensor_id, s.fields) for s in xyz_sensors]
