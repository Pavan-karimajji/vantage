# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`IMP-0045`: the system tests of the orchestrator and its six rules, `SYT-ORC-01` to `SYT-ORC-12`
(`VANTAGE_Test_Spec.md` section 3), one test per case `.cN` (a case over every lab case is parametrized, each
parameter a lab case). Every assertion message names the FAIL side the spec states for the case.

A test whose lab output, library or tool is missing skips with the reason printed (`tests/support`).
`SYT-ORC-02.c1` runs `loop_no_edge`, for which the lab writes no run setup (it refuses the topology by design): the
test copies `feedback` `all_simulated`'s setup, drops `A`'s `previous_cycle` mark and points every library path at
`loop_no_edge`'s build (the same stages, inputs and periods).
"""

from __future__ import annotations

import dataclasses
import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml

from tests.support.engine_runs import (
    EngineRun, Recording, library_with_bundle, point_at_recording, run_case, run_engine, skip, stage_of,
    tap_case, tool_path,
)
from tests.support.lab_cases import LabCase, edit_recording, lab_case, lab_root

# ---- the cases of the lab ------------------------------------------------------------------------------------------

def _catalogue() -> dict[str, dict]:
    found = {}
    for path in sorted((lab_root() / "catalogue").glob("*.yaml")):
        if path.name != "provisional.yaml":
            found[path.stem] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return found


def _exact_cases() -> list[tuple[str, str, str]]:
    """`(topology, scenario, case)` of every exact case: the scenario expects `exact` and the case is not `hang` or
    `crash`, which need the supervisor (`F-CAT`)."""
    return [(topology, scenario["name"], case["name"])
            for topology, declared in _catalogue().items()
            for scenario in declared.get("scenarios", []) if scenario.get("expect", "exact") == "exact"
            for case in scenario.get("resim", []) if case["name"] not in ("hang", "crash")]


def _case_params(cases: list[tuple[str, str, str]]):
    if not cases:
        return [pytest.param(None, None, None, id="no-lab-catalogue",
                             marks=pytest.mark.skip(reason=f"lab not built: no catalogue under {lab_root() / 'catalogue'}"))]
    return [pytest.param(*case, id="/".join(case)) for case in cases]


def _controls(recording: Recording, stages) -> dict[str, list[int]]:
    return {stage: recording.counters(f"{stage}.control") for stage in stages}


def _simulated(case: LabCase) -> list[str]:
    setup = json.loads(case.setup.read_text(encoding="utf-8"))
    return [stage["name"] for stage in setup["stages"] if stage["mode"] == "simulate"]


def _ran(case: LabCase, directory: Path, label: str, **kwargs) -> tuple[EngineRun, Recording]:
    run = run_case(case, directory, label, **kwargs)
    assert run.returncode == 0, f"{case.topology}/{case.scenario}/{case.case}: the engine run failed: {run.stderr[-400:]}"
    return run, Recording(run.recording)


def _entry(recording: Recording, stage: str, port: str) -> list[tuple[int, int]]:
    """`(measurement_counter, source_timestamp_us)` of the refSync entry for `port` of every run of `stage`, in file
    order."""
    found = []
    for _i, _t, ref_sync in recording.decoded(f"{stage}.refSync"):
        entry = next((e for e in ref_sync.inputs if e.port == port), None)
        found.append((entry.measurement_counter, entry.source_timestamp_us) if entry is not None else (0, 0))
    return found


# ---- SYT-ORC-01 .. 03 ----------------------------------------------------------------------------------------------

def test_syt_orc_01_c1_a_higher_rank_run_reads_the_lower_rank_output_of_its_own_step(tmp_path):  # SYT-ORC-01.c1
    case = lab_case("running_example", "all_simulated", "no_ref_sync")
    _run, produced = _ran(case, tmp_path, "run")
    controls_a = {t for _i, t, _m in produced.decoded("A.control")}
    controls_b = {t for _i, t, _m in produced.decoded("B.control")}
    steps = sorted(controls_a & controls_b)
    assert steps, "SYT-ORC-01.c1: no step runs both A and B, so the case could not fail"

    a_output = {t: m.sig_header.measurement_counter for _i, t, m in produced.decoded("A.out")}
    b_entry = {t: (m.inputs) for _i, t, m in produced.decoded("B.refSync")}
    for step in steps:
        named = next((e.measurement_counter for e in b_entry[step] if e.port == "in_A"), None)
        assert named == a_output[step], (
            f"SYT-ORC-01.c1: step at {step} ns: B's entry for A names {named}, an older sample than A's output {a_output[step]} of that step")


def _loop_no_edge_libraries() -> dict[str, str]:
    """`{stage: library path}` of `loop_no_edge`'s build, or skip with the reason when it is missing."""
    root = lab_root()
    found = sorted((root / "conan_workarea").glob("build-sil-*/lab/loop_no_edge/index.json"))
    if not found:
        skip("lab not built: no conan_workarea/build-sil-*/lab/loop_no_edge/index.json (the loop_no_edge libraries)")
    components = json.loads(found[-1].read_text(encoding="utf-8")).get("components", {})
    libraries = {name: item["library"] for name, item in components.items()}
    missing = [path for path in libraries.values() if not Path(path).is_file()]
    if not libraries or missing:
        skip(f"lab not built: loop_no_edge libraries missing on this machine: {missing[:1] or 'none listed'}")
    return libraries


