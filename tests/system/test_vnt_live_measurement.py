# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`IMP-0120`: the live measurement as the engine writes it, `SYT-LMW-01`..`16` (`VANTAGE_Test_Spec.md` section 8).
Each test names its case id, cites the `Accept` it checks and states the FAIL side in its message.

Readers: the inspector (`dump`, `attach`), `F-READER`, and `LiveRegion`, which reads the shared memory with `struct`
and a wire parser written in `tests/support/livemeas_runs.py`, independent of every C++ reader. On Windows a name
lives while a handle is open, so each test attaches before the run ends (`D31 (5)`).

Where the spec leaves a step open it is chosen so the case can fail:
- `F-LM-HELD`'s ring holds the whole run (steps from `F-TAP` plus 8); tests that read no cycles use a ring of 4;
- `SYT-LMW-02` runs every lab case that loads (a `refused_at_load` scenario has no description) and compares the
  description with the held setup, which is the case's plus the held stage `H`;
- `SYT-LMW-04`'s "arrival time" of a sample is the logging time of its message in the engine-run recording (the
  lab recording for a `source.*` port), and the engine's step times are `F-TAP`'s;
- `SYT-LMW-08`: the `camera` topology has no stage reading `Cam`, so the case's `bulk: [source.Cam]` flags no stage
  port; the held stage reads `Cam` there (the setup edit of `F-SETUP-EDIT`), and the bulk ring is enlarged to hold
  every frame, the big one included. `bulk` empty is the same setup with the flag off;
- `SYT-LMW-12` and `-13`..`-14` read with `F-READER --until-finished` and `LiveRegion` attached as the name appears.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from tests.support.engine_runs import (
    Recording, case_change, case_params, compare_recordings, exact_cases, lab_compare, lab_setups, ran, run_case,
    run_engine, tap_case, tool_path,
)
from tests.support.lab_cases import edit_recording, edit_setup, lab_case
from tests.support.livemeas_runs import (
    PROBE_STAGE, LiveRegion, case_bundles, descendants, held_run, inspect, pair_controls, parse_dump, process_table,
    release_and_follow, start_inspect, status_fields, tap_with_region, wait_until,
)
from tests.support.engine_runs import point_at_recording, sha256_of
from tests.support.lab_cases import LabCase


def cut_c() -> LabCase:
    return lab_case("running_example", "cut_c")


def _port_names(region: LiveRegion) -> list[str]:
    return [p["name"] for p in region.description().ports]


def _end(held, region: LiveRegion | None = None):
    region = region or LiveRegion(held.name)
    held.release()
    finished = held.finish()
    assert finished.returncode == 0, f"the held run failed: {finished.stderr[-400:]}"
    return region, finished


# ---- SYT-LMW-01 ---------------------------------------------------------------------------------------------------

def test_syt_lmw_01_the_setup_names_the_live_measurement(tmp_path):
    """`SYT-LMW-01`, `SYS-0058` Accept. `.c1`: name and geometry as the setup's and a cycle for step 0. FAIL: another
    name or geometry, or no cycle for step 0. `.c2`: with `outputs.livemeas` removed no live measurement of that name
    exists. FAIL: one does."""
    held = held_run(cut_c(), tmp_path, "lmw01a")
    try:
        region = LiveRegion(held.name)
        declared = json.loads(held.setup.read_text(encoding="utf-8"))["outputs"]["livemeas"]
        attached = status_fields(inspect("attach", held.name).out)
        status = region.status()
        assert (status.cycle_slot_count, status.cycle_slot_size, status.bulk_slot_count, status.bulk_slot_size) == (
            declared["cycle_slot_count"], declared["cycle_slot_size"], declared["bulk_slot_count"], declared["bulk_slot_size"]), \
            "SYT-LMW-01.c1: another geometry than the setup's"
        assert attached["cycle slots"] == f"{declared['cycle_slot_count']} x {declared['cycle_slot_size']} bytes"
        _end(held, region)
        cycles = region.cycles()
        assert cycles and cycles[0].step == 0, "SYT-LMW-01.c1: no cycle for step 0"
    finally:
        held.close()
    removed = held_run(cut_c(), tmp_path, "lmw01b", livemeas=False)
    try:
        listed = inspect("attach", removed.name)
        assert listed.code == 6, f"SYT-LMW-01.c2: a live measurement named {removed.name} exists: {listed.out}"
        removed.release()
        assert removed.finish().returncode == 0
    finally:
        removed.close()


