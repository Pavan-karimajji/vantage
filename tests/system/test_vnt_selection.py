# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`IMP-0046`: the system tests of input selection, `SYT-SEL-01` to `SYT-SEL-13` (`VANTAGE_Test_Spec.md` section 4),
one test per case `.cN` (a case over every lab case is parametrized, each parameter a lab case). Every assertion
message names the FAIL side the spec states for the case.

The re-run refSync of a run is the `refSync` the engine wrote for it (`S.refSync` in the engine-run recording); it
names what the engine handed the stage. A run is found by its control's `measurement_counter`, which every
refSync of the run copies. Where the spec leaves a step open it is chosen so the case can fail:
- "the middle" run of `SYT-SEL-02` is the first run at or after the middle whose recorded entry for `Z` is not 0;
- "its step" is the logging time of the run's refSync in the engine-run recording.

A test whose lab output, library or tool is missing skips with the reason printed (`tests/support`).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.engine_runs import (
    Recording, case_params, edited_payload, event_entries, exact_cases, point_at_recording, ran, tap_case,
)
from tests.support.lab_cases import edit_recording, lab_case

_UNKNOWN_TIME = 0


def _setup_of(case) -> dict:
    return json.loads(case.setup.read_text(encoding="utf-8"))


def _entries_by_run(recording: Recording, stage: str) -> dict[int, dict[str, tuple[int, int]]]:
    """`{run counter: {port: (measurement_counter, source_timestamp_us)}}` of `S.refSync`, keyed by the refSync's own
    `measurement_counter` (the control's)."""
    found = {}
    for _i, _t, ref_sync in recording.decoded(f"{stage}.refSync"):
        found[ref_sync.sig_header.measurement_counter] = {
            e.port: (e.measurement_counter, e.source_timestamp_us) for e in ref_sync.inputs}
    return found


def _run_steps(recording: Recording, stage: str) -> dict[int, int]:
    """`{run counter: logging time of that run's refSync}`: the step the run is in."""
    return {m.sig_header.measurement_counter: t for _i, t, m in recording.decoded(f"{stage}.refSync")}


def _topic_of_input(stage: dict, port: str) -> str:
    wired = next(i for i in stage["inputs"] if i["port"] == port)
    return f"source.{wired['producer_port']}" if wired["producer"] == "source" else f"{wired['producer']}.{wired['producer_port']}"


def _after(candidate: int, counter: int) -> bool:
    return counter != 0 and 0 < (candidate - counter) % 2**32 < 2**31


# ---- SYT-SEL-01 .. 02 ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("topology", "scenario", "name"), case_params(exact_cases()))
def test_syt_sel_01_c1_inputs_are_chosen_by_the_recorded_refsync(tmp_path, topology, scenario, name):  # SYT-SEL-01.c1
    case = lab_case(topology, name, scenario)
    _run, produced = ran(case, tmp_path, "run")
    recorded = Recording(case.recording)
    for stage in [s["name"] for s in _setup_of(case)["stages"] if s["mode"] == "simulate"]:
        mine, theirs = _entries_by_run(produced, stage), _entries_by_run(recorded, stage)
        assert mine, f"SYT-SEL-01.c1: {topology}/{scenario}/{name} stage {stage}: the engine wrote no refSync"
        for counter, entries in mine.items():
            assert counter in theirs, f"SYT-SEL-01.c1: {topology}/{scenario}/{name} stage {stage} run {counter}: no recorded refSync"
            for port, entry in entries.items():
                assert theirs[counter].get(port) == entry, (
                    f"SYT-SEL-01.c1: any difference: {topology}/{scenario}/{name} stage {stage} run {counter} input {port}: "
                    f"re-run {entry}, recorded {theirs[counter].get(port)}")