def test_syt_orc_02_c1_a_loop_without_a_previous_cycle_input_is_refused(tmp_path):  # SYT-ORC-02.c1
    libraries = _loop_no_edge_libraries()
    case = lab_case("feedback", "all_simulated")

    def make_the_loop(setup: dict) -> None:
        for stage in setup["stages"]:
            stage["impl"]["path"] = Path(libraries[stage["name"]]).as_posix()
            for wired in stage["inputs"]:
                if stage["name"] == "A":
                    wired["previous_cycle"] = False

    run = run_case(case, tmp_path, "run", change=make_the_loop)
    text = run.error_text()
    assert run.returncode != 0 and not run.started, "SYT-ORC-02.c1: it runs"
    assert "A" in text and "B" in text, f"SYT-ORC-02.c1: the error names another stage or none: {text.strip()}"


def test_syt_orc_02_c2_a_loop_with_a_previous_cycle_input_runs_to_the_recordings_end(tmp_path):  # SYT-ORC-02.c2
    case = lab_case("feedback", "all_simulated")
    run, produced = _ran(case, tmp_path, "run")
    recorded = Recording(case.recording)
    for stage in _simulated(case):
        assert len(produced.of(f"{stage}.control")) == len(recorded.of(f"{stage}.control")) > 0, (
            f"SYT-ORC-02.c2: a load error or an early stop: stage {stage} ran {len(produced.of(f'{stage}.control'))} of "
            f"{len(recorded.of(f'{stage}.control'))} recorded runs")


def _by_data_without(tmp_path: Path, remove_topic: str | None = None):
    case = lab_case("data_triggered", "by_data")
    if remove_topic is None:
        return case, None
    cut = edit_recording(case, tmp_path / "cut.mcap", lambda ms: [m for m in ms if m[0] != remove_topic], drop_topics=[remove_topic])
    return case, cut


def test_syt_orc_03_c1_a_control_trigger_without_a_recorded_control_is_refused(tmp_path):  # SYT-ORC-03.c1
    case, cut = _by_data_without(tmp_path, "T.control")
    run = run_case(case, tmp_path, "run", change=lambda s: (point_at_recording(s, cut), stage_of(s, "T").update(trigger="control")))
    text = run.error_text()
    assert run.returncode != 0 and not run.started, "SYT-ORC-03.c1: the run starts"
    assert "'T'" in text and "T.control" in text, f"SYT-ORC-03.c1: the error does not name T and T.control: {text.strip()}"


