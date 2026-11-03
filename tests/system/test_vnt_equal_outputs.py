# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`IMP-0048`: the system tests of threads and of equal outputs, `SYT-THR-02`, `SYT-THR-03` and `SYT-EQO-02` to
`SYT-EQO-05` (`VANTAGE_Test_Spec.md` sections 6 and 7), one test per case `.cN` (a case over every lab case is
parametrized, each parameter a lab case). Every assertion message names the FAIL side the spec states for the case.
`SYT-THR-01` and `SYT-EQO-01` are gate `G3` (`IMP-0043`), not here.

Where the spec leaves a step open it is chosen so the case can fail:
- the "step" of `SYT-EQO-02` and `SYT-EQO-03` is the step number the event log carries: the position of the run's
  logging time among the engine-run recording's distinct logging times;
- the first difference of `SYT-EQO-02.c1` is the first, in step order, stage order and the order of the setup's
  `pro` ports, at which a RUN run's output differs from the recorded run of the same `measurement_counter` through
  the lab's comparator (a `refSync` through the engine's own rule, counter and time only, `SYS-0044`);
- the "middle" run of `SYT-EQO-03.c2` is `B`'s run at the middle of its runs.

A test whose lab output, library or tool is missing skips with the reason printed (`tests/support`).
"""

from __future__ import annotations

import json

import pytest

from tests.support.engine_runs import (
    Recording, case_params, catalogue, edited_payload, event_entries, exact_cases, instants, lab_compare, point_at_recording,
    probe_copy, ran, run_case, simulated_names, stage_of, step_starting_instants, tap_case,
)
from tests.support.lab_cases import edit_recording, lab_case


def _setup_of(case) -> dict:
    return json.loads(case.setup.read_text(encoding="utf-8"))


# ---- SYT-THR-02, 03 ------------------------------------------------------------------------------------------------

def _probe_log(log) -> list[dict[str, str]]:
    lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return [dict(part.split("=", 1) for part in line.split() if "=" in part) for line in lines]


def _all_probes(case, directory, log, spin_ms: int):
    """A setup change that puts a separate probe copy in place of each stage's library."""
    libraries = {stage: probe_copy(directory, stage, log, spin_ms) for stage in simulated_names(case)}

    def change(setup: dict) -> None:
        for name, library in libraries.items():
            stage_of(setup, name)["impl"]["path"] = library.as_posix()
    return change


def _thread_ids(tmp_path, threads: int | None) -> set[str]:
    case = lab_case("diamond", "all_simulated")
    log = tmp_path / f"threads_{threads}.log"
    run = run_case(case, tmp_path / f"t{threads}", "run", change=_all_probes(case, tmp_path / f"p{threads}", log, 3), threads=threads)
    assert run.returncode == 0, f"the diamond run failed (threads {threads}): {run.stderr[-300:]}"
    return {entry["thread"] for entry in _probe_log(log)}


def test_syt_thr_02_c1_one_thread_by_default(tmp_path):  # SYT-THR-02.c1
    ids = _thread_ids(tmp_path, None)
    assert len(ids) == 1, f"SYT-THR-02.c1: two or more thread ids without --threads: {sorted(ids)}"


def test_syt_thr_02_c2_two_threads_are_seen_with_threads_2(tmp_path):  # SYT-THR-02.c2
    ids = _thread_ids(tmp_path, 2)
    assert len(ids) >= 2, f"SYT-THR-02.c2: one id with --threads 2, so the probe could not have seen a second thread: {sorted(ids)}"


def _overlaps(entries: list[dict[str, str]]) -> int:
    """How many calls entered while another was inside, in the order the probe's log was written."""
    inside = overlaps = 0
    for entry in entries:
        if entry["event"] == "enter":
            overlaps += 1 if inside else 0
            inside += 1
        else:
            inside -= 1
    return overlaps


def _fan_out_with_probes(tmp_path, *, one_copy: bool) -> list[dict[str, str]]:
    case = lab_case("fan_out", "all_simulated")
    log = tmp_path / "calls.log"
    shared = probe_copy(tmp_path / "shared", "BC", log, 5) if one_copy else None
    own = {} if one_copy else {name: probe_copy(tmp_path / "own", name, log, 5) for name in ("B", "C")}

    def change(setup: dict) -> None:
        for name in ("B", "C"):
            stage_of(setup, name)["impl"]["path"] = (shared if one_copy else own[name]).as_posix()

    run = run_case(case, tmp_path, "run", change=change, threads=2)
    assert run.returncode == 0, f"the fan_out run failed: {run.stderr[-300:]}"
    return _probe_log(log)


def test_syt_thr_03_c1_one_copy_is_never_called_twice_at_once(tmp_path):  # SYT-THR-03.c1
    entries = _fan_out_with_probes(tmp_path, one_copy=True)
    assert [e for e in entries if e["event"] == "enter"], "SYT-THR-03.c1: the probe was never called, so the case could not fail"
    assert _overlaps(entries) == 0, f"SYT-THR-03.c1: an overlap: {_overlaps(entries)} calls entered while another was inside"


