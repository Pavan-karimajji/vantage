# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`render/viewer._index_expectation_windows` (S-C3 follow-up, timeline
expectation-window overlay, `sim_visualization_spec.md` SS7.3) -- pure
logic, no widget construction, so this stays a unit test despite living in
`render/viewer.py` (`PySide6` import-guard only, same convention
`test_b3_threading.py` already uses for a non-widget class in that module).
"""

from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from adas_sim.contracts.scenario import (  # noqa: E402
    ConstantAnchor, EgoScenario, Marker, RoadHint, RunControl, Scenario, ScenarioContent,
    SensorModelRef, SutRef,
)
from adas_sim.core.session import Session  # noqa: E402
from adas_sim.core.tick import PortValue, Pose2D, Tick  # noqa: E402
from adas_sim.render.viewer import _index_expectation_windows  # noqa: E402

_PERIOD_NS = 100_000_000  # 0.1 s/tick


def _scenario(expect: list[dict], markers: dict | None = None) -> Scenario:
    return Scenario(
        schema=2, id="t", doc="",
        scenario=ScenarioContent(road=RoadHint(), ego=EgoScenario(speed_mps=0.0), actors=()),
        world={}, sensor_model=SensorModelRef(), run=RunControl(), sut=SutRef(),
        markers=markers or {}, expect=tuple(expect),
    )


def _ticks(values: list[float], *, port: str = "widget.outputs") -> tuple[Tick, ...]:
    return tuple(
        Tick(
            index=i, t_ns=i * _PERIOD_NS, dt_ns=_PERIOD_NS,
            ports={port: PortValue(name=port, origin="simulated", message=SimpleNamespace(value=v), t_ns=i * _PERIOD_NS)},
            pose=Pose2D(x_m=0.0, y_m=0.0, yaw_rad=0.0),
        )
        for i, v in enumerate(values)
    )


def _session(ticks: tuple[Tick, ...]) -> Session:
    return Session(run_id="t", name="t", ticks=ticks)


def test_no_scenario_yields_no_windows():
    """`--scenario` not given -- the overlay is absent, never a guessed
    pass (`NR-SIM-4`)."""
    assert _index_expectation_windows(None, _session(_ticks([0, 0]))) == {}


def test_a_during_expectation_is_indexed_by_its_signal():
    ticks = _ticks([0, 0, 0, 1, 1])  # off until t=0.3
    scenario = _scenario([
        {"id": "EXP-1", "signal": "widget.outputs.value", "equals": 0, "during": [0.0, 0.2]},
    ])
    windows = _index_expectation_windows(scenario, _session(ticks))
    assert set(windows) == {"widget.outputs.value"}
    result = windows["widget.outputs.value"][0]
    assert result.window_s == (0.0, 0.2)
    assert result.passed is True


def test_a_predicate_with_no_window_is_not_indexed():
    """`equals ... always:` has no single fixed span -- `evaluate_scenario`
    still runs it (`sim check` needs the pass/fail), but the timeline
    overlay has nothing to draw for it."""
    ticks = _ticks([1, 1, 1, 1])
    scenario = _scenario([{"id": "EXP-1", "signal": "widget.outputs.value", "equals": 1, "always": True}])
    assert _index_expectation_windows(scenario, _session(ticks)) == {}


def test_two_expectations_on_one_signal_both_appear():
    """`bsd_mergein_vlat025.yaml`'s own real shape -- EXP-1/EXP-2 both
    address `left.warning` -- so this is a list per address, not a single
    result silently overwriting the other."""
    ticks = _ticks([0, 0, 1, 1, 1])
    scenario = _scenario(
        [
            {"id": "EXP-1", "signal": "widget.outputs.value", "equals": 0, "during": [0.0, "marker.entry"]},
            {"id": "EXP-2", "signal": "widget.outputs.value", "becomes": 1, "within_s": 0.05, "of": "marker.entry"},
        ],
        markers={"entry": Marker(id="entry", at=ConstantAnchor(seconds=0.2, source="test"))},
    )
    windows = _index_expectation_windows(scenario, _session(ticks))
    assert {r.id for r in windows["widget.outputs.value"]} == {"EXP-1", "EXP-2"}