def test_syt_orc_03_c2_an_undeclared_trigger_input_is_refused(tmp_path):  # SYT-ORC-03.c2
    run = run_case(lab_case("data_triggered", "by_data"), tmp_path, "run", change=lambda s: stage_of(s, "T").update(trigger="in_Q"))
    assert run.returncode != 0 and not run.started, "SYT-ORC-03.c2: the run starts"
    assert "'T'" in run.error_text() and "in_Q" in run.error_text(), f"SYT-ORC-03.c2: the error does not name T and the input: {run.error_text().strip()}"


def test_syt_orc_03_c3_no_trigger_and_clock_0_is_refused(tmp_path):  # SYT-ORC-03.c3
    run = run_case(lab_case("data_triggered", "by_data"), tmp_path, "run",
                   change=lambda s: stage_of(s, "T").update(trigger="", clock_period_ns=0))
    assert run.returncode != 0 and not run.started, "SYT-ORC-03.c3: the run starts"
    assert "'T'" in run.error_text(), f"SYT-ORC-03.c3: the error does not name T: {run.error_text().strip()}"


def test_syt_orc_03_c4_a_trigger_and_a_clock_is_refused(tmp_path):  # SYT-ORC-03.c4
    run = run_case(lab_case("data_triggered", "by_data"), tmp_path, "run",
                   change=lambda s: stage_of(s, "T").update(clock_period_ns=10_000_000))
    assert run.returncode != 0 and not run.started, "SYT-ORC-03.c4: the run starts"
    assert "'T'" in run.error_text(), f"SYT-ORC-03.c4: the error does not name T: {run.error_text().strip()}"


# ---- SYT-ORC-04 .. 06 ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("topology", "scenario", "name"), _case_params(_exact_cases()))
def test_syt_orc_04_c1_every_exact_case_has_as_many_controls_as_recorded(tmp_path, topology, scenario, name):  # SYT-ORC-04.c1
    case = lab_case(topology, name, scenario)
    _run, produced = _ran(case, tmp_path, "run")
    recorded = Recording(case.recording)
    for stage in _simulated(case):
        mine, theirs = len(produced.of(f"{stage}.control")), len(recorded.of(f"{stage}.control"))
        assert mine == theirs, f"SYT-ORC-04.c1: {topology}/{scenario}/{name} stage {stage}: {mine} controls in the engine-run recording, {theirs} recorded"


def test_syt_orc_04_c2_a_data_triggered_stage_runs_once_per_input_sample(tmp_path):  # SYT-ORC-04.c2
    case = lab_case("data_triggered", "by_data")
    _run, produced = _ran(case, tmp_path, "run")
    samples = len(Recording(case.recording).of("source.X"))
    controls = len(produced.of("T.control"))
    assert samples > 0 and controls == samples, f"SYT-ORC-04.c2: {controls} T controls for {samples} in_X samples"


def _compstate_problems(recording: Recording, stages: list[str]) -> list[str]:
    problems = []
    for stage in stages:
        counters = [m.sig_header.cycle_counter for _i, _t, m in recording.decoded(f"{stage}.compState")]
        controls = len(recording.of(f"{stage}.control"))
        gaps = [(a, b) for a, b in zip(counters, counters[1:]) if b != a + 1]
        if gaps:
            problems.append(f"stage {stage}: cycle_counter gaps {gaps[:3]}")
        if len(counters) != controls:
            problems.append(f"stage {stage}: {len(counters)} compState messages for {controls} controls")
    return problems


@pytest.mark.parametrize(("topology", "scenario", "name"), _case_params(_exact_cases()))
def test_syt_orc_04_c3_every_exact_case_records_every_runs_compstate(tmp_path, topology, scenario, name):  # SYT-ORC-04.c3
    case = lab_case(topology, name, scenario)
    _run, produced = _ran(case, tmp_path, "run")
    problems = _compstate_problems(produced, _simulated(case))
    assert not problems, f"SYT-ORC-04.c3: {topology}/{scenario}/{name}: a gap, or another count: {problems}"


