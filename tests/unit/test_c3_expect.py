# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C3 expectation predicate vocabulary + evaluator tests
(docs/sim_implementation_plan.md UT-C3-2..UT-C3-8-equivalent coverage).

Every fixture is a synthetic "widget.outputs" port -- no function name
anywhere (`R-SIM-1`), same convention `test_c1c_pipeline.py` already uses.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from adas_sim.check.expect import (
    Between, Becomes, Condition, Count, EqualsAlways, EqualsAtLeastS, EqualsAtMostS,
    EqualsDuring, EqualsWhenever, Monotonic, Never, TimeRef,
    evaluate_expectation, evaluate_scenario, parse_expectation, resolve_marker, resolve_markers,
)
from adas_sim.config.scenario import BecomesAnchor, ConstantAnchor, CrossesAnchor, Marker, load_scenario
from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.session.tick import PortValue, Pose2D, Tick

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "scenarios"
_PERIOD_NS = 100_000_000  # 0.1 s/tick


def _ticks(values: list[float], *, port: str = "widget.outputs") -> tuple[Tick, ...]:
    return tuple(
        Tick(
            index=i, t_ns=i * _PERIOD_NS, dt_ns=_PERIOD_NS,
            ports={port: PortValue(name=port, origin="simulated", message=SimpleNamespace(value=v), t_ns=i * _PERIOD_NS)},
            pose=Pose2D(x_m=0.0, y_m=0.0, yaw_rad=0.0),
        )
        for i, v in enumerate(values)
    )


# ---------------------------------------------------------------------------
# parse_expectation -- shape selection + closed-vocabulary errors
# ---------------------------------------------------------------------------


def test_parses_equals_always():
    exp = parse_expectation(
        {"id": "E1", "signal": "widget.outputs.value", "equals": 1, "always": True}, where="t",
    )
    assert exp.predicate == EqualsAlways(value=1)


def test_parses_equals_during_with_marker_bound():
    exp = parse_expectation(
        {"id": "E1", "signal": "widget.outputs.value", "equals": 0, "during": [0.0, "marker.entry"]}, where="t",
    )
    assert exp.predicate == EqualsDuring(value=0, start=0.0, end=TimeRef(marker_id="entry"))


def test_parses_equals_whenever():
    exp = parse_expectation(
        {"id": "E1", "signal": "widget.outputs.value", "equals": 1, "whenever": "widget.outputs.value != 0"}, where="t",
    )
    assert exp.predicate == EqualsWhenever(value=1, condition=Condition(signal="widget.outputs.value", op="!=", value="0"))


def test_parses_equals_at_least_s_and_at_most_s():
    least = parse_expectation({"id": "E1", "signal": "s", "equals": 1, "at_least_s": 0.5}, where="t")
    most = parse_expectation({"id": "E2", "signal": "s", "equals": 1, "at_most_s": 2.0}, where="t")
    assert least.predicate == EqualsAtLeastS(value=1, duration_s=0.5)
    assert most.predicate == EqualsAtMostS(value=1, duration_s=2.0)


def test_parses_becomes():
    exp = parse_expectation(
        {"id": "E1", "signal": "s", "becomes": 1, "within_s": 0.3, "of": "marker.entry"}, where="t",
    )
    assert exp.predicate == Becomes(value=1, within_s=0.3, of=TimeRef(marker_id="entry"))


def test_becomes_without_within_s_is_a_schema_error():
    """UT-C3-3."""
    with pytest.raises(AuthoringError, match="within_s"):
        parse_expectation({"id": "E1", "signal": "s", "becomes": 1, "of": "marker.entry"}, where="t")


def test_parses_never_count_between_monotonic():
    assert parse_expectation({"id": "E1", "signal": "s", "never": 2}, where="t").predicate == Never(value=2)
    assert parse_expectation(
        {"id": "E1", "signal": "s", "count": {"value": 1, "times": 3}}, where="t",
    ).predicate == Count(value=1, times=3)
    assert parse_expectation(
        {"id": "E1", "signal": "s", "between": [0.0, 5.0]}, where="t",
    ).predicate == Between(lo=0.0, hi=5.0)
    assert parse_expectation(
        {"id": "E1", "signal": "s", "monotonic": "decreasing"}, where="t",
    ).predicate == Monotonic(direction="decreasing")


