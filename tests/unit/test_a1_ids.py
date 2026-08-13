# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-A1 run-id test: UT-A1-7 (docs/sim_implementation_plan.md)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from adas_sim.diagnostics.errors import InternalError
from adas_sim.runspec.ids import REQUIRED_KEYS, new_run_id

_CLOCK = datetime(2026, 7, 28, 14, 30, 12, tzinfo=timezone.utc)
_BASE_INPUTS = {
    "pipeline_sha": "p1",
    "recording_sha": "r1",
    "project": "base",
    "component_build_shas": "df:abc123",
    "bundle_sha": "b1",
    "overrides_repr": "{}",
    "seed": "0",
}


def test_new_run_id_is_stable_for_identical_inputs():
    """UT-A1-7: same inputs -> same id."""
    first = new_run_id(inputs=dict(_BASE_INPUTS), clock=_CLOCK)
    second = new_run_id(inputs=dict(_BASE_INPUTS), clock=_CLOCK)
    assert first == second
    assert first.startswith("20260728T143012Z-")


def test_new_run_id_differs_for_any_single_changed_input():
    """UT-A1-7: N-9's equality is itself diagnostic -- a single changed input
    must change the id."""
    baseline = new_run_id(inputs=_BASE_INPUTS, clock=_CLOCK)
    for key in REQUIRED_KEYS:
        changed = dict(_BASE_INPUTS)
        changed[key] = changed[key] + "_different"
        assert new_run_id(inputs=changed, clock=_CLOCK) != baseline, f"changing {key!r} did not change the id"


def test_new_run_id_rejects_a_partial_input_set():
    """A caller supplying fewer than the required keys is a framework bug (N-9)."""
    with pytest.raises(InternalError):
        new_run_id(inputs={"seed": "0"}, clock=_CLOCK)