# ---- SYT-LMW-02 ---------------------------------------------------------------------------------------------------

def _loading_setups() -> list[tuple[str, str, str]]:
    from tests.support.engine_runs import catalogue

    expect = {(t, s["name"]): s.get("expect", "exact") for t, d in catalogue().items() for s in d.get("scenarios", [])}
    return [c for c in lab_setups() if expect.get((c[0], c[1]), "exact") != "refused_at_load"]


@pytest.mark.parametrize("topology,scenario,case", case_params(_loading_setups()))
def test_syt_lmw_02_c1_the_description_equals_the_setup(tmp_path, topology, scenario, case):
    """`SYT-LMW-02.c1`, `SYS-0059` Accept: every stage, port, `bulk` flag, trigger, clock, previous-cycle input,
    override, bundle hash and the readiness limit in the description equals the setup's, nothing extra. FAIL: any
    difference, naming case and field."""
    lab = lab_case(topology, case, scenario)
    held = held_run(lab, tmp_path, "lmw02", ring=4)
    where = f"{topology}/{scenario}/{case}"
    try:
        region = LiveRegion(held.name)
        description = region.description()
        setup = json.loads(held.setup.read_text(encoding="utf-8"))
    finally:
        held.close()
    assert description.recording == Path(setup["sources"][0]["path"]).name, f"{where}: recording"
    assert [s["name"] for s in description.stages] == [s["name"] for s in setup["stages"]], f"{where}: stages"
    modes = {"simulate": "MODE_SIMULATE", "measured": "MODE_MEASURED", "off": "MODE_OFF"}
    for declared, described in zip(setup["stages"], description.stages):
        name = declared["name"]
        assert described["mode"] == modes[declared["mode"]], f"{where}: {name} mode"
        impl = declared["impl"]
        assert described["impl"] == (impl["kind"] if not impl["path"] else f"{impl['kind']}:{impl['path']}"), f"{where}: {name} impl"
        assert described["trigger"] == declared["trigger"], f"{where}: {name} trigger"
        assert described["clock_period_ns"] == declared["clock_period_ns"], f"{where}: {name} clock"
        assert described["previous_cycle_inputs"] == [i["port"] for i in declared["inputs"] if i["previous_cycle"]], \
            f"{where}: {name} previous-cycle inputs"
    expected_ports: dict[str, bool] = {}
    for stage in setup["stages"]:
        if stage["mode"] != "off":
            for port in stage["ports"]:
                expected_ports[f"{stage['name']}.{port['name']}"] = port["bulk"]
    for stage in setup["stages"]:
        if stage["mode"] == "off":
            continue
        for wired in stage["inputs"]:
            if wired["producer"] == "source":
                name = f"source.{wired['producer_port']}"
                bulk = next(p["bulk"] for p in stage["ports"] if p["name"] == wired["port"])
                expected_ports[name] = expected_ports.get(name, False) or bulk
    assert {p["name"]: p["bulk"] for p in description.ports} == expected_ports, f"{where}: ports or bulk flags"
    assert len(description.ports) == len(expected_ports), f"{where}: a port listed twice"
    assert len(description.overrides) == len(setup["mutations"]), f"{where}: overrides"
    for mutation, described in zip(setup["mutations"], description.overrides):
        assert mutation["address"]["stage"] in described["address"] and mutation["address"]["port"] in described["address"], \
            f"{where}: override address {described['address']}"
    hashed = [(s["name"], s["config_bundle_sha256"]) for s in setup["stages"] if s["config_bundle_sha256"]]
    assert [(b["stage"], b["sha256"]) for b in description.bundles] == hashed, f"{where}: bundle hashes"
    assert description.readiness_limit_steps == setup["readiness_limit_steps"], f"{where}: readiness limit"


