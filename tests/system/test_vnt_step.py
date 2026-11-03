# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`IMP-0047`: the system tests of the engine step, `SYT-STP-01` to `SYT-STP-06` (`VANTAGE_Test_Spec.md` section 5),
one test per case `.cN` (a case over every lab case is parametrized, each parameter a lab case). Every assertion
message names the FAIL side the spec states for the case.

Where the spec leaves a step open it is chosen so the case can fail:
- the instants of `SYT-STP-01.c1` and `.c2` are those of `step_starting_instants` (`tests/support/engine_runs.py`):
  the reception times of the step-starting messages the run setup declares (`ARCH §7`, `D28 (2)`) and `E`'s ticks,
  which the engine puts at the whole recording's first reception time plus whole periods, up to the recording's
  last reception time;
- a stage's runs after the jump (`SYT-STP-05.c1`) are those whose step is at or after `jump_to_ms`; the first of
  them is the RESTART run, which is never compared, so the stage is warming up through the runs before the first
  later run whose `out` and `compState` equal the recorded run of the same `measurement_counter` (a stage whose
  outputs never equal them is badged through its last run).

A test whose lab output, library or tool is missing skips with the reason printed (`tests/support`).
"""

from __future__ import annotations

import json
import re

import pytest

from tests.support.engine_runs import (
    Recording, case_params, instants, lab_compare, lab_setups, ran, run_case, stage_of, step_starting_instants, tap_case,
)
from tests.support.lab_cases import lab_case

_KINDS = ("output_counter_break", "fallback_beyond_gap", "counter_gap", "counter_reset", "stalled_trigger",
          "eviction_miss", "first_divergence")
_LINE = re.compile(r"^event=degrade step=(\d+) entry=(" + "|".join(_KINDS) + r")( .*)?$")


def _setup_of(case) -> dict:
    return json.loads(case.setup.read_text(encoding="utf-8"))


def _jump(case) -> tuple[int, int]:
    return 500, int(case.case_entry["jump_to_ms"])


# ---- SYT-STP-01 ----------------------------------------------------------------------------------------------------

_CUT_C_STARTERS = frozenset({"source.X", "source.Y", "source.Z", "C.out", "C.refSync", "C.compState",
                             "A.control", "B.control", "D.control", "E.control"})


def test_syt_stp_01_c1_the_steps_are_the_step_starting_messages_reception_times(tmp_path):  # SYT-STP-01.c1
    case = lab_case("running_example", "cut_c")
    tapped = tap_case(case, tmp_path, "tap")
    assert tapped.returncode == 0, f"SYT-STP-01.c1: the run failed: {tapped.stderr[-300:]}"
    assert [s["step"] for s in tapped.steps] == list(range(len(tapped.steps))), "SYT-STP-01.c1: a gap in the step numbers"
    starters = step_starting_instants(_setup_of(case), Recording(case.recording))
    assert starters.topics == _CUT_C_STARTERS, (
        f"SYT-STP-01.c1: the helper chose other topics than the spec lists: {sorted(starters.topics ^ _CUT_C_STARTERS)}")
    times = [s["time_ns"] for s in tapped.steps]
    expected = starters.times
    assert times == expected, (
        f"SYT-STP-01.c1: a missing or extra step, a gap, or a wrong time: {len(times)} steps for {len(expected)} reception "
        f"times; missing {sorted(set(expected) - set(times))[:3]}, extra {sorted(set(times) - set(expected))[:3]}")


def test_syt_stp_01_c2_a_clock_adds_its_tick_instants(tmp_path):  # SYT-STP-01.c2
    case = lab_case("running_example", "cut_c")
    period = 7_000_000

    def clock_e(setup: dict) -> None:
        stage = stage_of(setup, "E")
        stage["trigger"] = ""
        stage["clock_period_ns"] = period

    tapped = tap_case(case, tmp_path, "tap", change=clock_e)
    assert tapped.returncode == 0, f"SYT-STP-01.c2: the run failed: {tapped.stderr[-300:]}"
    clocked = _setup_of(case)
    clock_e(clocked)
    expected = step_starting_instants(clocked, Recording(case.recording)).times
    times = [s["time_ns"] for s in tapped.steps]
    assert times == expected, (
        f"SYT-STP-01.c2: a tick instant without its step: missing {sorted(set(expected) - set(times))[:3]}, "
        f"extra {sorted(set(times) - set(expected))[:3]}")


# ---- SYT-STP-02 ----------------------------------------------------------------------------------------------------

def test_syt_stp_02_c1_a_run_triggered_by_an_output_runs_in_that_step(tmp_path):  # SYT-STP-02.c1
    case = lab_case("fan_out", "all_simulated")
    _run, produced = ran(case, tmp_path, "run", change=lambda setup: stage_of(setup, "B").update(trigger="in_A"))
    output_time = {m.sig_header.measurement_counter: t for _i, t, m in produced.decoded("A.out")}
    pairs = 0
    for _i, control_time, control in produced.decoded("B.control"):
        counter = control.sig_header.measurement_counter
        pairs += 1
        assert counter in output_time, f"SYT-STP-02.c1: B's control {counter} has no A output carrying its counter"
        assert control_time == output_time[counter], (
            f"SYT-STP-02.c1: a later one: B's control {counter} at {control_time} ns, A's output at {output_time[counter]} ns")
    assert pairs > 0, "SYT-STP-02.c1: B has no control, so the case could not fail"


# ---- SYT-STP-03 .. 05 ----------------------------------------------------------------------------------------------

def _jumped(tmp_path):
    case = lab_case("running_example", "jump")
    tapped = tap_case(case, tmp_path, "tap", jump=_jump(case))
    assert tapped.returncode == 0, f"the jumped run failed: {tapped.stderr[-300:]}"
    return case, tapped


def test_syt_stp_03_c1_after_a_jump_no_older_sample_is_named(tmp_path):  # SYT-STP-03.c1
    case, tapped = _jumped(tmp_path)
    jump_to_ns = _jump(case)[1] * 1_000_000
    produced, recorded = Recording(tapped.recording), Recording(case.recording)
    setup = _setup_of(case)
    topic_of = {}
    for stage in setup["stages"]:
        for wired in stage["inputs"]:
            topic_of[(stage["name"], wired["port"])] = (
                f"source.{wired['producer_port']}" if wired["producer"] == "source" else f"{wired['producer']}.{wired['producer_port']}")
    logged_at = {topic: {} for topic in set(topic_of.values())}
    for topic in logged_at:
        for _i, t, m in recorded.decoded(topic):
            logged_at[topic][m.sig_header.measurement_counter] = t
    checked = 0
    for stage in [s["name"] for s in setup["stages"] if s["mode"] == "simulate"]:
        for _i, step_time, ref_sync in produced.decoded(f"{stage}.refSync"):
            if step_time < jump_to_ns:
                continue
            for entry in ref_sync.inputs:
                if entry.measurement_counter == 0:
                    continue
                checked += 1
                at = logged_at[topic_of[(stage, entry.port)]].get(entry.measurement_counter)
                assert at is not None and at >= jump_to_ns, (
                    f"SYT-STP-03.c1: one is: stage {stage} at {step_time} ns names {entry.port} {entry.measurement_counter}, "
                    f"logged at {at} ns, before jump_to_ms")
    assert checked > 0, "SYT-STP-03.c1: no run after the jump names a sample, so the case could not fail"


def test_syt_stp_04_c1_a_jump_keeps_the_step_numbers(tmp_path):  # SYT-STP-04.c1
    case, tapped = _jumped(tmp_path)
    numbers = [s["step"] for s in tapped.steps]
    assert numbers == list(range(len(numbers))), (
        f"SYT-STP-04.c1: a restart at 0, a gap or a repeat: {[(a, b) for a, b in zip(numbers, numbers[1:]) if b != a + 1][:3]}")
    times = [s["time_ns"] for s in tapped.steps]
    assert any(b - a >= _jump(case)[1] * 1_000_000 - 2 * 500_000_000 for a, b in zip(times, times[1:])), (
        "SYT-STP-04.c1: the run never jumped, so the case could not fail")


def _first_equal_run(produced: Recording, recorded: Recording, stage: str, from_ns: int) -> tuple[list[int], int | None]:
    """`(step times of the stage's runs from `from_ns`, index of the first non-RESTART run whose `out` and `compState`
    equal the recorded run of the same counter, through the lab's comparator)`."""
    compare, messages = lab_compare()
    runs = [(t, m.sig_header.measurement_counter) for _i, t, m in produced.decoded(f"{stage}.control") if t >= from_ns]
    times = [t for t, _c in runs]
    for position, (time_ns, counter) in enumerate(runs):
        if position == 0:
            continue  # the RESTART run after the jump is never compared
        equal = True
        for port in ("out", "compState"):
            topic = f"{stage}.{port}"
            mine = [p for _i, t, p in produced.of(topic) if t == time_ns]
            theirs = [p for _i, _t, p in recorded.of(topic) if recorded.decode(topic, p).sig_header.measurement_counter == counter]
            if not mine or not theirs:
                equal = False
                break
            name, descriptor_set = recorded.schemas[topic]
            equal = equal and compare.equal_outputs([theirs[0]], [mine[-1]], messages.MessageFactory(descriptor_set), name).equal
        if equal:
            return times, position
    return times, None


def test_syt_stp_05_c1_warming_up_is_badged_from_the_jump_until_the_outputs_are_equal(tmp_path):  # SYT-STP-05.c1
    case, tapped = _jumped(tmp_path)
    produced, recorded = Recording(tapped.recording), Recording(case.recording)
    jump_to_ns = _jump(case)[1] * 1_000_000
    previous: dict[str, int] = {}
    seen: dict[tuple[str, int], int] = {}
    for step in tapped.steps:
        for badge in step["badges"]:
            if badge["kind"] == "KIND_WARMING_UP":
                grew = badge["count"] - previous.get(badge["subject"], 0)
                previous[badge["subject"]] = badge["count"]
                if grew:
                    seen[(badge["subject"], step["time_ns"])] = grew
    checked = 0
    for stage in [s["name"] for s in _setup_of(case)["stages"] if s["mode"] == "simulate"]:
        times, first_equal = _first_equal_run(produced, recorded, stage, jump_to_ns)
        # A stage with memory (`B`, `D`) restarts without its state and its outputs may never equal the recorded ones: it
        # is then badged on every run after the jump.
        expected = {(stage, t): 1 for t in (times if first_equal is None else times[:first_equal])}
        found = {k: v for k, v in seen.items() if k[0] == stage and k[1] >= jump_to_ns}  # the badge before the jump is SYT-STP-05.c2's
        checked += 1
        assert found == expected, (
            f"SYT-STP-05.c1: a missing badge, or one after the first equal step: stage {stage} badged at "
            f"{sorted(t for _s, t in found)[:4]}..., expected {sorted(t for _s, t in expected)[:4]}...")
    assert checked > 0, "SYT-STP-05.c1: no simulated stage, so the case could not fail"


def test_syt_stp_05_c2_no_stage_is_warming_up_without_a_jump(tmp_path):  # SYT-STP-05.c2
    tapped = tap_case(lab_case("running_example", "cut_c"), tmp_path, "tap")
    assert tapped.returncode == 0, f"SYT-STP-05.c2: the run failed: {tapped.stderr[-300:]}"
    assert tapped.steps, "SYT-STP-05.c2: the tap printed no step"
    assert tapped.badges("KIND_WARMING_UP") == {}, f"SYT-STP-05.c2: any: {tapped.badges('KIND_WARMING_UP')}"


# ---- SYT-STP-06 ----------------------------------------------------------------------------------------------------

def parse_event_line(line: str) -> tuple[int, str]:
    """`(step, kind)` of one event log line; `ValueError` for a line whose kind is not of the closed list or that
    carries no step."""
    found = _LINE.match(line)
    if found is None:
        raise ValueError(f"not an event log line of the closed list: {line!r}")
    return int(found.group(1)), found.group(2)


_SUPERVISED = ("hang", "crash")


@pytest.mark.parametrize(("topology", "scenario", "name"),
                         case_params([c for c in lab_setups() if c[2] not in _SUPERVISED]))
def test_syt_stp_06_c1_every_event_log_line_has_a_listed_kind_and_a_step(tmp_path, topology, scenario, name):  # SYT-STP-06.c1
    run = run_case(lab_case(topology, name, scenario), tmp_path, "run")
    assert run.returncode == 0, f"SYT-STP-06.c1: {topology}/{scenario}/{name}: the run failed: {run.stderr[-300:]}"
    for line in run.events:
        try:
            parse_event_line(line)
        except ValueError as exc:
            raise AssertionError(f"SYT-STP-06.c1: a line with another kind or no step: {topology}/{scenario}/{name}: {exc}") from exc


def test_syt_stp_06_c2_a_line_of_another_kind_is_rejected():  # SYT-STP-06.c2
    with pytest.raises(ValueError):
        parse_event_line("event=degrade step=3 entry=other stage=A")
    with pytest.raises(ValueError):
        parse_event_line("event=degrade entry=counter_gap port=source.X")
    assert parse_event_line("event=degrade step=3 entry=counter_gap port=source.X from=1 to=3 missed=1") == (3, "counter_gap"), (
        "SYT-STP-06.c2: the parser rejects a line of the list, so a rejection proves nothing")