def test_syt_thr_03_c2_two_copies_overlap(tmp_path):  # SYT-THR-03.c2
    entries = _fan_out_with_probes(tmp_path, one_copy=False)
    assert _overlaps(entries) >= 1, "SYT-THR-03.c2: none, so the probe could not have seen two calls at once"


# ---- SYT-EQO-02 ----------------------------------------------------------------------------------------------------

def _first_difference(case, produced: Recording, recorded: Recording) -> tuple[int, str, str] | None:
    """`(step number, stage, port)` of the first RUN-run output that differs from the recorded run of the same
    `measurement_counter`, or None."""
    compare, messages = lab_compare()
    setup = _setup_of(case)
    times = instants(produced)
    restart = {}
    for stage in simulated_names(case):
        restart[stage] = {m.sig_header.measurement_counter: m.op_mode == m.RESTART for _i, _t, m in produced.decoded(f"{stage}.control")}
    for step, time_ns in enumerate(times):
        for stage in [s for s in setup["stages"] if s["mode"] == "simulate"]:
            name = stage["name"]
            for port in [p["name"] for p in stage["ports"] if p["dir"] == "pro"]:
                topic = f"{name}.{port}"
                for _i, t, payload in produced.of(topic):
                    if t != time_ns:
                        continue
                    counter = produced.decode(topic, payload).sig_header.measurement_counter
                    if restart[name].get(counter, False):
                        continue
                    theirs = [p for _a, _b, p in recorded.of(topic) if recorded.decode(topic, p).sig_header.measurement_counter == counter]
                    if not theirs:
                        continue
                    schema, descriptor_set = recorded.schemas[topic]
                    if port == "refSync":
                        mine_m, their_m = produced.decode(topic, payload), recorded.decode(topic, theirs[0])
                        same = [(e.port, e.measurement_counter, e.source_timestamp_us) for e in mine_m.inputs] == \
                               [(e.port, e.measurement_counter, e.source_timestamp_us) for e in their_m.inputs]
                    else:
                        same = compare.equal_outputs([theirs[0]], [payload], messages.MessageFactory(descriptor_set), schema).equal
                    if not same:
                        return step, name, port
    return None


def test_syt_eqo_02_c1_the_first_divergence_is_the_first_difference(tmp_path):  # SYT-EQO-02.c1
    case = lab_case("running_example", "all_simulated", "no_ref_sync")
    run, produced = ran(case, tmp_path, "run")
    expected = _first_difference(case, produced, Recording(case.recording))
    assert expected is not None, "SYT-EQO-02.c1: the comparator finds no difference, so the case could not fail"
    logged = event_entries(run.events, "first_divergence")
    assert len(logged) == 1, f"SYT-EQO-02.c1: missing (or more than one) first_divergence entry: {run.events[:3]}"
    got = (int(logged[0]["step"]), logged[0]["stage"], logged[0]["port"])
    assert got == expected, f"SYT-EQO-02.c1: the entry names {got}, the comparator's first difference is {expected}"


@pytest.mark.parametrize(("topology", "scenario", "name"), case_params(exact_cases()))
def test_syt_eqo_02_c2_an_exact_case_reports_no_divergence(tmp_path, topology, scenario, name):  # SYT-EQO-02.c2
    run, _produced = ran(lab_case(topology, name, scenario), tmp_path, "run")
    assert event_entries(run.events, "first_divergence") == [], (
        f"SYT-EQO-02.c2: {topology}/{scenario}/{name}: any: {event_entries(run.events, 'first_divergence')}")


# ---- SYT-EQO-03 ----------------------------------------------------------------------------------------------------

def test_syt_eqo_03_c1_a_jump_does_not_make_the_refsync_diverge(tmp_path):  # SYT-EQO-03.c1
    case = lab_case("diamond", "all_simulated")
    tapped = tap_case(case, tmp_path, "tap", jump=(500, 1000))
    assert tapped.returncode == 0, f"SYT-EQO-03.c1: the run failed: {tapped.stderr[-300:]}"
    times = [s["time_ns"] for s in tapped.steps]
    assert any(b - a >= 400_000_000 for a, b in zip(times, times[1:])), "SYT-EQO-03.c1: the run never jumped, so the case could not fail"
    assert event_entries(tapped.events, "first_divergence") == [], (
        f"SYT-EQO-03.c1: one is reported: {event_entries(tapped.events, 'first_divergence')}")