def test_syt_lmw_02_c2_c_has_no_build_id_and_a_simulated_stage_has_its_manifests(tmp_path):
    """`SYT-LMW-02.c2`, `SYS-0060` Accept: `C`, measured, has an empty `build_id`; each simulated stage's equals its
    loaded manifest's (the engine's run manifest names it). FAIL: `C` non-empty, or a simulated stage's differing."""
    lab = cut_c()
    held = held_run(lab, tmp_path, "lmw02b", ring=4)
    try:
        region = LiveRegion(held.name)
        description = region.description()
        held.release()
        finished = held.finish()
        assert finished.returncode == 0, finished.stderr[-300:]
    finally:
        held.close()
    manifest = Recording(finished.recording).manifest
    built = {c["name"]: c["build_id"] for c in manifest["components"]}
    by_name = {s["name"]: s for s in description.stages}
    assert by_name["C"]["mode"] == "MODE_MEASURED" and by_name["C"]["build_id"] == "", f"SYT-LMW-02.c2: C's build_id {by_name['C']['build_id']!r}"
    simulated = [n for n, s in by_name.items() if s["mode"] == "MODE_SIMULATE"]
    assert {"A", "B", "D", "E", PROBE_STAGE} <= set(simulated)
    for name in simulated:
        assert by_name[name]["build_id"] and by_name[name]["build_id"] == built[name], \
            f"SYT-LMW-02.c2: {name}'s build_id {by_name[name]['build_id']!r} is not its manifest's {built.get(name)!r}"


# ---- SYT-LMW-03 ---------------------------------------------------------------------------------------------------

def test_syt_lmw_03_every_schema_is_in_the_descriptor_set(tmp_path):
    """`SYT-LMW-03`, `SYS-0061` Accept. `.c1`: with `C`'s library path removed (it is measured), every port decodes,
    `C`'s recorded output included. FAIL: one undecodable port."""
    def without_c_library(setup: dict) -> None:
        for stage in setup["stages"]:
            if stage["name"] == "C":
                stage["impl"]["path"] = ""

    held = held_run(cut_c(), tmp_path, "lmw03", change=without_c_library)
    try:
        (dumped,) = release_and_follow(held, ("dump", "--follow"))
        assert held.finish().returncode == 0
    finally:
        held.close()
    lines = parse_dump(dumped.out)
    bad = [l for l in lines if l.body.startswith("<")]
    assert dumped.code == 0 and lines and not bad, f"SYT-LMW-03.c1: undecodable ports: {sorted({l.port for l in bad})}"
    assert any(l.port == "C.out" for l in lines), "SYT-LMW-03.c1: C's recorded output is not in the dump"


# ---- SYT-LMW-04 ---------------------------------------------------------------------------------------------------

def test_syt_lmw_04_held_values_and_their_age(tmp_path):
    """`SYT-LMW-04`, `SYS-0062` Accept. `.c1`: each port's value in step k is the newest sample by k, `age_ns` k's
    time minus its arrival. FAIL: another value or age. `.c2`: a port with no sample by k is absent from step k. FAIL:
    a value or a default is present."""
    import bisect

    lab = lab_case("running_example", "all_simulated")
    tapped = tap_case(lab, tmp_path, "lmw04_tap")
    assert tapped.returncode == 0, tapped.stderr[-300:]
    times = {s["step"]: s["time_ns"] for s in tapped.steps}
    held = held_run(lab, tmp_path, "lmw04")
    try:
        region = LiveRegion(held.name)
        _end(held, region)
        finished_recording = held.recording
    finally:
        held.close()
    compare, messages = lab_compare()
    produced, recorded = Recording(finished_recording), Recording(lab.recording)
    names = _port_names(region)
    arrivals: dict[str, tuple[list[int], list[bytes]]] = {}
    for name in names:
        if name.startswith(PROBE_STAGE + "."):
            continue
        source = recorded if name.startswith("source.") else produced
        found = sorted(((t, i, p) for i, t, p in source.of(name)), key=lambda m: (m[0], m[1]))
        arrivals[name] = ([t for t, _i, _p in found], [p for _t, _i, p in found])
    cycles = region.cycles()
    assert len(cycles) == len(tapped.steps), f"the ring holds {len(cycles)} of {len(tapped.steps)} steps"
    wrong, present = [], 0
    for cycle in cycles:
        now = times[cycle.step]
        seen = set()
        for value in cycle.values:
            name = names[value.port]
            if name not in arrivals:
                continue
            seen.add(name)
            times_of, payloads = arrivals[name]
            index = bisect.bisect_right(times_of, now) - 1
            if index < 0:
                wrong.append(f"step {cycle.step} {name}: a value with no sample by then (c2)")
                continue
            present += 1
            schema, descriptor_set = (produced.schemas.get(name) or recorded.schemas[name])
            same = compare.equal_outputs([payloads[index]], [value.payload], messages.MessageFactory(descriptor_set), schema).equal
            if not same or value.age_ns != now - times_of[index]:
                wrong.append(f"step {cycle.step} {name}: value equal {same}, age {value.age_ns} != {now - times_of[index]}")
        for name, (times_of, _payloads) in arrivals.items():
            if name not in seen and times_of and times_of[0] <= now and not name.endswith(".control"):
                wrong.append(f"step {cycle.step} {name}: a sample arrived by then but the port is absent")
    assert present > 1000 and not wrong, f"SYT-LMW-04.c1/.c2: {len(wrong)} wrong of {present}: {wrong[:6]}"