def test_syt_orc_04_c3_depth_one_on_every_port_still_records_every_runs_compstate(tmp_path):  # SYT-ORC-04.c3
    case = lab_case("running_example", "all_simulated")

    def depth_one(setup: dict) -> None:
        for stage in setup["stages"]:
            for port in stage["ports"]:
                port["buffer_depth"] = 1

    _run, produced = _ran(case, tmp_path, "run", change=depth_one)
    problems = _compstate_problems(produced, _simulated(case))
    assert not problems, f"SYT-ORC-04.c3: running_example all_simulated at depth 1: a gap, or another count: {problems}"


def test_syt_orc_05_c1_an_output_not_copying_its_controls_counter_is_logged(tmp_path):  # SYT-ORC-05.c1
    case = lab_case("running_example", "shifted", "renumber_lib")
    folder = case.setup.parent / f"{case.scenario}.{case.case}.bundles" / "A"
    if not folder.is_dir():
        skip(f"lab not built: {folder} (the shifted bundle of A) is missing")
    library = library_with_bundle(case, "A", tmp_path / "shifted_A", bundle=folder)
    run, produced = _ran(case, tmp_path, "run", change=lambda s: stage_of(s, "A")["impl"].update(path=library.as_posix()))

    control = produced.counters("A.control")
    differing = []  # (port, run index)
    for port in ("out", "compState"):
        for k, counter in enumerate(produced.counters(f"A.{port}")):
            if counter != control[k]:
                differing.append((port, k))
    assert differing, "SYT-ORC-05.c1: no output of A differs from its control's counter, so the case could not fail"
    logged = [line for line in run.events if "entry=output_counter_break" in line]
    seen = sorted((re.search(r"stage=(\S+)", line).group(1), re.search(r"port=(\S+)", line).group(1)) for line in logged)
    assert all(re.search(r"step=\d+", line) for line in logged), f"SYT-ORC-05.c1: an entry without its step: {logged[:2]}"
    assert seen == sorted(("A", port) for port, _k in differing), (
        f"SYT-ORC-05.c1: a missing entry: {len(logged)} entries for {len(differing)} listed outputs {sorted(set(differing))[:3]}...")
    assert len(produced.of("A.control")) == len(Recording(case.recording).of("A.control")), "SYT-ORC-05.c1: the run stops before the recording's end"


def test_syt_orc_06_c1_a_stages_runs_go_strictly_in_order(tmp_path):  # SYT-ORC-06.c1
    case = lab_case("late_consumer", "all_simulated")
    _run, produced = _ran(case, tmp_path, "run")
    recorded = Recording(case.recording)
    for stage in _simulated(case):
        assert produced.counters(f"{stage}.control") == recorded.counters(f"{stage}.control"), (
            f"SYT-ORC-06.c1: stage {stage}: a control out of trigger order")
        topics = {f"{stage}.control", f"{stage}.out", f"{stage}.refSync", f"{stage}.compState"}
        in_file_order = [(topic, produced.decode(topic, payload).sig_header.measurement_counter)
                         for topic, _t, payload in produced.messages if topic in topics]
        position = 0
        while position < len(in_file_order):
            topic, counter = in_file_order[position]
            assert topic == f"{stage}.control", (
                f"SYT-ORC-06.c1: stage {stage}: {topic} {counter} is not preceded by its own control: a control is out of place")
            own = in_file_order[position + 1: position + 4]
            assert sorted(own) == sorted((f"{stage}.{port}", counter) for port in ("out", "refSync", "compState")), (
                f"SYT-ORC-06.c1: stage {stage}: a control before the previous control's outputs: control {counter} is followed by {own}")
            position += 4


# ---- SYT-ORC-07, 08 ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("case_name", "case_id"), [("all_simulated", "SYT-ORC-07.c1"), ("cut_p", "SYT-ORC-07.c2")])
def test_syt_orc_07_a_run_waits_for_its_named_sample(tmp_path, case_name, case_id):  # SYT-ORC-07.c1 (all_simulated), SYT-ORC-07.c2 (cut_p)
    case = lab_case("late_consumer", case_name)
    _run, produced = _ran(case, tmp_path, "run")
    rerun, recorded = _entry(produced, "Q", "in_P"), _entry(Recording(case.recording), "Q", "in_P")
    assert rerun and len(rerun) == len(recorded), f"{case_id}: {len(rerun)} Q re-run entries, {len(recorded)} recorded"
    differing = [(k, a, b) for k, (a, b) in enumerate(zip(rerun, recorded)) if a != b]
    assert not differing, f"{case_id}: any difference (run, re-run, recorded): {differing[:3]}"


