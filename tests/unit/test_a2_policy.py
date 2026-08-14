# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-04: IMP-0069/IMP-0163 -- UT-CFG-01, UT-CFG-14."""

from __future__ import annotations

import pytest
from google.protobuf import descriptor_pb2

from adas_sim.config.policy import check_interpolatable, microseconds_to_nanoseconds, read_period_us
from adas_sim.diagnostics.errors import AuthoringError

_FT = descriptor_pb2.FieldDescriptorProto


def test_interpolate_on_a_continuous_port_is_accepted():
    """UT-CFG-01: declare interpolate on a continuous port, then on an enum
    port."""
    check_interpolatable(_FT.TYPE_DOUBLE, repeated=False, port_name="egoDyn.vx")  # no raise


def test_interpolate_on_an_enum_port_is_refused():
    with pytest.raises(AuthoringError) as excinfo:
        check_interpolatable(_FT.TYPE_ENUM, repeated=False, port_name="compState")
    assert "compState" in str(excinfo.value)


@pytest.mark.parametrize("field_type,repeated", [
    (_FT.TYPE_STRING, False),   # identifier
    (_FT.TYPE_UINT32, False),   # count
    (_FT.TYPE_DOUBLE, True),    # repeated -- even though the scalar itself is continuous
])
def test_interpolate_refused_on_every_non_continuous_shape(field_type, repeated):
    with pytest.raises(AuthoringError):
        check_interpolatable(field_type, repeated=repeated, port_name="p")


def test_declare_a_period_in_integer_microseconds_reads_correctly():
    """UT-CFG-14: declare a period in integer microseconds; read it as
    period_ns in the emitted spec."""
    calibration = {"AEB_TTC_PERIOD_US": 10000}
    period_us = read_period_us(calibration, component="aeb", function="ttc")
    assert period_us == 10000
    assert microseconds_to_nanoseconds(period_us) == 10_000_000


def test_a_fractional_period_is_refused_no_float_anywhere():
    calibration = {"AEB_TTC_PERIOD_US": 10000.0}
    with pytest.raises(AuthoringError):
        read_period_us(calibration, component="aeb", function="ttc")


def test_a_missing_period_key_is_refused_naming_it():
    with pytest.raises(AuthoringError) as excinfo:
        read_period_us({}, component="aeb", function="ttc")
    assert "AEB_TTC_PERIOD_US" in str(excinfo.value)