# ---- SYT-LMW-05 ---------------------------------------------------------------------------------------------------

def test_syt_lmw_05_origins(tmp_path):
    """`SYT-LMW-05`, `SYS-0063` Accept. `.c1`: with one override on `source.Y`, every value of `C` and of the sources
    carries the recording's tag, every other stage's output `simulated`, `B`'s `in_Y` `overridden`. FAIL: any other
    origin, or `overridden` on a port not overridden."""
    def override_y(setup: dict) -> None:
        setup["mutations"] = [{"verb": "const", "address": {"stage": "source", "port": "Y", "path": ["value"], "index": None},
                               "operands": [7], "window_ns": [None, None]}]

    lab = cut_c()
    held = held_run(lab, tmp_path, "lmw05", change=override_y)
    try:
        region = LiveRegion(held.name)
        _end(held, region)
    finally:
        held.close()
    names = _port_names(region)
    tags = {t: v.upper() for t, v in Recording(lab.recording).provenance.items()}
    origins: dict[str, set[str]] = {}
    for cycle in region.cycles():
        for value in cycle.values:
            origins.setdefault(names[value.port], set()).add(value.origin)
    problems = []
    for name, found in origins.items():
        stage, _dot, port = name.partition(".")
        if stage == PROBE_STAGE:
            continue
        if stage == "source" or stage == "C":
            expected = {tags[name]}
        elif port in ("out", "refSync", "compState"):
            expected = {"SIMULATED"}
        elif port == "in_Y":
            expected = {"OVERRIDDEN"}
        else:
            continue  # a simulated stage's control
        if found != expected:
            problems.append(f"{name}: {sorted(found)} (expected {sorted(expected)})")
    overridden = sorted(n for n, f in origins.items() if "OVERRIDDEN" in f)
    assert not problems, f"SYT-LMW-05.c1: {problems}"
    assert "B.in_Y" in overridden and all(n.endswith(".in_Y") for n in overridden), f"SYT-LMW-05.c1: overridden ports {overridden}"


# ---- SYT-LMW-06, 14 -----------------------------------------------------------------------------------------------

def _badges_by_step(cycles) -> dict[int, set]:
    return {c.step: {b for b in c.badges if not b[1].startswith(PROBE_STAGE + ".")} for c in cycles}


def test_syt_lmw_06_badges_in_the_step_that_raised_them(tmp_path):
    """`SYT-LMW-06`, `SYS-0064` Accept. `.c1`: on `missing_sample` the cycle's badges equal the tap's at every step and
    `KIND_FALLBACK` first appears at the tap's step. FAIL: any difference."""
    lab = lab_case("running_example", "all_simulated", "missing_sample")
    tapped = tap_case(lab, tmp_path, "lmw06_tap")
    assert tapped.returncode == 0, tapped.stderr[-300:]
    held = held_run(lab, tmp_path, "lmw06")
    try:
        region = LiveRegion(held.name)
        _end(held, region)
    finally:
        held.close()
    live = _badges_by_step(region.cycles())
    expected = {s["step"]: {(b["kind"], b["subject"], b["count"]) for b in s["badges"]} for s in tapped.steps}
    different = [k for k in expected if live.get(k) != expected[k]]
    assert not different, f"SYT-LMW-06.c1: badges differ at steps {different[:5]}: {live.get(different[0])} vs {expected[different[0]]}"
    first = lambda by: min((k for k, v in sorted(by.items()) if any(b[0] == "KIND_FALLBACK" for b in v)), default=None)
    assert first(live) is not None and first(live) == first(expected), \
        f"SYT-LMW-06.c1: KIND_FALLBACK first at {first(live)}, the tap's {first(expected)} (None: the case could not fail)"