def test_syt_orc_07_c3_a_readiness_limit_of_0_times_out_a_q_run(tmp_path):  # SYT-ORC-07.c3
    case = lab_case("late_consumer", "all_simulated")
    tapped = tap_case(case, tmp_path, "tap", change=lambda s: s.update(readiness_limit_steps=0))
    assert tapped.returncode == 0, f"SYT-ORC-07.c3: the run failed: {tapped.stderr[-300:]}"
    timeouts = {subject: count for subject, count in tapped.badges("KIND_READINESS_TIMEOUT").items() if subject.startswith("Q.")}
    assert timeouts, "SYT-ORC-07.c3: no Q run raises KIND_READINESS_TIMEOUT"


def test_syt_orc_08_c1_the_recordings_end_runs_every_waiting_ticket(tmp_path):  # SYT-ORC-08.c1
    case = lab_case("late_consumer", "all_simulated")
    full = Recording(case.recording)
    p_out = {m.sig_header.measurement_counter: i for i, _t, m in full.decoded("P.out")}
    chosen = None
    for (control_index, _t, control), (ref_index, _rt, ref_sync) in zip(full.decoded("Q.control"), full.decoded("Q.refSync")):
        named = next((e.measurement_counter for e in ref_sync.inputs if e.port == "in_P"), 0)
        if named and p_out[named] > control_index:
            chosen = (control_index, ref_index, control.sig_header.measurement_counter)
            break
    assert chosen is not None, "SYT-ORC-08.c1: no Q control names a P sample logged after it, so the case could not fail"
    control_index, ref_index, counter = chosen
    # The cut keeps everything up to that Q control and the run's own recorded refSync (without it the run has
    # nothing naming a sample, and the time rule picks one); the later messages, P's among them, are gone.
    cut = edit_recording(case, tmp_path / "cut.mcap", lambda ms: [m for i, m in enumerate(ms) if i <= control_index or i == ref_index])

    def use_cut(setup: dict) -> None:
        point_at_recording(setup, cut)

    tapped = tap_case(case, tmp_path, "tap", change=use_cut)
    run, produced = _ran(case, tmp_path, "run", change=use_cut)
    assert tapped.returncode == 0 and tapped.steps, f"SYT-ORC-08.c1: the tapped run failed: {tapped.stderr[-300:]}"
    last = len(tapped.steps) - 1
    in_last = tapped.badge_count("KIND_READINESS_TIMEOUT", "Q.in_P") - tapped.badge_count("KIND_READINESS_TIMEOUT", "Q.in_P", step_index=last - 1)
    assert in_last == 1, f"SYT-ORC-08.c1: the Q run is missing, in another step, or not badged (timeouts raised in the last step: {in_last})"
    ran_at = [t for _i, t, m in produced.decoded("Q.out") if m.sig_header.measurement_counter == counter]
    assert ran_at == [tapped.steps[-1]["time_ns"]], (
        f"SYT-ORC-08.c1: the run of control {counter} is missing or in another step: logged at {ran_at}, last step at {tapped.steps[-1]['time_ns']}")


# ---- SYT-ORC-09 .. 12 ----------------------------------------------------------------------------------------------

def test_syt_orc_09_c1_a_simulated_stage_nobody_simulated_consumes_is_badged_once(tmp_path):  # SYT-ORC-09.c1
    tapped = tap_case(lab_case("measured_middle", "cut_m"), tmp_path, "tap")
    assert tapped.returncode == 0, f"SYT-ORC-09.c1: the run failed: {tapped.stderr[-300:]}"
    assert tapped.badges("KIND_COMPUTED_NOT_CONSUMED") == {"A": 1}, (
        f"SYT-ORC-09.c1: missing, raised more than once, or on another stage: {tapped.badges('KIND_COMPUTED_NOT_CONSUMED')}")


