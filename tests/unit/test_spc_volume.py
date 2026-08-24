# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-22` `SI-14 runspec` -- `UT-SPC-18` (`SW-0225`): the pre-run recording
volume estimate, labelled an upper bound and revised from the measured
rate. `runspec/volume.py::estimate_upper_bound_bytes`/
`revised_estimate_bytes` -- moved here from `sources/recorder.py::Recorder`
(`IMP-0225`, `MOVE`); `test_c2_recorder.py`'s own existing coverage of
`Recorder.estimate_upper_bound_bytes`/`revised_estimate_bytes` (now thin
wrappers over this module) is unaffected and still exercises the same
arithmetic through the live `Recorder`."""

from __future__ import annotations

from adas_sim.runspec import volume


def test_estimate_upper_bound_bytes_is_the_sum_of_port_caps_times_ticks():
    assert volume.estimate_upper_bound_bytes([100, 256, 44], 10) == 4000


def test_estimate_upper_bound_bytes_is_zero_with_no_ports():
    assert volume.estimate_upper_bound_bytes([], 100) == 0


def test_revised_estimate_is_none_before_the_threshold():
    assert volume.revised_estimate_bytes(bytes_written=500, ticks_written=10, total_ticks=1000) is None


def test_revised_estimate_extrapolates_the_measured_rate_past_the_threshold():
    # 100 ticks written, 1000 bytes -> 10 bytes/tick; 500 total ticks -> 5000
    result = volume.revised_estimate_bytes(bytes_written=1000, ticks_written=100, total_ticks=500)
    assert result == 5000


def test_revised_estimate_threshold_is_configurable():
    assert volume.revised_estimate_bytes(
        bytes_written=10, ticks_written=5, total_ticks=100, min_ticks_before_revision=5,
    ) == 200