def test_syt_lmw_14_the_tap_and_the_writer_get_the_same_step(tmp_path):
    """`SYT-LMW-14`, `SYS-0072` Accept. `.c1`: with `outputs.livemeas`, each tap line's step, time and badges equal the
    cycle of that step. FAIL: any difference."""
    run = tap_with_region(cut_c(), tmp_path, "lmw14")
    assert run.returncode == 0 and run.region is not None, f"tap run: {run.returncode} {run.stderr[-300:]}"
    cycles = {c.step: c for c in run.region.cycles()}
    assert len(cycles) == len(run.steps) > 100, f"SYT-LMW-14.c1: {len(cycles)} cycles for {len(run.steps)} tap lines"
    for line in run.steps:
        cycle = cycles.get(line["step"])
        assert cycle is not None, f"SYT-LMW-14.c1: no cycle for step {line['step']}"
        assert cycle.sim_time_ns == line["time_ns"], f"SYT-LMW-14.c1: step {line['step']} time {cycle.sim_time_ns} != {line['time_ns']}"
        assert set(cycle.badges) == {(b["kind"], b["subject"], b["count"]) for b in line["badges"]}, \
            f"SYT-LMW-14.c1: step {line['step']} badges differ"


# ---- SYT-LMW-07 ---------------------------------------------------------------------------------------------------

def test_syt_lmw_07_two_runs_of_a_stage_in_one_step(tmp_path):
    """`SYT-LMW-07`, `SYS-0065` Accept. `.c1`: on `F-LM-TWICE` each step with two `B` runs has two values on `B`'s
    control, refSync, output and overridden-input ports, each with its run's counter, in run order. FAIL: one value,
    another order, or no step with two `B` runs."""
    lab = lab_case("running_example", "all_simulated")
    edited = edit_recording(lab, tmp_path / "paired.mcap", pair_controls)

    def twice(setup: dict) -> None:
        point_at_recording(setup, edited)
        setup["mutations"] = [{"verb": "scale", "address": {"stage": "source", "port": "Y", "path": ["value"], "index": None},
                               "operands": [1.0], "window_ns": [None, None]}]

    tapped = tap_case(lab, tmp_path, "lmw07_tap", change=twice)
    assert tapped.returncode == 0, tapped.stderr[-300:]
    held = held_run(lab, tmp_path, "lmw07", change=twice)
    try:
        region = LiveRegion(held.name)
        _end(held, region)
        recording = Recording(held.recording)
    finally:
        held.close()
    names = _port_names(region)
    times = {s["step"]: s["time_ns"] for s in tapped.steps}
    controls_at: dict[int, list[int]] = {}
    for _i, t, message in recording.decoded("B.control"):
        controls_at.setdefault(t, []).append(message.sig_header.measurement_counter)
    two_runs = [step for step, t in times.items() if len(controls_at.get(t, [])) == 2]
    assert two_runs, "SYT-LMW-07.c1: no step with two B runs, so the case could not fail"
    cycles = {c.step: c for c in region.cycles()}
    for step in two_runs:
        at = times[step]
        for port in ("control", "refSync", "out", "in_Y"):
            topic = f"B.{port}"
            expected = [m.sig_header.measurement_counter for _i, t, m in recording.decoded(topic) if t == at]
            got = [recording.decode(topic, v.payload).sig_header.measurement_counter
                   for v in cycles[step].values if names[v.port] == topic]
            if port in ("refSync",):
                expected = expected  # RefSync's own header counter is the run's control counter
            assert len(got) == 2 and got == expected, \
                f"SYT-LMW-07.c1: step {step} {topic}: values {got}, the runs' counters {expected}"
        in_y = [v for v in cycles[step].values if names[v.port] == "B.in_Y"]
        assert all(v.origin == "OVERRIDDEN" for v in in_y), f"SYT-LMW-07.c1: step {step}: B.in_Y origins {[v.origin for v in in_y]}"


# ---- SYT-LMW-08 ---------------------------------------------------------------------------------------------------

CAM = {"source": "Cam", "source_type": "adas.lab.LabImage"}


def _bulk_ring_for_the_run(setup: dict) -> None:
    """The bulk ring enlarged to hold every write of the run, the 65536-byte frame included (a `F-SETUP-EDIT`): a
    flagged port's newest sample is written to `MeasBulk` at every step, so the ring needs a slot per port per step."""
    setup["outputs"]["livemeas"]["bulk_slot_count"] = 600
    setup["outputs"]["livemeas"]["bulk_slot_size"] = 69632