def test_syt_orc_09_c2_a_simulated_chain_raises_none(tmp_path):  # SYT-ORC-09.c2
    tapped = tap_case(lab_case("fan_out", "all_simulated"), tmp_path, "tap")
    assert tapped.returncode == 0, f"SYT-ORC-09.c2: the run failed: {tapped.stderr[-300:]}"
    assert tapped.steps, "SYT-ORC-09.c2: the tap printed no step"
    assert tapped.badges("KIND_COMPUTED_NOT_CONSUMED") == {}, f"SYT-ORC-09.c2: any: {tapped.badges('KIND_COMPUTED_NOT_CONSUMED')}"


def _lab_setups() -> list[tuple[str, str, str]]:
    found = []
    for path in sorted((lab_root() / "lab").glob("*/*.run.json")):
        scenario, _dot, case = path.name[: -len(".run.json")].partition(".")
        found.append((path.parent.name, scenario, case))
    return found


def _expected_plan(topology_name: str, case_entry: dict, setup: dict) -> dict[str, tuple[int, str, list[str]]]:
    """`{stage: (rank, start, previous-cycle inputs)}` of every simulated stage, from the topology file."""
    try:
        from lab_tools.topology import load_topology
    except ImportError as exc:
        skip(f"the lab's topology reader cannot be imported: {exc}")
    topology = load_topology(lab_root() / "catalogue" / f"{topology_name}.yaml")
    simulated = [s["name"] for s in setup["stages"] if s["mode"] == "simulate"]
    rank: dict[str, int] = {}
    pending = list(simulated)
    while pending:
        for name in list(pending):
            component = topology.component(name)
            below = [i.producer for i in component.inputs if not i.previous_cycle and i.producer in simulated]
            if all(p in rank for p in below):
                rank[name] = 1 + max((rank[p] for p in below), default=0)
                pending.remove(name)
    overrides = case_entry.get("trigger") or {}
    plan = {}
    for name in simulated:
        component = topology.component(name)
        trigger = overrides.get(name, component.trigger if component.trigger else "control")
        start = "control" if trigger == "control" else f"input:{trigger}"
        previous = [f"{i.name}<-{i.producer}.{i.port}" for i in component.inputs if i.previous_cycle]
        plan[name] = (rank[name], start, previous)
    return plan


def _printed_plan(text: str) -> dict[str, tuple[int, str, list[str]]]:
    found = {}
    for match in re.finditer(r"^stage: (\S+) rank=(\d+) start=(\S+) previous_cycle=\[(.*)\]$", text, re.MULTILINE):
        found[match.group(1)] = (int(match.group(2)), match.group(3), [p for p in match.group(4).split(",") if p])
    return found


@pytest.mark.parametrize(("topology", "scenario", "name"), _case_params(_lab_setups()))
def test_syt_orc_10_c1_the_plan_is_printed_without_running(tmp_path, topology, scenario, name):  # SYT-ORC-10.c1
    case = lab_case(topology, name, scenario)
    setup = json.loads(case.setup.read_text(encoding="utf-8"))
    expected = _expected_plan(topology, case.case_entry, setup)

    def remove_libraries(copy: dict) -> None:
        for stage in copy["stages"]:
            stage["impl"]["path"] = (tmp_path / "removed" / f"{stage['name']}.dll").as_posix()

    run = run_case(case, tmp_path, "run", change=remove_libraries)
    label = f"{topology}/{scenario}/{name}"
    printed = _printed_plan(run.stderr)
    error_at = run.stderr.find("[simengine] error:")
    plan_at = run.stderr.find("stage: ")
    assert run.returncode != 0 and error_at >= 0, f"SYT-ORC-10.c1: {label}: no load error for the missing libraries (exit {run.returncode})"
    assert 0 <= plan_at < error_at, f"SYT-ORC-10.c1: {label}: no plan before the load error for the missing library"
    assert set(printed) == set(expected), f"SYT-ORC-10.c1: {label}: a missing stage: printed {sorted(printed)}, expected {sorted(expected)}"
    for stage, wanted in expected.items():
        assert printed[stage] == wanted, f"SYT-ORC-10.c1: {label}: stage {stage}: a mismatch, printed {printed[stage]}, expected {wanted}"