def test_syt_sel_02_c1_an_entry_of_zero_gives_an_empty_input_and_no_badge(tmp_path):  # SYT-SEL-02.c1
    case = lab_case("running_example", "all_simulated")
    recorded = Recording(case.recording)
    runs = [(i, m.sig_header.measurement_counter, {e.port: e.measurement_counter for e in m.inputs})
            for i, _t, m in recorded.decoded("B.refSync")]
    middle = next(position for position, (_i, _c, entries) in enumerate(runs)
                  if position >= len(runs) // 2 and entries.get("in_Z", 0) != 0)
    target_index, target_counter, _entries = runs[middle]

    def zero_z(messages):
        edited = []
        for index, (topic, time_ns, payload) in enumerate(messages):
            if index == target_index and topic == "B.refSync":
                def mutate(message):
                    for entry in message.inputs:
                        if entry.port == "in_Z":
                            entry.measurement_counter = 0
                payload = edited_payload(recorded, topic, payload, mutate)
            edited.append((topic, time_ns, payload))
        return edited

    edited = edit_recording(case, tmp_path / "zero_z.mcap", zero_z)
    use = lambda setup: point_at_recording(setup, edited)  # noqa: E731
    tapped = tap_case(case, tmp_path, "tap", change=use)
    run, produced = ran(case, tmp_path, "engine", change=use)
    assert tapped.returncode == 0, f"SYT-SEL-02.c1: the tapped run failed: {tapped.stderr[-300:]}"

    entry = _entries_by_run(produced, "B")[target_counter]["in_Z"]
    assert entry[0] == 0, f"SYT-SEL-02.c1: a non-zero entry for Z in B's run {target_counter}: {entry}"
    step_time = _run_steps(produced, "B")[target_counter]
    steps = {s["time_ns"]: i for i, s in enumerate(tapped.steps)}
    index = steps[step_time]
    for kind in ("KIND_FALLBACK", "KIND_READINESS_TIMEOUT"):
        before = tapped.badge_count(kind, "B.in_Z", step_index=index - 1) if index else 0
        assert tapped.badge_count(kind, "B.in_Z", step_index=index) == before, (
            f"SYT-SEL-02.c1: a badge: {kind} on B.in_Z rose in the step of run {target_counter}")


# ---- SYT-SEL-03 .. 05 ----------------------------------------------------------------------------------------------

def test_syt_sel_03_c1_a_dropped_sample_falls_back_to_the_newest_present_below_it(tmp_path):  # SYT-SEL-03.c1
    case = lab_case("running_example", "all_simulated", "missing_sample")
    _run, produced = ran(case, tmp_path, "run")
    recorded = Recording(case.recording)
    checked = 0
    for stage in ("B", "E"):
        for counter, entries in _entries_by_run(recorded, stage).items():
            wanted = entries["in_Y"][0]
            if wanted in (20, 21, 22):
                got = _entries_by_run(produced, stage)[counter]["in_Y"][0]
                checked += 1
                assert got == 19, f"SYT-SEL-03.c1: stage {stage} run {counter} wants source.Y {wanted}: the entry names {got}, not 19"
    assert checked > 0, "SYT-SEL-03.c1: no run names source.Y 20, 21 or 22, so the case could not fail"


def _beyond_the_gap(case, recorded: Recording, stages=("B", "E")):
    """`[(stage, run counter, wanted, newest present below it)]` of the runs whose wanted `source.Y` counter is more
    than `fallback_max_gap` past the newest present one."""
    gap = _setup_of(case)["fallback_max_gap"]
    present = sorted(recorded.counters("source.Y"))
    found = []
    for stage in stages:
        for counter, entries in _entries_by_run(recorded, stage).items():
            wanted = entries["in_Y"][0]
            below = [c for c in present if not _after(c, wanted)]
            if wanted and below and (wanted - max(below)) % 2**32 > gap:
                found.append((stage, counter, wanted, max(below)))
    return found


def test_syt_sel_04_c1_beyond_the_gap_the_time_rule_picks(tmp_path):  # SYT-SEL-04.c1
    case = lab_case("running_example", "all_simulated", "missing_run")
    _run, produced = ran(case, tmp_path, "run")
    recorded = Recording(case.recording)
    runs = _beyond_the_gap(case, recorded)
    assert runs, "SYT-SEL-04.c1: no run wants a counter beyond fallback_max_gap, so the case could not fail"
    samples = [(i, t, m.sig_header.measurement_counter, m.sig_header.source_timestamp_us)
               for i, t, m in recorded.decoded("source.Y")]
    for stage, counter, wanted, _found in runs:
        step_time = _run_steps(produced, stage)[counter]
        control_time = next(m.sig_header.source_timestamp_us for _i, _t, m in produced.decoded(f"{stage}.control")
                            if m.sig_header.measurement_counter == counter)
        arrived = [s for s in samples if s[1] <= step_time]
        usable = [s for s in arrived if _UNKNOWN_TIME in (control_time, s[3]) or s[3] <= control_time]
        expected = usable[-1][2] if usable else 0
        got = _entries_by_run(produced, stage)[counter]["in_Y"][0]
        assert got == expected, (
            f"SYT-SEL-04.c1: stage {stage} run {counter} wants {wanted}: the entry names {got}, the time rule's sample is {expected}")


def test_syt_sel_05_c1_a_fallback_beyond_the_gap_is_logged(tmp_path):  # SYT-SEL-05.c1
    case = lab_case("running_example", "all_simulated", "missing_run")
    run, _produced = ran(case, tmp_path, "run")
    recorded = Recording(case.recording)
    expected = sorted((stage, "in_Y", wanted, found, wanted - found) for stage, _c, wanted, found in _beyond_the_gap(case, recorded))
    assert expected, "SYT-SEL-05.c1: no run wants a counter beyond fallback_max_gap, so the case could not fail"
    logged = sorted((e["stage"], e["port"], int(e["wanted"]), int(e["found"]), int(e["gap"]))
                    for e in event_entries(run.events, "fallback_beyond_gap"))
    assert logged == expected, f"SYT-SEL-05.c1: a missing, extra or wrong entry: logged {logged}, expected {expected}"


# ---- SYT-SEL-06 .. 08 ----------------------------------------------------------------------------------------------

def test_syt_sel_06_c1_no_recorded_refsync_means_the_time_rule(tmp_path):  # SYT-SEL-06.c1
    case = lab_case("running_example", "all_simulated", "no_ref_sync")
    _run, produced = ran(case, tmp_path, "run")
    setup = _setup_of(case)
    checked = 0
    for stage in [s for s in setup["stages"] if s["mode"] == "simulate"]:
        name = stage["name"]
        control_time = {m.sig_header.measurement_counter: m.sig_header.source_timestamp_us
                        for _i, _t, m in produced.decoded(f"{name}.control")}
        for counter, step_time in _run_steps(produced, name).items():
            for port in [p["name"] for p in stage["ports"] if p["dir"] == "req" and p["name"] != "control"]:
                topic = _topic_of_input(stage, port)
                arrived = [(m.sig_header.measurement_counter, m.sig_header.source_timestamp_us)
                           for _i, t, m in produced.decoded(topic) if t <= step_time]
                usable = [a for a in arrived if _UNKNOWN_TIME in (control_time[counter], a[1]) or a[1] <= control_time[counter]]
                expected = usable[-1][0] if usable else 0
                got = _entries_by_run(produced, name)[counter][port][0]
                checked += 1
                assert got == expected, (
                    f"SYT-SEL-06.c1: stage {name} run {counter} input {port}: the entry names {got}, the newest sample "
                    f"logged at or before the step and not after the control is {expected} (a sample logged after the "
                    f"step, or an older one)")
    assert checked > 0, "SYT-SEL-06.c1: no run, so the case could not fail"


def test_syt_sel_07_c1_a_previous_cycle_input_never_sees_the_current_step(tmp_path):  # SYT-SEL-07.c1
    case = lab_case("feedback", "all_simulated")
    recorded = Recording(case.recording)
    refsyncs = [t for t in recorded.topics() if t.endswith(".refSync")]
    without = edit_recording(case, tmp_path / "without_refsync.mcap", lambda ms: [m for m in ms if m[0] not in refsyncs],
                             exclude_topics=refsyncs)
    _run, produced = ran(case, tmp_path, "run", change=lambda setup: point_at_recording(setup, without))
    committed_at = {m.sig_header.measurement_counter: t for _i, t, m in produced.decoded("B.out")}
    runs = _entries_by_run(produced, "A")
    steps = _run_steps(produced, "A")
    named = 0
    for counter, entries in runs.items():
        wanted = entries["in_B"][0]
        if wanted == 0:
            continue
        named += 1
        assert committed_at[wanted] < steps[counter], (
            f"SYT-SEL-07.c1: A's run {counter} names B's sample {wanted}, committed in the same step ({steps[counter]} ns)")
    assert named > 0, "SYT-SEL-07.c1: no A run names a B sample, so the case could not fail"


def test_syt_sel_08_c1_no_sample_found_gives_an_empty_input(tmp_path):  # SYT-SEL-08.c1
    case = lab_case("running_example", "all_simulated")
    recorded = Recording(case.recording)
    y_positions = [i for i, _t, _p in recorded.of("source.Y")]
    first_five = set(y_positions[:5])
    cut = edit_recording(case, tmp_path / "cut.mcap", lambda ms: [m for i, m in enumerate(ms) if i not in first_five])
    _run, produced = ran(case, tmp_path, "run", change=lambda setup: point_at_recording(setup, cut))
    first_left = Recording(cut).counters("source.Y")[0]
    checked = 0
    for stage in ("B", "E"):
        recorded_entries = _entries_by_run(recorded, stage)
        for counter, entries in _entries_by_run(produced, stage).items():
            wanted = recorded_entries[counter]["in_Y"][0]
            # `SYS-0027` (`D28 (5)`): the runs whose recorded entry for Y names a removed sample, not the runs
            # before the first remaining sample's logging time -- a car run may read a sample logged after its
            # control, and is handed it.
            if wanted and _after(first_left, wanted):
                checked += 1
                assert entries["in_Y"][0] == 0, (
                    f"SYT-SEL-08.c1: a non-zero entry: stage {stage} run {counter} wants removed Y {wanted} and is "
                    f"handed {entries['in_Y'][0]}")
    assert checked > 0, "SYT-SEL-08.c1: no run names a removed Y sample, so the case could not fail"


# ---- SYT-SEL-09 ----------------------------------------------------------------------------------------------------

_BADGE_KINDS = ("KIND_FALLBACK", "KIND_READINESS_TIMEOUT")
# `SYT-SEL-09` names its cases in its steps: every exact case beside the drills that diverge (`D28 (1)`).
_BADGE_CASES = [*exact_cases(), ("running_example", "missing_sample", "all_simulated"),
                ("running_example", "missing_run", "all_simulated"), ("running_example", "no_ref_sync", "all_simulated")]


def _expected_badges(case, tapped, limit0: bool) -> dict[tuple[str, str, int], int]:
    """`{(kind, subject, step time ns): count}` the table of `ARCH §6` gives for the selections of the tapped run: a
    run's input whose recorded entry names a sample the re-run entry does not is a fallback (with a timeout first
    when the producer is a simulated stage whose sample was not committed by then); every input of a run with no
    recorded refSync is a fallback; an entry of 0 and a matched entry raise nothing."""
    setup = _setup_of(case)
    produced, recorded = Recording(tapped.recording), Recording(case.recording)
    simulated = {s["name"] for s in setup["stages"] if s["mode"] == "simulate"}
    committed = {name: {m.sig_header.measurement_counter: t for _i, t, m in produced.decoded(f"{name}.out")} for name in simulated}
    expected: dict[tuple[str, str, int], int] = {}

    def add(kind: str, subject: str, time_ns: int) -> None:
        expected[(kind, subject, time_ns)] = expected.get((kind, subject, time_ns), 0) + 1

    for stage in setup["stages"]:
        name = stage["name"]
        if name not in simulated:
            continue
        theirs = _entries_by_run(recorded, name)
        steps = _run_steps(produced, name)
        for counter, mine in _entries_by_run(produced, name).items():
            for port in [p["name"] for p in stage["ports"] if p["dir"] == "req" and p["name"] != "control"]:
                if port not in mine:
                    continue
                wanted = theirs.get(counter, {}).get(port, (None,))[0] if counter in theirs else None
                if wanted == 0:
                    continue
                if wanted is not None and mine[port][0] == wanted:
                    continue
                producer = next(i["producer"] for i in stage["inputs"] if i["port"] == port)
                if wanted is not None and producer in simulated and committed[producer].get(wanted, steps[counter] + 1) > steps[counter]:
                    add("KIND_READINESS_TIMEOUT", f"{name}.{port}", steps[counter])
                add("KIND_FALLBACK", f"{name}.{port}", steps[counter])
    return expected


def _badge_increments(tapped) -> dict[tuple[str, str, int], int]:
    found: dict[tuple[str, str, int], int] = {}
    previous: dict[tuple[str, str], int] = {}
    for step in tapped.steps:
        for badge in step["badges"]:
            if badge["kind"] not in _BADGE_KINDS:
                continue
            key = (badge["kind"], badge["subject"])
            grew = badge["count"] - previous.get(key, 0)
            previous[key] = badge["count"]
            if grew:
                found[(badge["kind"], badge["subject"], step["time_ns"])] = grew
    return found


def _badges_are_the_tables(tmp_path, topology: str, scenario: str, name: str, *, limit0: bool = False) -> None:
    case = lab_case(topology, name, scenario)
    tapped = tap_case(case, tmp_path, "tap", change=(lambda s: s.update(readiness_limit_steps=0)) if limit0 else None)
    assert tapped.returncode == 0, f"SYT-SEL-09.c1: {topology}/{scenario}/{name}: the run failed: {tapped.stderr[-300:]}"
    expected = _expected_badges(case, tapped, limit0)
    if limit0:
        assert any(kind == "KIND_READINESS_TIMEOUT" for kind, _s, _t in expected), (
            "SYT-SEL-09.c1: late_consumer at limit 0 expects no timeout, so the case could not fail")
    found = _badge_increments(tapped)
    missing = sorted(set(expected) - set(found))
    extra = sorted(set(found) - set(expected))
    wrong = sorted(k for k in set(expected) & set(found) if expected[k] != found[k])
    assert not (missing or extra or wrong), (
        f"SYT-SEL-09.c1: {topology}/{scenario}/{name}: a missing {missing[:3]}, extra {extra[:3]} or misplaced {wrong[:3]} badge "
        f"(kind, subject, step time ns)")


@pytest.mark.parametrize(("topology", "scenario", "name"), case_params(_BADGE_CASES))
def test_syt_sel_09_c1_selection_outcomes_raise_their_badges(tmp_path, topology, scenario, name):  # SYT-SEL-09.c1
    _badges_are_the_tables(tmp_path, topology, scenario, name)


def test_syt_sel_09_c1_selection_outcomes_raise_their_badges_at_readiness_limit_0(tmp_path):  # SYT-SEL-09.c1
    _badges_are_the_tables(tmp_path, "late_consumer", "base", "all_simulated", limit0=True)


# ---- SYT-SEL-10 .. 13 ----------------------------------------------------------------------------------------------

def _lower_x_counter(recorded: Recording, from_sample: int, by: int):
    """The messages of the recording with `source.X`'s `measurement_counter` lowered by `by` from its
    `from_sample`-th sample on, its `cycle_counter` unchanged."""
    first = [i for i, _t, _p in recorded.of("source.X")][from_sample - 1]

    def edit(messages):
        edited = []
        for index, (topic, time_ns, payload) in enumerate(messages):
            if topic == "source.X" and index >= first:
                def mutate(message):
                    message.sig_header.measurement_counter -= by
                payload = edited_payload(recorded, topic, payload, mutate)
            edited.append((topic, time_ns, payload))
        return edited
    return edit


def test_syt_sel_10_c1_identity_broken_is_raised_on_the_port_whose_counter_went_back(tmp_path):  # SYT-SEL-10.c1
    case = lab_case("running_example", "all_simulated")
    recorded = Recording(case.recording)
    edited = edit_recording(case, tmp_path / "counter_back.mcap", _lower_x_counter(recorded, 100, 5))
    tapped = tap_case(case, tmp_path, "tap", change=lambda setup: point_at_recording(setup, edited))
    assert tapped.returncode == 0, f"SYT-SEL-10.c1: the run failed: {tapped.stderr[-300:]}"
    raised = tapped.badges("KIND_IDENTITY_BROKEN")
    assert raised == {"source.X": 1}, (
        f"SYT-SEL-10.c1: none, more than one, or a badge on another port (a downstream input or output): {raised}")
    hundredth = recorded.of("source.X")[99][1]
    first_step = next(step for step in tapped.steps
                      if any(b["kind"] == "KIND_IDENTITY_BROKEN" and b["subject"] == "source.X" for b in step["badges"]))
    assert first_step["time_ns"] == hundredth, (
        f"SYT-SEL-10.c1: another step: raised at {first_step['time_ns']} ns, the 100th sample is at {hundredth} ns")


@pytest.mark.parametrize(("topology", "scenario", "name"), case_params(exact_cases()))
def test_syt_sel_10_c2_identity_broken_is_never_raised_in_an_exact_case(tmp_path, topology, scenario, name):  # SYT-SEL-10.c2
    tapped = tap_case(lab_case(topology, name, scenario), tmp_path, "tap")
    assert tapped.returncode == 0, f"SYT-SEL-10.c2: {topology}/{scenario}/{name}: the run failed: {tapped.stderr[-300:]}"
    assert tapped.badges("KIND_IDENTITY_BROKEN") == {}, (
        f"SYT-SEL-10.c2: {topology}/{scenario}/{name}: any: {tapped.badges('KIND_IDENTITY_BROKEN')}")


def test_syt_sel_11_c1_a_counter_jump_is_one_gap_and_no_reset(tmp_path):  # SYT-SEL-11.c1
    run, _produced = ran(lab_case("running_example", "all_simulated", "counter_jump"), tmp_path, "run")
    gaps = [e for e in event_entries(run.events, "counter_gap") if e["port"] == "source.X"]
    resets = [e for e in event_entries(run.events, "counter_reset") if e["port"] == "source.X"]
    assert (len(gaps), len(resets)) == (1, 0), f"SYT-SEL-11.c1: another count: {len(gaps)} gaps, {len(resets)} resets on source.X"


def _restart_x(recorded: Recording, from_sample: int):
    """The messages of the recording with `source.X`'s counters restarted at 1 from its `from_sample`-th sample."""
    first = [i for i, _t, _p in recorded.of("source.X")][from_sample - 1]

    def edit(messages):
        edited, next_counter = [], 1
        for index, (topic, time_ns, payload) in enumerate(messages):
            if topic == "source.X" and index >= first:
                number = next_counter

                def mutate(message, number=number):
                    message.sig_header.measurement_counter = number
                    message.sig_header.cycle_counter = number
                payload = edited_payload(recorded, topic, payload, mutate)
                next_counter += 1
            edited.append((topic, time_ns, payload))
        return edited
    return edit


def test_syt_sel_11_c2_a_restarted_counter_is_one_reset_and_no_identity_broken(tmp_path):  # SYT-SEL-11.c2
    case = lab_case("running_example", "all_simulated")
    restarted = edit_recording(case, tmp_path / "restarted.mcap", _restart_x(Recording(case.recording), 100))
    use = lambda setup: point_at_recording(setup, restarted)  # noqa: E731
    run, _produced = ran(case, tmp_path, "engine", change=use)
    tapped = tap_case(case, tmp_path, "tap", change=use)
    resets = [e for e in event_entries(run.events, "counter_reset") if e["port"] == "source.X"]
    assert len(resets) == 1, f"SYT-SEL-11.c2: another count: {len(resets)} resets on source.X"
    assert tapped.badge_count("KIND_IDENTITY_BROKEN", "source.X") == 0, "SYT-SEL-11.c2: KIND_IDENTITY_BROKEN on source.X"


def test_syt_sel_12_c1_a_counter_wrap_is_consecutive(tmp_path):  # SYT-SEL-12.c1
    case = lab_case("running_example", "all_simulated", "counter_wrap")
    run, _produced = ran(case, tmp_path, "engine")
    tapped = tap_case(case, tmp_path, "tap")
    assert 0xFFFFFFFF in Recording(case.recording).counters("source.X"), "SYT-SEL-12.c1: the recording never reaches 0xFFFFFFFF"
    entries = [e for kind in ("counter_gap", "counter_reset") for e in event_entries(run.events, kind) if e["port"] == "source.X"]
    assert not entries, f"SYT-SEL-12.c1: any entry, in particular a gap of 1 at the wrap: {entries}"
    assert tapped.badges("KIND_IDENTITY_BROKEN") == {}, f"SYT-SEL-12.c1: KIND_IDENTITY_BROKEN: {tapped.badges('KIND_IDENTITY_BROKEN')}"


def test_syt_sel_12_c2_a_rewritten_sample_after_the_wrap_shows_one_gap(tmp_path):  # SYT-SEL-12.c2
    case = lab_case("running_example", "all_simulated", "counter_wrap")
    recorded = Recording(case.recording)
    samples = recorded.decoded("source.X")
    wrap = next(k for k, (_i, _t, m) in enumerate(samples) if m.sig_header.measurement_counter == 0xFFFFFFFF)
    after_index = samples[wrap + 1][0]

    def carry_3(messages):
        edited = list(messages)
        topic, time_ns, payload = edited[after_index]
        edited[after_index] = (topic, time_ns, edited_payload(
            recorded, topic, payload, lambda message: setattr(message.sig_header, "measurement_counter", 3)))
        return edited

    edited = edit_recording(case, tmp_path / "carry_3.mcap", carry_3)
    run, _produced = ran(case, tmp_path, "engine", change=lambda setup: point_at_recording(setup, edited))
    gaps = [e for e in event_entries(run.events, "counter_gap") if e["port"] == "source.X"]
    assert len(gaps) == 1, f"SYT-SEL-12.c2: none, so the check could not have failed (or another count): {len(gaps)} gaps on source.X"


def _wrap_without_ones(tmp_path: Path):
    case = lab_case("running_example", "all_simulated", "counter_wrap")
    recorded = Recording(case.recording)
    drop = {i for i, _t, m in recorded.decoded("source.X") if m.sig_header.measurement_counter in (0xFFFFFFFF, 1, 2)}
    cut = edit_recording(case, tmp_path / "cut.mcap", lambda ms: [m for i, m in enumerate(ms) if i not in drop])
    return case, recorded, cut


def _runs_wanting_1_or_2(case, recorded: Recording):
    setup = _setup_of(case)
    found = []
    for stage in [s for s in setup["stages"] if s["mode"] == "simulate"]:
        for port in [i["port"] for i in stage["inputs"] if i["producer"] == "source" and i["producer_port"] == "X"]:
            for counter, entries in _entries_by_run(recorded, stage["name"]).items():
                if entries.get(port, (0,))[0] in (1, 2):
                    found.append((stage["name"], port, counter, entries[port][0]))
    return found


def test_syt_sel_13_c1_the_gap_counts_the_wrap_as_one_step(tmp_path):  # SYT-SEL-13.c1
    case, recorded, cut = _wrap_without_ones(tmp_path)
    runs = _runs_wanting_1_or_2(case, recorded)
    run, _produced = ran(case, tmp_path, "gap1", change=lambda s: (point_at_recording(s, cut), s.update(fallback_max_gap=1)))
    assert runs, "SYT-SEL-13.c1: no such run at all"
    logged = sorted((e["stage"], e["port"], int(e["wanted"]), int(e["found"]), int(e["gap"]))
                    for e in event_entries(run.events, "fallback_beyond_gap"))
    expected = sorted((stage, port, wanted, 0xFFFFFFFE, 2 if wanted == 1 else 3) for stage, port, _c, wanted in runs)
    assert logged == expected, (
        f"SYT-SEL-13.c1: a gap of 3 for 1 or of 4 for 2, or a missing entry: logged {logged[:4]}, expected {expected[:4]}")


def test_syt_sel_13_c2_within_the_gap_there_is_no_entry_and_the_sample_is_fffffffe(tmp_path):  # SYT-SEL-13.c2
    case, recorded, cut = _wrap_without_ones(tmp_path)
    runs = _runs_wanting_1_or_2(case, recorded)
    assert runs, "SYT-SEL-13.c2: no such run at all"
    run, produced = ran(case, tmp_path, "gap3", change=lambda s: (point_at_recording(s, cut), s.update(fallback_max_gap=3)))
    assert not event_entries(run.events, "fallback_beyond_gap"), (
        f"SYT-SEL-13.c2: an entry (a run wanting 2 at gap 4): {event_entries(run.events, 'fallback_beyond_gap')[:2]}")
    for stage, port, counter, _wanted in runs:
        got = _entries_by_run(produced, stage)[counter][port][0]
        assert got == 0xFFFFFFFE, f"SYT-SEL-13.c2: stage {stage} run {counter}: the entry names {got:#x}, not 0xFFFFFFFE"