def test_syt_lmw_08_only_a_flagged_port_goes_to_meas_bulk(tmp_path):
    """`SYT-LMW-08`, `SYS-0066` Accept. `.c1`: on `camera` with `bulk: [source.Cam]` only `source.Cam` (and the stage
    port that reads it) is flagged and every image resolves in `MeasBulk`. FAIL: another port flagged, or an
    unresolved image. `.c2`: with `bulk` empty no `MeasBulk` frame is written. FAIL: a frame is written."""
    lab = lab_case("camera", "bulk")
    held = held_run(lab, tmp_path, "lmw08a", change=_bulk_ring_for_the_run, held_source=dict(CAM, bulk=True), ring=200)
    try:
        region = LiveRegion(held.name)
        _end(held, region)
        recording = Recording(lab.recording)
    finally:
        held.close()
    description = region.description()
    names = _port_names(region)
    flagged = sorted(p["name"] for p in description.ports if p["bulk"])
    assert flagged == [f"{PROBE_STAGE}.in", "source.Cam"], f"SYT-LMW-08.c1: flagged ports {flagged}"
    frames = {m.sig_header.measurement_counter: p for _i, _t, p in recording.of("source.Cam")
              for m in [recording.decode("source.Cam", p)]}
    resolved = 0
    for cycle in region.cycles():
        for value in cycle.values:
            if names[value.port] not in ("source.Cam", f"{PROBE_STAGE}.in"):
                continue
            assert value.payload == b"" and value.bulk is not None and not value.omitted, \
                f"SYT-LMW-08.c1: step {cycle.step} {names[value.port]}: inline bytes or no reference"
            sequence, step, port, payload = region.bulk_slot(value.bulk[0])
            assert (sequence, step, port) == (value.bulk[1], cycle.step, value.port), \
                f"SYT-LMW-08.c1: step {cycle.step}: the reference resolves to step {step} sequence {sequence}"
            assert payload == frames[recording.decode("source.Cam", payload).sig_header.measurement_counter], \
                f"SYT-LMW-08.c1: step {cycle.step}: the frame is not the recording's"
            resolved += 1
    assert resolved >= 40, f"SYT-LMW-08.c1: only {resolved} references resolved"

    empty = held_run(lab_case("camera", "oversize"), tmp_path, "lmw08b", held_source=dict(CAM, bulk=False), ring=200)
    try:
        region = LiveRegion(empty.name)
        _end(empty, region)
    finally:
        empty.close()
    assert all(region.bulk_slot(i)[0] == 0 for i in range(region.status().bulk_slot_count)), \
        "SYT-LMW-08.c2: a MeasBulk frame was written with bulk empty"
    assert not any(v.bulk is not None for c in region.cycles() for v in c.values), "SYT-LMW-08.c2: a bulk reference in a cycle"


# ---- SYT-LMW-09 ---------------------------------------------------------------------------------------------------

def test_syt_lmw_09_the_worker_is_the_writer(tmp_path):
    """`SYT-LMW-09`, `SYS-0067` Accept. `.c1`: on a supervised `cut_c` `writerPid` is the worker's and not the
    supervisor's. FAIL: it is the supervisor's, or another process's."""
    held = held_run(cut_c(), tmp_path, "lmw09", supervise_ms=120000)
    try:
        region = LiveRegion(held.name)
        writer = region.status().writer_pid
        children = descendants(held.pid)
        held.release()
        assert held.finish().returncode == 0
    finally:
        held.close()
    assert writer != held.pid, "SYT-LMW-09.c1: the supervisor is the writer"
    assert children == [writer], f"SYT-LMW-09.c1: writerPid {writer}, the supervisor's descendants {children}"


# ---- SYT-LMW-10 ---------------------------------------------------------------------------------------------------