def _one_run_per_distinct_counter(produced: Recording, recorded: Recording) -> list[str]:
    """The count check of `SYT-ORC-11`: `T`'s controls in the engine-run recording against the distinct `in_X`
    counters of the recording."""
    distinct = len(set(recorded.counters("source.X")))
    controls = len(produced.of("T.control"))
    return [] if controls == distinct else [f"{controls} T controls for {distinct} distinct in_X counters"]


def test_syt_orc_11_c1_a_repeated_trigger_sample_starts_no_run_and_is_logged_stalled(tmp_path):  # SYT-ORC-11.c1
    case = lab_case("data_triggered", "by_data", "repeat_trigger")
    run, produced = _ran(case, tmp_path, "run")
    recorded = Recording(case.recording)
    assert len(recorded.of("source.X")) > len(set(recorded.counters("source.X"))), "SYT-ORC-11.c1: the recording holds no repeated sample"
    assert _one_run_per_distinct_counter(produced, recorded) == [], f"SYT-ORC-11.c1: an extra or a missing run: {_one_run_per_distinct_counter(produced, recorded)}"
    stalled = [line for line in run.events if "entry=stalled_trigger" in line and "stage=T" in line and "port=in_X" in line]
    assert len(stalled) == 1, f"SYT-ORC-11.c1: one stalled_trigger entry naming T and in_X expected, found {len(stalled)}: {run.events[:4]}"


def test_syt_orc_11_c2_a_planted_extra_run_is_reported(tmp_path):  # SYT-ORC-11.c2
    case = lab_case("data_triggered", "by_data", "repeat_trigger")
    _run, produced = _ran(case, tmp_path, "run")
    recorded = Recording(case.recording)
    seen: set[int] = set()
    repeat_index = None
    for index, _t, message in produced.decoded("source.X"):
        counter = message.sig_header.measurement_counter
        if counter in seen:
            repeat_index = index
            break
        seen.add(counter)
    assert repeat_index is not None, "SYT-ORC-11.c2: the engine-run recording holds no repeated sample"
    repeat_time = produced.messages[repeat_index][1]
    a_control = produced.of("T.control")[0][2]

    planted_case = dataclasses.replace(case, recording=produced.path)
    planted = edit_recording(planted_case, tmp_path / "planted.mcap",
                             lambda ms: [m for i, m in enumerate(ms[: repeat_index + 1])] + [("T.control", repeat_time, a_control)] + ms[repeat_index + 1:])
    problems = _one_run_per_distinct_counter(Recording(planted), recorded)
    assert problems, "SYT-ORC-11.c2: the copy passes, so the check could not have failed"


def test_syt_orc_12_c1_a_clock_started_control_wraps_to_1():  # SYT-ORC-12.c1
    executable = tool_path("control_tick")
    expected = {0: 1, 1: 2, 0xFFFFFFFE: 0xFFFFFFFF, 0xFFFFFFFF: 1, 0x100000000: 2}
    found = {}
    for tick in expected:
        done = subprocess.run([str(executable), "1000000", hex(tick)], capture_output=True, text=True, timeout=60)
        assert done.returncode == 0, f"SYT-ORC-12.c1: control_tick failed for tick {tick:#x}: {done.stderr}"
        found[tick] = int(done.stdout.strip())
    assert found == expected, (
        "SYT-ORC-12.c1: a 0, or 0xFFFFFFFF followed by anything but 1: "
        + ", ".join(f"tick {t:#x} -> {found[t]:#x} (expected {expected[t]:#x})" for t in expected if found[t] != expected[t]))