def test_two_shape_keys_at_once_is_a_schema_error():
    with pytest.raises(AuthoringError, match="exactly one"):
        parse_expectation({"id": "E1", "signal": "s", "never": 1, "count": {"value": 1, "times": 1}}, where="t")


def test_equals_with_two_modifiers_is_a_schema_error():
    with pytest.raises(AuthoringError, match="exactly one"):
        parse_expectation({"id": "E1", "signal": "s", "equals": 1, "always": True, "at_least_s": 1.0}, where="t")


def test_whenever_with_two_signals_is_a_schema_error():
    with pytest.raises(AuthoringError, match="closed comparison"):
        parse_expectation(
            {"id": "E1", "signal": "s", "equals": 1, "whenever": "a.b == c.d + 1"}, where="t",
        )


def test_missing_id_is_a_schema_error():
    with pytest.raises(AuthoringError):
        parse_expectation({"signal": "s", "never": 1}, where="t")


# ---------------------------------------------------------------------------
# evaluate_expectation -- both directions per predicate (UT-C3-2)
# ---------------------------------------------------------------------------


def test_equals_always_passes_and_fails():
    """UT-C3-5: a failing result carries the actual value and actual time
    next to the expected ones."""
    ticks = _ticks([1, 1, 1, 1])
    exp = parse_expectation({"id": "E", "signal": "widget.outputs.value", "equals": 1, "always": True}, where="t")
    assert evaluate_expectation(exp, ticks, markers={}).passed is True

    ticks_bad = _ticks([1, 1, 0, 1])
    result = evaluate_expectation(exp, ticks_bad, markers={})
    assert result.passed is False
    assert result.actual_value == 0
    assert result.actual_time_s == pytest.approx(0.2)


def test_equals_always_reports_no_window_s():
    """A predicate with no single fixed span never guesses one
    (`NR-SIM-4`) -- `always`/`whenever`/`never`/`count`/`between`/
    `monotonic`/`at_least_s`/`at_most_s` all stay `window_s=None`; only
    `during`/`becomes` (their own dedicated tests) have one."""
    ticks = _ticks([1, 1, 1, 1])
    exp = parse_expectation({"id": "E", "signal": "widget.outputs.value", "equals": 1, "always": True}, where="t")
    assert evaluate_expectation(exp, ticks, markers={}).window_s is None


def test_equals_during_passes_and_fails():
    ticks = _ticks([0, 0, 0, 1, 1])  # off until t=0.3, then on
    exp = parse_expectation(
        {"id": "E", "signal": "widget.outputs.value", "equals": 0, "during": [0.0, "marker.entry"]}, where="t",
    )
    assert evaluate_expectation(exp, ticks, markers={"entry": 0.2}).passed is True
    assert evaluate_expectation(exp, ticks, markers={"entry": 0.35}).passed is False


def test_equals_during_reports_its_window_s():
    """The timeline overlay's own input (`render/timeline.py` §7.3): a
    `during:` span's window_s is exactly its resolved [start, end], marker
    bounds included, regardless of pass/fail."""
    ticks = _ticks([0, 0, 0, 1, 1])
    exp = parse_expectation(
        {"id": "E", "signal": "widget.outputs.value", "equals": 0, "during": [0.0, "marker.entry"]}, where="t",
    )
    result = evaluate_expectation(exp, ticks, markers={"entry": 0.35})
    assert result.window_s == (0.0, 0.35)


