# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""PARITY `WP-10` tests: `UT-ranges-01`..`UT-ranges-03`
(`docs/v2/parity/PARITY_Test_Spec.md` §5.7). `F-STORE`: an in-memory store
that can be written, closed and reopened.
"""

from __future__ import annotations

import dataclasses

from adas_sim.io.ranges import Range, read, write


class _Store:
    """`F-STORE`, same shape `test_parity_wp07_bundle.py::_Store` uses --
    a fresh instance built from a closed one's own payload stands in for
    "reopened"."""

    def __init__(self, payload=()) -> None:
        self._payload = tuple(payload)
        self._closed = False

    def write_ranges(self, ranges) -> None:
        self._payload = tuple(ranges)

    def read_ranges(self):
        return self._payload

    def close(self) -> None:
        self._closed = True

    def reopen(self) -> "_Store":
        assert self._closed, "reopen() is only meaningful after close()"
        return _Store(self._payload)


def test_bounds_are_in_recording_time_ut_ranges_01():
    """UT-ranges-01."""
    # SW-0033's own claim is structural: no wall-clock field exists at all,
    # so there is nothing a host clock or timezone change COULD shift.
    field_names = {f.name for f in dataclasses.fields(Range)}
    assert field_names == {"name", "start_ns", "end_ns"}

    store = _Store()
    write(store, [Range(name="interesting", start_ns=1_000_000_000, end_ns=2_000_000_000)])
    (restored,) = read(store)
    assert (restored.start_ns, restored.end_ns) == (1_000_000_000, 2_000_000_000)  # .c1


def test_ranges_round_trip_ut_ranges_02():
    """UT-ranges-02."""
    original = Range(name="interesting", start_ns=1_000_000_000, end_ns=2_500_000_000)
    store = _Store()

    write(store, [original])
    store.close()
    reopened = store.reopen()
    (restored,) = read(reopened)

    assert restored == original  # .c1: name and bounds compare equal


def test_membership_is_exact_at_the_edges_ut_ranges_03():
    """UT-ranges-03."""
    span = Range(name="window", start_ns=1_000, end_ns=2_000)

    assert span.contains(1_500) is True  # inside
    assert span.contains(500) is False  # outside, before
    assert span.contains(2_500) is False  # outside, after
    assert span.contains(1_000) is True  # .c1: inclusive at the start boundary
    assert span.contains(2_000) is True  # .c1: inclusive at the end boundary
