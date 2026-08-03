# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C2 slice 2: `SyntheticSource` -- scripted stimuli, no world model
(`sim_implementation_plan.md` S-C2)."""

from __future__ import annotations

import pytest

from adas_sim.contracts.scenario import (
    EgoScenario, RoadHint, RunControl, Scenario, ScenarioContent, SensorModelRef, SutRef,
)
from adas_sim.core.errors import AuthoringError, InternalError
from adas_sim.sources.synthetic import SyntheticSource


def _scenario() -> Scenario:
    return Scenario(
        schema=2, id="test", doc="",
        scenario=ScenarioContent(road=RoadHint(), ego=EgoScenario(speed_mps=0.0), actors=()),
        world={}, sensor_model=SensorModelRef(), run=RunControl(), sut=SutRef(),
    )


def test_emits_is_the_union_of_every_scripted_ticks_ports():
    source = SyntheticSource([{"objects": b"t0"}, {"veh_dyn": b"t0"}, {"objects": b"t1"}])
    assert source.emits() == frozenset({"objects", "veh_dyn"})


def test_poll_replays_the_script_in_order_deterministically():
    source = SyntheticSource([{"objects": b"t0"}, {"objects": b"t1"}, {"objects": b"t2"}])
    source.start(_scenario())

    assert [source.poll()["objects"] for _ in range(3)] == [b"t0", b"t1", b"t2"]


def test_restarting_replays_from_the_beginning():
    source = SyntheticSource([{"objects": b"t0"}, {"objects": b"t1"}])
    source.start(_scenario())
    source.poll()
    source.stop()

    source.start(_scenario())
    assert source.poll()["objects"] == b"t0"  # not t1 -- start() resets the index


def test_poll_before_start_raises():
    source = SyntheticSource([{"objects": b"t0"}])
    with pytest.raises(InternalError):
        source.poll()


def test_polling_past_the_scripts_length_raises_naming_the_script_length():
    source = SyntheticSource([{"objects": b"t0"}])
    source.start(_scenario())
    source.poll()

    with pytest.raises(AuthoringError) as excinfo:
        source.poll()
    assert "1" in str(excinfo.value)


def test_a_tick_with_no_entry_for_a_port_omits_it_not_a_default():
    """A port only some ticks declare -- `Pipeline`'s own "absent port"
    convention (valid=0 downstream) handles the gap; `SyntheticSource`
    never invents a placeholder value."""
    source = SyntheticSource([{"objects": b"t0", "veh_dyn": b"vd0"}, {"objects": b"t1"}])
    source.start(_scenario())
    source.poll()

    second = source.poll()
    assert "veh_dyn" not in second
    assert second["objects"] == b"t1"