def test_syt_eqo_03_c2_a_changed_recorded_source_time_is_a_divergence_on_the_refsync(tmp_path):  # SYT-EQO-03.c2
    case = lab_case("running_example", "cut_c")
    recorded = Recording(case.recording)
    runs = recorded.decoded("B.refSync")
    index, _time, message = runs[len(runs) // 2]
    counter = message.sig_header.measurement_counter
    port = message.inputs[0].port

    def change_time(messages):
        edited = list(messages)
        topic, time_ns, payload = edited[index]

        def mutate(ref_sync):
            next(e for e in ref_sync.inputs if e.port == port).source_timestamp_us += 1

        edited[index] = (topic, time_ns, edited_payload(recorded, topic, payload, mutate))
        return edited

    edited = edit_recording(case, tmp_path / "edited.mcap", change_time)
    run, produced = ran(case, tmp_path, "run", change=lambda setup: point_at_recording(setup, edited))
    step_time = next(t for _i, t, m in produced.decoded("B.refSync") if m.sig_header.measurement_counter == counter)
    step = instants(produced).index(step_time)
    logged = event_entries(run.events, "first_divergence")
    assert len(logged) == 1, f"SYT-EQO-03.c2: none is reported: {run.events[:3]}"
    got = (int(logged[0]["step"]), logged[0]["stage"], logged[0]["port"])
    assert got == (step, "B", "refSync"), f"SYT-EQO-03.c2: none, or another port first: {got}, expected {(step, 'B', 'refSync')}"


# ---- SYT-EQO-04 ----------------------------------------------------------------------------------------------------

def test_syt_eqo_04_c1_a_divergence_does_not_fail_the_engine_run(tmp_path):  # SYT-EQO-04.c1
    diverging = lab_case("running_example", "all_simulated", "no_ref_sync")
    clean = lab_case("running_example", "cut_c")
    run_a, produced_a = ran(diverging, tmp_path / "a", "run")
    run_b, _produced_b = ran(clean, tmp_path / "b", "run")
    assert event_entries(run_a.events, "first_divergence"), "SYT-EQO-04.c1: no_ref_sync diverges nowhere, so the case could not fail"
    assert run_a.returncode == run_b.returncode == 0, (
        f"SYT-EQO-04.c1: a fail outcome: no_ref_sync exits {run_a.returncode}, cut_c {run_b.returncode}")
    starting = step_starting_instants(json.loads(diverging.setup.read_text(encoding="utf-8")), Recording(diverging.recording))
    steps = instants(produced_a)
    assert len(steps) == len(starting.times), (
        f"SYT-EQO-04.c1: another number of steps: no_ref_sync ran {len(steps)} steps for {len(starting.times)} distinct "
        f"reception times of its step-starting messages")


# ---- SYT-EQO-05 ----------------------------------------------------------------------------------------------------

def _dropped_y(scenario: str) -> set[int]:
    """The `source.Y` counters the catalogue's `scenario` removes from the recording."""
    declared = next(s for s in catalogue()["running_example"]["scenarios"] if s["name"] == scenario)
    return {d["counter"] for d in declared["recording"]["drop_sample"] if d["port"] == "source.Y"}


@pytest.mark.parametrize("scenario", ["missing_sample", "missing_run"])
def test_syt_eqo_05_c1_a_lost_inputs_divergence_comes_no_earlier_than_the_loss(tmp_path, scenario):  # SYT-EQO-05.c1
    case = lab_case("running_example", "all_simulated", scenario)
    dropped = _dropped_y(scenario)
    tapped = tap_case(case, tmp_path, "tap")
    assert tapped.returncode == 0, f"SYT-EQO-05.c1: {scenario}: the run failed: {tapped.stderr[-300:]}"
    produced, recorded = Recording(tapped.recording), Recording(case.recording)
    step_times = instants(produced)
    losses = []  # (step, stage): a run whose recorded refSync names a dropped Y sample
    for stage in ("B", "E"):
        for _i, _t, ref_sync in recorded.decoded(f"{stage}.refSync"):
            counter = ref_sync.sig_header.measurement_counter
            if not any(e.port == "in_Y" and e.measurement_counter in dropped for e in ref_sync.inputs):
                continue
            run_time = next(t for _j, t, m in produced.decoded(f"{stage}.refSync") if m.sig_header.measurement_counter == counter)
            losses.append((step_times.index(run_time), stage, run_time))
    assert losses, f"SYT-EQO-05.c1: {scenario}: no run names a dropped Y sample, so the case could not fail"
    step, stage, run_time = min(losses)
    logged = event_entries(tapped.events, "first_divergence")
    assert logged, f"SYT-EQO-05.c1: {scenario}: no entry"
    assert int(logged[0]["step"]) >= step, (
        f"SYT-EQO-05.c1: {scenario}: an entry at an earlier step: step {logged[0]['step']}, the first loss is step {step} ({stage})")

    def fallbacks(upto: int) -> int:
        return tapped.badge_count("KIND_FALLBACK", f"{stage}.in_Y", step_index=upto)

    at = next(i for i, entry in enumerate(tapped.steps) if entry["time_ns"] == run_time)
    assert fallbacks(at) - (fallbacks(at - 1) if at > 0 else 0) >= 1, (
        f"SYT-EQO-05.c1: {scenario}: no KIND_FALLBACK on {stage}.in_Y at the loss step {step}")