def test_equals_whenever_passes_and_fails():
    values = [0, 1, 1, 0]  # a second signal drives the condition
    ticks = tuple(
        Tick(
            index=i, t_ns=i * _PERIOD_NS, dt_ns=_PERIOD_NS,
            ports={
                "widget.outputs": PortValue(
                    name="widget.outputs", origin="simulated",
                    message=SimpleNamespace(value=v, scenario=("MERGE_IN" if v else "NONE")), t_ns=i * _PERIOD_NS,
                ),
            },
            pose=Pose2D(x_m=0.0, y_m=0.0, yaw_rad=0.0),
        )
        for i, v in enumerate(values)
    )
    exp_ok = parse_expectation(
        {
            "id": "E", "signal": "widget.outputs.scenario", "equals": "MERGE_IN",
            "whenever": "widget.outputs.value != 0",
        }, where="t",
    )
    assert evaluate_expectation(exp_ok, ticks, markers={}).passed is True

    exp_bad = parse_expectation(
        {
            "id": "E", "signal": "widget.outputs.scenario", "equals": "NONE",
            "whenever": "widget.outputs.value != 0",
        }, where="t",
    )
    result = evaluate_expectation(exp_bad, ticks, markers={})
    assert result.passed is False


def test_equals_at_least_s_passes_and_fails():
    exp = parse_expectation({"id": "E", "signal": "widget.outputs.value", "equals": 1, "at_least_s": 0.25}, where="t")
    ticks_short = _ticks([0, 1, 0, 0, 0])  # span [t=0.1 .. t=0.2), duration 0.1s < 0.25 -> fails
    assert evaluate_expectation(exp, ticks_short, markers={}).passed is False

    ticks_long = _ticks([0, 1, 1, 1, 1, 1, 0])  # span duration 0.4s >= 0.25
    assert evaluate_expectation(exp, ticks_long, markers={}).passed is True


def test_equals_at_most_s_passes_and_fails():
    exp = parse_expectation({"id": "E", "signal": "widget.outputs.value", "equals": 1, "at_most_s": 0.25}, where="t")
    ticks_ok = _ticks([0, 1, 1, 0])  # span duration 0.1s <= 0.25
    assert evaluate_expectation(exp, ticks_ok, markers={}).passed is True

    ticks_bad = _ticks([0, 1, 1, 1, 1, 1, 0])  # span duration 0.4s > 0.25
    assert evaluate_expectation(exp, ticks_bad, markers={}).passed is False


def test_becomes_passes_and_fails():
    ticks = _ticks([0, 0, 1, 1, 1])  # becomes 1 at t=0.2
    exp = parse_expectation(
        {"id": "E", "signal": "widget.outputs.value", "becomes": 1, "within_s": 0.05, "of": "marker.entry"}, where="t",
    )
    assert evaluate_expectation(exp, ticks, markers={"entry": 0.2}).passed is True
    assert evaluate_expectation(exp, ticks, markers={"entry": 1.0}).passed is False


def test_becomes_needs_a_real_edge_not_the_first_sample():
    """A series that merely starts at the value has not become it: the first
    sample has no predecessor, so it is never a transition."""
    exp = parse_expectation(
        {"id": "E", "signal": "widget.outputs.value", "becomes": 1, "within_s": 0.5, "of": "marker.entry"}, where="t",
    )
    starts_at_value = evaluate_expectation(exp, _ticks([1, 1, 1]), markers={"entry": 0.0})
    assert starts_at_value.passed is False
    assert "never became" in starts_at_value.detail
    leaves_and_returns = evaluate_expectation(exp, _ticks([1, 0, 1]), markers={"entry": 0.2})
    assert leaves_and_returns.passed is True


def test_becomes_never_reaching_value_fails():
    ticks = _ticks([0, 0, 0])
    exp = parse_expectation(
        {"id": "E", "signal": "widget.outputs.value", "becomes": 1, "within_s": 0.05, "of": "marker.entry"}, where="t",
    )
    result = evaluate_expectation(exp, ticks, markers={"entry": 0.1})
    assert result.passed is False
    assert "never became" in result.detail


def test_becomes_reports_its_window_s_symmetric_around_the_anchor():
    """The timeline overlay's own input: `becomes ... within_s ... of:`
    passes on `abs(actual - expected) <= within_s` (evaluate_expectation's
    own condition) -- so its window is symmetric around the anchor, not a
    one-sided deadline extending only forward."""
    ticks = _ticks([0, 0, 1, 1, 1])
    exp = parse_expectation(
        {"id": "E", "signal": "widget.outputs.value", "becomes": 1, "within_s": 0.05, "of": "marker.entry"}, where="t",
    )
    result = evaluate_expectation(exp, ticks, markers={"entry": 0.2})
    assert result.window_s == pytest.approx((0.15, 0.25))


