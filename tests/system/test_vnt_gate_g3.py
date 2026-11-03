# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`IMP-0043`: gate `G3`, `SYT-EQO-01` and `SYT-THR-01` (`VANTAGE_Test_Spec.md` section 1), one test per lab case
`.cN` (`SYT-THR-01` one per case and N). Every assertion message names the FAIL side the spec states for the case.

Where the spec leaves a step open it is chosen so the case can fail:
- the "step" of a difference is the position of the message's logging time among the engine-run recording's distinct
  logging times, the convention of `test_vnt_equal_outputs.py`;
- the compared topics of `SYT-EQO-01` are each simulated stage's `pro` ports except `refSync` (data outputs and
  `compState`), never a `measured` stage's;
- a reproduced message is paired with the recorded message of the same topic and the same
  `sig_header.measurement_counter`; one with no counterpart is a difference, and every pair goes through the lab's
  `equal_outputs`;
- `running_example` `base` `jump` (the one case with `jump_to_ms`) runs on `F-TAP` with a jump from 500 ms to 1500 ms;
  a stage's reproduced messages logged at a step where the tap shows its `KIND_WARMING_UP` count grow are left out;
  each simulated stage must have a compared message, and some stage one at or after the jump. A stage with memory
  stays warming up to the end after a jump (`D28 (4)`, `SYT-STP-05.c1`), so all its post-jump outputs are left out;
- every other case also requires each topic's reproduced counters to equal its recorded counters, in order; in the
  jump case the reproduced counters before the jump are the recording's first ones, and those compared at or after it
  the recording's from the first of them on, none dropped;
- a topic whose recorded counters repeat is a difference, since pairing by counter could not hold;
- `SYT-THR-01` also requires both recordings to log the same topics at the same logging times in the same file order
  (`SYS-0039`: every port of every step);
- the `--threads 1` run of `SYT-THR-01` is made once per case and shared across its N.

A test whose lab output, library or tool is missing skips with the reason printed (`tests/support`).
"""

from __future__ import annotations

import json

import pytest

from tests.support.engine_runs import (
    Recording, case_params, compare_recordings, exact_cases, instants, lab_compare, ran, simulated_names, tap_case,
)
from tests.support.lab_cases import LabCase, lab_case, lab_root

JUMP = (500, 1500)  # ms: `running_example` `base` `jump`


def _load(topology: str, scenario: str, name: str) -> LabCase:
    return lab_case(topology, name, scenario)


def _jumps(case: LabCase) -> bool:
    return bool(case.case_entry.get("jump_to_ms"))


def _run(case: LabCase, directory, label: str, threads: int | None = None) -> tuple[Recording, list[str], object]:
    """The case run on `F-ENGINE`, or on `F-TAP` with the jump when the case has one: `(recording, events, tap)`."""
    if _jumps(case):
        tapped = tap_case(case, directory, label, threads=threads, jump=JUMP)
        assert tapped.returncode == 0, f"{case.topology}/{case.scenario}/{case.case}: the tap run failed: {tapped.stderr[-400:]}"
        return Recording(tapped.recording), tapped.events, tapped
    run, recording = ran(case, directory, label, threads=threads)
    return recording, run.events, None


def _step(produced: Recording, time_ns: int) -> int:
    return instants(produced).index(time_ns)


# ---- SYT-EQO-01 ----------------------------------------------------------------------------------------------------

def _warming_up(tapped) -> dict[str, set[int]]:
    """`{stage: {step time}}` at which the tap shows the stage's `KIND_WARMING_UP` count grow."""
    seen: dict[str, set[int]] = {}
    previous: dict[str, int] = {}
    for step in tapped.steps:
        for badge in step["badges"]:
            if badge["kind"] == "KIND_WARMING_UP":
                if badge["count"] > previous.get(badge["subject"], 0):
                    seen.setdefault(badge["subject"], set()).add(step["time_ns"])
                previous[badge["subject"]] = badge["count"]
    return seen