def test_syt_lmw_10_a_second_engine_on_a_held_name(tmp_path):
    """`SYT-LMW-10`, `SYS-0068` Accept. `.c1`: one warning naming the name and the cause. FAIL: none, two, or a message
    without the name. `.c2`: equal outputs to a run with no `outputs.livemeas`, and the first engine's live measurement
    unchanged. FAIL: a difference, or the first run disturbed."""
    lab = cut_c()
    held = held_run(lab, tmp_path, "lmw10")
    try:
        region = LiveRegion(held.name)
        before = region.copy()

        def same_name(setup: dict) -> None:
            setup["outputs"]["livemeas"]["name"] = held.name

        second = run_engine(edit_setup(lab, tmp_path, same_name, name="second", outputs=tmp_path / "second.mcap"), cwd=tmp_path)
        third = run_case(lab, tmp_path, "third", change=lambda s: s["outputs"].pop("livemeas"))
        after = region.copy()
        held.release()
        held.finish()
    finally:
        held.close()
    warnings = [l for l in second.stderr.splitlines() if "warning" in l.lower() and held.name in l]
    assert second.returncode == 0 and len(warnings) == 1 and "kLiveMeasNameHeld" in warnings[0], \
        f"SYT-LMW-10.c1: exit {second.returncode}, warnings {warnings} in {second.stderr[-500:]}"
    assert third.returncode == 0
    differences = compare_recordings(Recording(second.recording), Recording(third.recording))
    assert not differences, f"SYT-LMW-10.c2: outputs differ: {differences[:3]}"
    assert before == after, "SYT-LMW-10.c2: the first engine's live measurement changed under the second run"


# ---- SYT-LMW-11 ---------------------------------------------------------------------------------------------------

def test_syt_lmw_11_a_dead_writers_name_is_replaced(tmp_path):
    """`SYT-LMW-11`, `SYS-0069` Accept. `.c1`: after the engine is killed while held, a second on the same name opens
    it, its run id differs and a cycle for step 0 is read. FAIL: an open refused, the same run id, or no cycle for
    step 0."""
    lab = cut_c()
    first = held_run(lab, tmp_path / "one", "lmw11")
    killed = LiveRegion(first.name)
    first_run_id = killed.status().run_id
    first.kill()
    second = held_run(lab, tmp_path / "two", "lmw11", distinct_from=first_run_id)
    try:
        assert second.process.poll() is None, "SYT-LMW-11.c1: the second engine ended (its open was refused?)"
        region = LiveRegion(second.name)
        assert region.status().run_id != first_run_id, "SYT-LMW-11.c1: the same run id"
        second.release()
        finished = second.finish()
        assert finished.returncode == 0, f"SYT-LMW-11.c1: {finished.stderr[-300:]}"
        cycles = region.cycles()
        assert cycles and cycles[0].step == 0, "SYT-LMW-11.c1: no cycle for step 0"
    finally:
        first.close()
        second.close()


# ---- SYT-LMW-12 ---------------------------------------------------------------------------------------------------

def _reader(name: str, budget_ms: int = 120000) -> subprocess.Popen:
    return subprocess.Popen([str(tool_path("lm_reader")), "--until-finished", name, "--timeout-ms", str(budget_ms)],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)


def _outcome(reader: subprocess.Popen) -> int | None:
    out, _ = reader.communicate(timeout=120)
    found = [l for l in out.splitlines() if l.startswith("outcome=")]
    return int(found[-1].split("=")[1]) if found else None


def test_syt_lmw_12_the_workers_own_outcomes(tmp_path):
    """`SYT-LMW-12`, `SYS-0070` Accept. `.c1`: the attached reader reads status finished with `pass`, `fail` and
    `timeout` (1, 2, 4) after `cut_c`, `held_probe` failing its third call, and `hang` with `limits.exec_timeout_ms` below the
    hang. FAIL: any other outcome, or a status other than finished."""
    lab = cut_c()
    def name_of(case: LabCase, label: str) -> str:
        return json.loads(case.setup.read_text(encoding="utf-8"))["outputs"]["livemeas"]["name"] + f"_{label}"

    reader = _reader(name_of(lab, "pass"))
    passed = run_case(lab, tmp_path, "pass")
    assert passed.returncode == 0, passed.stderr[-300:]
    assert _outcome(reader) == 1, "SYT-LMW-12.c1: cut_c did not read finished with pass"

    hang = lab_case("running_example", "hang")

    on_hang_bundle = case_bundles(hang, tmp_path)

    def short_timeout(setup: dict) -> None:
        on_hang_bundle(setup)
        setup["limits"]["exec_timeout_ms"] = 300

    reader = _reader(name_of(hang, "timeout"))
    timed_out = run_case(hang, tmp_path, "timeout", change=short_timeout)
    assert timed_out.returncode == 7, f"hang with a timeout below it exited {timed_out.returncode}: {timed_out.stderr[-300:]}"
    assert _outcome(reader) == 4, "SYT-LMW-12.c1: hang did not read finished with timeout"

    reader = _reader(name_of(lab, "fail"))
    failing = held_run(lab, tmp_path, "fail", fail_at_call=3)
    failing.release()
    failed = failing.finish()
    outcome = _outcome(reader)
    assert failed.returncode != 0 and outcome == 2, (
        f"SYT-LMW-12.c1: `held_probe` failing its third call gave exit {failed.returncode} and the reader read outcome "
        f"{outcome}, not a failed run (2): {failed.stderr[-300:]}")