def test_a_reference_to_an_undeclared_marker_names_itself():
    """UT-C3-4: `marker.<name>` resolves; a missing marker names itself."""
    ticks = _ticks([0, 1, 1])
    exp = parse_expectation(
        {"id": "E", "signal": "widget.outputs.value", "becomes": 1, "within_s": 0.05, "of": "marker.no_such_marker"},
        where="t",
    )
    with pytest.raises(AuthoringError, match="no_such_marker"):
        evaluate_expectation(exp, ticks, markers={"entry": 0.1})


def test_never_passes_and_fails():
    exp = parse_expectation({"id": "E", "signal": "widget.outputs.value", "never": 9}, where="t")
    assert evaluate_expectation(exp, _ticks([0, 1, 2]), markers={}).passed is True
    assert evaluate_expectation(exp, _ticks([0, 9, 2]), markers={}).passed is False


def test_count_passes_and_fails():
    exp = parse_expectation({"id": "E", "signal": "widget.outputs.value", "count": {"value": 1, "times": 2}}, where="t")
    # transitions into 1: at index 1 and index 4 -> 2 total
    assert evaluate_expectation(exp, _ticks([0, 1, 1, 0, 1]), markers={}).passed is True
    assert evaluate_expectation(exp, _ticks([0, 1, 1, 1, 1]), markers={}).passed is False


def test_count_does_not_count_the_first_sample_as_an_edge():
    exp = parse_expectation({"id": "E", "signal": "widget.outputs.value", "count": {"value": 1, "times": 1}}, where="t")
    # starts at 1, leaves, returns once -> one real rising edge, not two
    assert evaluate_expectation(exp, _ticks([1, 1, 0, 1]), markers={}).passed is True
    assert evaluate_expectation(exp, _ticks([1, 1, 1, 1]), markers={}).passed is False


def test_between_passes_and_fails():
    exp = parse_expectation({"id": "E", "signal": "widget.outputs.value", "between": [0.0, 5.0]}, where="t")
    assert evaluate_expectation(exp, _ticks([0, 2, 5]), markers={}).passed is True
    assert evaluate_expectation(exp, _ticks([0, 2, 6]), markers={}).passed is False


def test_monotonic_passes_and_fails():
    exp_dec = parse_expectation({"id": "E", "signal": "widget.outputs.value", "monotonic": "decreasing"}, where="t")
    assert evaluate_expectation(exp_dec, _ticks([5, 4, 3, 3, 1]), markers={}).passed is True
    assert evaluate_expectation(exp_dec, _ticks([5, 4, 6, 1]), markers={}).passed is False


# ---------------------------------------------------------------------------
# Markers -- resolution reuses the same evaluator (SS9.1)
# ---------------------------------------------------------------------------


def test_resolve_constant_anchor():
    marker = Marker(id="m", at=ConstantAnchor(seconds=7.32, source="offline"))
    assert resolve_marker(marker, _ticks([0, 0])) == 7.32


def test_resolve_becomes_anchor():
    """UT-C3-7 (1/2): a predicate-form anchor resolves to the first tick
    satisfying it."""
    marker = Marker(id="m", at=BecomesAnchor(signal="widget.outputs.value", value=1))
    ticks = _ticks([0, 0, 1, 1])
    assert resolve_marker(marker, ticks) == pytest.approx(0.2)


def test_resolve_becomes_anchor_never_satisfied_raises():
    marker = Marker(id="m", at=BecomesAnchor(signal="widget.outputs.value", value=9))
    with pytest.raises(AuthoringError, match="m"):
        resolve_marker(marker, _ticks([0, 0, 1]))


def test_resolve_crosses_anchor_rising_and_falling():
    """UT-C3-7 (2/2)."""
    rising = Marker(id="r", at=CrossesAnchor(signal="widget.outputs.value", threshold=0.5, direction="rising"))
    falling = Marker(id="f", at=CrossesAnchor(signal="widget.outputs.value", threshold=0.5, direction="falling"))
    ticks = _ticks([0.0, 0.2, 0.6, 1.0, 0.4, 0.1])
    assert resolve_marker(rising, ticks) == pytest.approx(0.2)  # index 2: 0.2 -> 0.6
    assert resolve_marker(falling, ticks) == pytest.approx(0.4)  # index 4: 1.0 -> 0.4