def _differences(case: LabCase, produced: Recording, recorded: Recording,
                 tapped=None) -> tuple[list[str], dict[str, int], dict[str, int]]:
    """`(differences, compared per stage, compared at or after the jump per stage)` of a run against the recording:
    each difference as `topology/scenario/case: stage port step N: why`. `tapped` is the jump case's tap run."""
    compare, messages = lab_compare()
    setup = json.loads(case.setup.read_text(encoding="utf-8"))
    skipped = _warming_up(tapped) if tapped is not None else {}
    jump_to_ns = JUMP[1] * 1_000_000
    where = f"{case.topology}/{case.scenario}/{case.case}"
    found: list[str] = []
    compared: dict[str, int] = {}
    after_jump: dict[str, int] = {}
    for stage in [s for s in setup["stages"] if s["mode"] == "simulate"]:
        name = stage["name"]
        compared[name] = 0
        for port in [p["name"] for p in stage["ports"] if p["dir"] == "pro" and p["name"] != "refSync"]:
            topic = f"{name}.{port}"
            recorded_counters = recorded.counters(topic)
            if len(set(recorded_counters)) != len(recorded_counters):
                found.append(f"{where}: {name} {port}: a counter repeats in the recording, so pairing by counter cannot hold")
            theirs: dict[int, bytes] = {}
            for _i, _t, payload in recorded.of(topic):
                theirs.setdefault(recorded.decode(topic, payload).sig_header.measurement_counter, payload)
            schema, descriptor_set = recorded.schemas.get(topic) or produced.schemas[topic]
            factory = messages.MessageFactory(descriptor_set)
            counters = []
            timed: list[tuple[int, int]] = []  # (logging time, counter) of each compared message
            for _i, t, payload in produced.of(topic):
                counter = produced.decode(topic, payload).sig_header.measurement_counter
                if t in skipped.get(name, ()):
                    continue
                counters.append(counter)
                timed.append((t, counter))
                step = _step(produced, t)
                if counter not in theirs:
                    found.append(f"{where}: {name} {port} step {step}: no recorded message of counter {counter}")
                    continue
                result = compare.equal_outputs([theirs[counter]], [payload], factory, schema)
                if not result.equal:
                    found.append(f"{where}: {name} {port} step {step}: counter {counter}: {result.reason}")
                compared[name] += 1
                if tapped is not None and t >= jump_to_ns:
                    after_jump[name] = after_jump.get(name, 0) + 1
            if tapped is None and counters != recorded.counters(topic):
                found.append(f"{where}: {name} {port}: reproduced counters {counters[:4]}... "
                             f"differ from recorded {recorded.counters(topic)[:4]}...")
            if tapped is not None:
                before = [c for t, c in timed if t < jump_to_ns]
                after = [c for t, c in timed if t >= jump_to_ns]
                if before != recorded_counters[: len(before)]:
                    found.append(f"{where}: {name} {port}: reproduced counters before the jump {before[:4]}... are not "
                                 f"the recording's first {len(before)}")
                if after and (after[0] not in recorded_counters
                              or after != recorded_counters[recorded_counters.index(after[0]):]):
                    found.append(f"{where}: {name} {port}: reproduced counters after the jump {after[:4]}... are not "
                                 f"the recording's from counter {after[0]} on")
    return found, compared, after_jump


@pytest.mark.parametrize(("topology", "scenario", "name"), case_params(exact_cases()))
def test_syt_eqo_01_c1_every_exact_case_equals_the_fake_car(tmp_path, topology, scenario, name):  # SYT-EQO-01.c1
    case = _load(topology, scenario, name)
    produced, _events, tapped = _run(case, tmp_path, "run")
    found, compared, after_jump = _differences(case, produced, Recording(case.recording), tapped)
    assert compared, f"SYT-EQO-01.c1: {topology}/{scenario}/{name}: no simulated stage, so the case could not fail"
    assert all(compared.values()), (
        f"SYT-EQO-01.c1: {topology}/{scenario}/{name}: a simulated stage with no compared message, so the case could "
        f"not fail: {compared}")
    if tapped is not None:
        assert after_jump, (
            f"SYT-EQO-01.c1: {topology}/{scenario}/{name}: no stage compared at or after the jump, so the jump could not "
            f"fail: {compared}")
    assert not found, f"SYT-EQO-01.c1: any difference ({len(found)}); first: {found[0]}"


def test_syt_eqo_01_c2_no_ref_sync_differs_from_the_fake_car(tmp_path):  # SYT-EQO-01.c2
    case = lab_case("running_example", "all_simulated", "no_ref_sync")
    produced, _events, tapped = _run(case, tmp_path, "run")
    found, _compared, _after_jump = _differences(case, produced, Recording(case.recording), tapped)
    assert found, "SYT-EQO-01.c2: the comparison finds none, so the comparison could not have failed"