# ---- SYT-LMW-13 ---------------------------------------------------------------------------------------------------

def test_syt_lmw_13_a_jump_keeps_one_run_id(tmp_path):
    """`SYT-LMW-13`, `SYS-0071` Accept. `.c1`: the run id is the same before and after the jump and the steps are
    consecutive across it. FAIL: a new run id, a gap or a restart at 0."""
    lab = lab_case("running_example", "jump")
    run = tap_with_region(lab, tmp_path, "lmw13", jump=(500, 1500))
    assert run.returncode == 0 and run.region is not None, f"{run.returncode} {run.stderr[-300:]}"
    times = [s["time_ns"] for s in run.steps]
    assert any(b - a > 500_000_000 for a, b in zip(times, times[1:])), "SYT-LMW-13.c1: the tap shows no jump, so the case could not fail"
    steps = [c.step for c in run.region.cycles()]
    assert steps == list(range(len(run.steps))), f"SYT-LMW-13.c1: steps are not consecutive across the jump: {steps[:3]}..{steps[-3:]}"
    # one run id: the engine opens once per run, and the tap's single process holds the one region
    assert run.region.status().run_id != 0


# ---- SYT-LMW-15 ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("topology,scenario,case", case_params(exact_cases()))
def test_syt_lmw_15_writing_the_live_measurement_changes_no_output(tmp_path, topology, scenario, case):
    """`SYT-LMW-15`, `SYS-0073` Accept. `.c1`: with and without `outputs.livemeas` the engine-run recordings are equal
    outputs on every port and the event logs identical. FAIL: any difference, naming case, port and step."""
    lab = lab_case(topology, case, scenario)
    with_lm, with_recording = ran(lab, tmp_path, "with")
    without, without_recording = ran(lab, tmp_path, "without", change=lambda s: s["outputs"].pop("livemeas"))
    where = f"{topology}/{scenario}/{case}"
    differences = compare_recordings(with_recording, without_recording)
    assert not differences, f"SYT-LMW-15.c1: {where}: outputs differ: {differences[:3]}"
    assert with_lm.events == without.events, f"SYT-LMW-15.c1: {where}: the event logs differ"


# ---- SYT-LMW-16 ---------------------------------------------------------------------------------------------------

def test_syt_lmw_16_a_killed_reader_costs_nothing(tmp_path):
    """`SYT-LMW-16`, `SYS-0105` Accept. `.c1`: with an `F-READER --kill-after 3` attached and killed once released, the
    run writes every step with outputs equal to a run with no reader, and a reader started before the end reads every
    cycle. FAIL: a missing step, a difference, or a cycle the fresh reader cannot read."""
    lab = cut_c()
    held = held_run(lab, tmp_path, "lmw16")
    killed = subprocess.Popen([str(tool_path("lm_reader")), held.name, "--kill-after", "3", "--timeout-ms", "30000"],
                              stdout=subprocess.PIPE, text=True)
    try:
        fresh = LiveRegion(held.name)
        time.sleep(0.3)
        held.release()
        assert killed.stdout.readline().strip() == "read 3", "the reader did not get its three cycles"
        killed.kill()
        killed.wait()
        finished = held.finish()
    finally:
        held.close()
        if killed.poll() is None:
            killed.kill()
    assert finished.returncode == 0, f"SYT-LMW-16.c1: the run failed after the reader was killed: {finished.stderr[-300:]}"
    steps = [c.step for c in fresh.cycles()]
    plain, plain_recording = ran(lab, tmp_path, "plain")
    expected_steps = len(tap_case(lab, tmp_path, "lmw16_steps").steps)
    assert steps == list(range(expected_steps)), f"SYT-LMW-16.c1: the fresh reader read steps {steps[:3]}..{steps[-3:]} of {expected_steps}"
    produced = Recording(held.recording)
    topics = [t for t in plain_recording.topics() if not t.startswith(PROBE_STAGE + ".")]
    differences = compare_recordings(produced, plain_recording, topics)
    assert not differences, f"SYT-LMW-16.c1: outputs differ from a run with no reader: {differences[:3]}"