def test_resolve_markers_resolves_every_declared_marker():
    scenario = load_scenario(_FIXTURES / "fixture_v2.yaml")
    ticks = _ticks([0.0, 0.2, 0.6, 1.0])
    resolved = resolve_markers(scenario, ticks)
    assert resolved["entry_s"] == 4.80
    assert resolved["crossing"] == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# evaluate_scenario -- the full wiring, markers resolved once, up front
# ---------------------------------------------------------------------------


def test_evaluate_scenario_resolves_markers_and_evaluates_expect_entries():
    scenario = load_scenario(_FIXTURES / "fixture_v2.yaml")
    ticks = _ticks([0.0, 0.2, 0.6, 1.0])
    results = evaluate_scenario(scenario, ticks)
    assert len(results) == 1
    assert results[0].id == "EXP-1"
    # fixture_v2's EXP-1 is `equals: 1, always: true`; the crafted ticks
    # above are not all == 1, so this exercises the failing path end to end.
    assert results[0].passed is False


# ---------------------------------------------------------------------------
# The YAML on/off/none-vs-enum-name authoring trap (Expectation's own
# docstring) -- a real enum field, quoted vs unquoted, end to end.
# ---------------------------------------------------------------------------


def _warning_state_cls():
    from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

    fdp = descriptor_pb2.FileDescriptorProto()
    fdp.name = "c3_expect_warning_state.proto"
    fdp.package = "adas_sim.test.c3expect"
    fdp.syntax = "proto3"
    enum = fdp.enum_type.add()
    enum.name = "WarningState"
    for name, number in [("OFF", 0), ("NORMAL", 1)]:
        value = enum.value.add()
        value.name, value.number = name, number
    msg = fdp.message_type.add()
    msg.name = "SideState"
    f = msg.field.add()
    f.name, f.number, f.type, f.type_name = (
        "warning", 1, descriptor_pb2.FieldDescriptorProto.TYPE_ENUM, ".adas_sim.test.c3expect.WarningState",
    )
    pool = descriptor_pool.DescriptorPool()
    pool.Add(fdp)
    return message_factory.GetMessageClass(pool.FindMessageTypeByName("adas_sim.test.c3expect.SideState"))


def _warning_ticks(states: list[int]):
    side_state_cls = _warning_state_cls()
    return tuple(
        Tick(
            index=i, t_ns=i * _PERIOD_NS, dt_ns=_PERIOD_NS,
            ports={
                "widget.outputs": PortValue(
                    name="widget.outputs", origin="simulated", message=side_state_cls(warning=v), t_ns=i * _PERIOD_NS,
                ),
            },
            pose=Pose2D(x_m=0.0, y_m=0.0, yaw_rad=0.0),
        )
        for i, v in enumerate(states)
    )


def test_quoted_off_matches_the_real_enum_name():
    ticks = _warning_ticks([0, 0, 0])
    exp = parse_expectation({"id": "E", "signal": "widget.outputs.warning", "equals": "OFF", "always": True}, where="t")
    assert evaluate_expectation(exp, ticks, markers={}).passed is True


def test_unquoted_off_is_the_yaml_boolean_trap_and_never_matches():
    """The gotcha `Expectation`'s docstring names, proven rather than just
    asserted: YAML reads a bare `off` as `False`, and `False != 'OFF'` --
    an unquoted `equals: off` can never pass against a real enum field
    named OFF, even when the signal genuinely is OFF every tick."""
    ticks = _warning_ticks([0, 0, 0])
    raw = yaml.safe_load("id: E\nsignal: widget.outputs.warning\nequals: off\nalways: true\n")
    assert raw["equals"] is False  # confirms the trap fired during YAML parsing itself
    exp = parse_expectation(raw, where="t")
    assert evaluate_expectation(exp, ticks, markers={}).passed is False