# ---- SYT-THR-01 ----------------------------------------------------------------------------------------------------

def _thread_pairs() -> list[tuple[str, str, str, int]]:
    """`(topology, scenario, case, N)` for every exact case and N from 2 to its number of simulated stages."""
    pairs = []
    for topology, scenario, name in exact_cases():
        setup = lab_root() / "lab" / topology / f"{scenario}.{name}.run.json"
        if not setup.is_file():
            continue
        count = sum(1 for stage in json.loads(setup.read_text(encoding="utf-8"))["stages"] if stage["mode"] == "simulate")
        pairs.extend((topology, scenario, name, n) for n in range(2, count + 1))
    return pairs


def _thread_params():
    pairs = _thread_pairs()
    if not pairs:
        return [pytest.param(None, None, None, None, id="no-lab-catalogue",
                             marks=pytest.mark.skip(reason=f"lab not built: no run setup under {lab_root() / 'lab'}"))]
    return [pytest.param(*pair, id="/".join(map(str, pair))) for pair in pairs]


@pytest.fixture(scope="module")
def one_thread(tmp_path_factory):
    """`--threads 1` runs, one per case, made on first use and shared across the case's N (never across cases)."""
    made: dict[tuple[str, str, str], tuple[Recording, list[str]]] = {}

    def get(case: LabCase) -> tuple[Recording, list[str]]:
        key = (case.topology, case.scenario, case.case)
        if key not in made:
            directory = tmp_path_factory.mktemp("_".join(key))
            recording, events, _tap = _run(case, directory, "one", threads=1)
            made[key] = (recording, events)
        return made[key]

    return get


def _first_difference_text(first: Recording, second: Recording, diffs: list[str]) -> str:
    """`port` and `step` of the first difference `compare_recordings` found."""
    topic = diffs[0].split(":", 1)[0]
    compare, messages = lab_compare()
    schema, descriptor_set = first.schemas.get(topic) or second.schemas[topic]
    mine, theirs = first.of(topic), second.of(topic)
    result = compare.equal_outputs([p for _i, _t, p in mine], [p for _i, _t, p in theirs], messages.MessageFactory(descriptor_set), schema)
    index = result.first_difference
    if index is None:
        return f"port {topic}, step unknown ({diffs[0]})"
    return f"port {topic}, step {_step(first, mine[index][1])} ({result.reason})"


@pytest.mark.parametrize(("topology", "scenario", "name", "threads"), _thread_params())
def test_syt_thr_01_c1_n_threads_give_equal_outputs_to_one(tmp_path, one_thread, topology, scenario, name, threads):  # SYT-THR-01.c1
    case = _load(topology, scenario, name)
    assert threads <= len(simulated_names(case)), "SYT-THR-01.c1: N above the number of simulated stages"
    single, single_events = one_thread(case)
    many, many_events, _tap = _run(case, tmp_path, "many", threads=threads)
    assert single.topics(), f"SYT-THR-01.c1: {topology}/{scenario}/{name}: the --threads 1 run holds no topic, so the case could not fail"
    diffs = compare_recordings(single, many)
    assert not diffs, (f"SYT-THR-01.c1: {topology}/{scenario}/{name} N={threads}: any difference ({len(diffs)}); first: "
                       f"{_first_difference_text(single, many, diffs)}")
    order = [(t, topic) for topic, t, _p in single.messages]
    other_order = [(t, topic) for topic, t, _p in many.messages]
    first = next((i for i, (x, y) in enumerate(zip(order, other_order)) if x != y), min(len(order), len(other_order)))
    assert order == other_order, (
        f"SYT-THR-01.c1: {topology}/{scenario}/{name} N={threads}: message {first} is logged at another step or on "
        f"another port: --threads 1 {order[first:first + 1]} / --threads {threads} {other_order[first:first + 1]}")
    for line, (one, other) in enumerate(zip(single_events, many_events)):
        assert one == other, (f"SYT-THR-01.c1: {topology}/{scenario}/{name} N={threads}: event log line {line} differs: "
                              f"--threads 1 {one!r} / --threads {threads} {other!r}")
    assert len(single_events) == len(many_events), (
        f"SYT-THR-01.c1: {topology}/{scenario}/{name} N={threads}: event logs of {len(single_events)} and {len(many_events)} "
        f"lines; first extra: {(single_events + many_events)[min(len(single_events), len(many_events))]!r}")
