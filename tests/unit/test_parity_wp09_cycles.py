# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""PARITY `WP-09` (Python half only -- `io/cycles.py`, no `viz` dependency)
tests: `UT-cycles-01`..`UT-cycles-03` (`docs/v2/parity/PARITY_Test_Spec.md`
§5.7). `F-REC-STUB`: a recording stub whose declared components are set
per case.
"""

from __future__ import annotations

import inspect

from adas_sim.io.base import ComponentBuildInfo, RunManifest
from adas_sim.io.cycles import discover, run_of


class _RecStub:
    def __init__(self, components: tuple[ComponentBuildInfo, ...]) -> None:
        self._manifest = RunManifest(manifest_version=2, components=components)

    def meta(self) -> RunManifest:
        return self._manifest


def test_cycles_come_from_the_recording_ut_cycles_01():
    """UT-cycles-01."""
    stub_a = _RecStub((ComponentBuildInfo(name="df", period_ns=20_000_000),))
    stub_b = _RecStub((
        ComponentBuildInfo(name="df", period_ns=20_000_000),
        ComponentBuildInfo(name="vdy", period_ns=10_000_000),
    ))

    cycles_a = discover(stub_a)
    cycles_b = discover(stub_b)
    assert {c.name for c in cycles_a} == {"df"}  # .c1: follows the recording
    assert {c.name for c in cycles_b} == {"df", "vdy"}

    # .c2: no configuration parameter exists to pass -- structural, not
    # just untested; discover()'s own signature takes only a reader.
    params = list(inspect.signature(discover).parameters)
    assert params == ["reader"]


def test_name_index_and_period_ut_cycles_02():
    """UT-cycles-02."""
    stub = _RecStub((
        ComponentBuildInfo(name="df", period_ns=20_000_000),
        ComponentBuildInfo(name="vdy", period_ns=10_000_000),
    ))

    cycles = discover(stub)

    assert len(cycles) == 2
    for expected_index, cycle in enumerate(cycles):
        assert cycle.name and isinstance(cycle.period_ns, int)  # .c1: all three present
        assert cycle.index == expected_index
        assert isinstance(cycle.period_ns, int) and not isinstance(cycle.period_ns, bool)  # .c2: integer, not float


def test_a_value_names_its_cycle_run_ut_cycles_03():
    """UT-cycles-03."""
    period_ns = 20_000_000
    first_run = run_of("df.objects", 5_000_000, period_ns=period_ns)
    second_run = run_of("df.objects", 25_000_000, period_ns=period_ns)

    assert first_run != second_run  # .c1: different runs report different identities
