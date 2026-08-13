# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 slice 10 `view/plots.py` tests: `UT-B3-7` (lane bookkeeping half)
(docs/sim_implementation_plan.md) plus kind-gating. No Qt (`view/` stays
headless-testable)."""

from __future__ import annotations

import pytest

from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.player.panels.plots import PlotState


def test_unknown_kind_raises():
    with pytest.raises(AuthoringError):
        PlotState("scatter3d")


def test_timeseries_lanes_never_merge_and_stay_ordered():
    """UT-B3-7 (lane half): two signals of different magnitude create two
    lanes -- `add_lane` never merges, the same rule `TimelineState` holds."""
    state = PlotState("timeseries")
    state.add_lane("derived.ttc")
    state.add_lane("source.veh_dyn.longitudinal.velocity")
    state.add_lane("derived.ttc")  # duplicate -- no second lane
    assert state.lanes() == ("derived.ttc", "source.veh_dyn.longitudinal.velocity")


def test_state_kind_also_supports_lanes():
    state = PlotState("state")
    state.add_lane("test.warning")
    assert state.lanes() == ("test.warning",)


def test_remove_lane():
    state = PlotState("timeseries")
    state.add_lane("a")
    state.add_lane("b")
    state.remove_lane("a")
    assert state.lanes() == ("b",)


def test_add_lane_on_an_xy_panel_raises():
    state = PlotState("xy")
    with pytest.raises(AuthoringError):
        state.add_lane("derived.ttc")


def test_set_xy_stores_x_y_and_optional_color():
    state = PlotState("xy")
    state.set_xy("source.veh_dyn.longitudinal.velocity", "derived.ttc")
    assert (state.x, state.y, state.color) == ("source.veh_dyn.longitudinal.velocity", "derived.ttc", None)

    state.set_xy("a", "b", color="c")
    assert (state.x, state.y, state.color) == ("a", "b", "c")


def test_set_xy_on_a_timeseries_panel_raises():
    state = PlotState("timeseries")
    with pytest.raises(AuthoringError):
        state.set_xy("a", "b")


def test_set_distribution_stores_the_one_address():
    state = PlotState("distribution")
    state.set_distribution("derived.ttc")
    assert state.address == "derived.ttc"


def test_set_distribution_on_an_xy_panel_raises():
    state = PlotState("xy")
    with pytest.raises(AuthoringError):
        state.set_distribution("derived.ttc")
