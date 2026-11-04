# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`IMP-0119`: the contract's live measurement tests on Vantage, `RCT:SYT-LMS-01`..`09`
(`modules/interfaces/docs/resim_contract/RCT_Test_Spec.md`). `F-LM` is `F-LM-HELD` (`tests/support/livemeas_runs.py`),
`F-LM-STRESS` is `F-STRESS` (`lm_stress`), `F-CAM` the `camera` topology, `F-LM-TWICE` the recording-edit of
`SYT-ORC-13`. Each id appears in this file; each test cites the `Accept` it checks and states the FAIL side.

Where the contract's steps are open they are chosen so the case can fail:
- `SYT-LMS-03` runs 60 s, the contract's number;
- `SYT-LMS-04`: the suspended reader is a `dump --follow` stopped through the platform API before the release, on a
  ring of 2 so the writer laps it many times; "outputs" are every port of the two engine-run recordings but the held
  stage's;
- `SYT-LMS-05`: the reader's write is `F-READER --write-byte`, which faults on its read-only mapping;
- `SYT-LMS-07` and `-09` need a stage that reads `Cam`, which the topology has none of (see `test_vnt_live_measurement`):
  the held stage reads it, and for `-07` the bulk ring holds every write.
"""
from __future__ import annotations

import bisect
import json
import subprocess
import time

import pytest

from tests.support.engine_runs import Recording, bare_environment, compare_recordings, lab_compare, ran, tap_case, tool_path
from tests.support.engine_runs import point_at_recording
from tests.support.lab_cases import edit_recording, lab_case
from tests.support.livemeas_runs import (
    PROBE_STAGE, LiveRegion, held_run, inspect, pair_controls, parse_dump, resume, start_inspect, suspend, wait_until,
)

CAM = {"source": "Cam", "source_type": "adas.lab.LabImage"}
EXPECTED_STEPS_SLACK = 0


def cut_c():
    return lab_case("running_example", "cut_c")


def _end(held, region):
    held.release()
    finished = held.finish()
    assert finished.returncode == 0, f"the held run failed: {finished.stderr[-300:]}"
    return finished


def test_rct_syt_lms_01_description_first_everything_decodes(tmp_path):
    """`RCT:SYT-LMS-01`, `RCT:SYS-0023` Accept. `.c1`: one description, before the first cycle, and every port of every
    cycle decoded, by an inspector started with no search path. FAIL: a cycle before the description, or any
    undecodable port."""
    held = held_run(cut_c(), tmp_path, "lms01")
    try:
        region = LiveRegion(held.name)
        before = region.status()
        assert before.description_length > 0 and before.write_sequence == 0, \
            "RCT:SYT-LMS-01.c1: no description before the first cycle (a cycle came first, or the description is empty)"
        description = inspect("dump", held.name, "--description")
        assert description.out.count("recording:") == 1, f"RCT:SYT-LMS-01.c1: not exactly one description: {description.out[:200]}"
        follower = start_inspect(tmp_path, "lms01_dump", "dump", held.name, "--follow", env=bare_environment())
        time.sleep(0.3)
        held.release()
        dumped = follower.finish()
        held.finish()
    finally:
        held.close()
    lines = parse_dump(dumped.out)
    assert dumped.code == 0 and lines, f"RCT:SYT-LMS-01.c1: {dumped.err}"
    undecodable = [l for l in lines if l.body.startswith("<")]
    assert not undecodable, f"RCT:SYT-LMS-01.c1: undecodable ports {sorted({l.port for l in undecodable})}"


def _values_equal_the_recording(region, times, recording, lab_recording):
    """Every non-held value of every cycle against the newest message of its port by the step's time; the problems."""
    compare, messages = lab_compare()
    names = [p["name"] for p in region.description().ports]
    arrivals = {}
    for name in names:
        if name.startswith(PROBE_STAGE + "."):
            continue
        source = lab_recording if name.startswith("source.") else recording
        found = sorted(((t, i, p) for i, t, p in source.of(name)), key=lambda m: (m[0], m[1]))
        arrivals[name] = ([t for t, _i, _p in found], [p for _t, _i, p in found], source)
    problems = []
    for cycle in region.cycles():
        for value in cycle.values:
            name = names[value.port]
            if name not in arrivals or value.omitted:
                continue
            times_of, payloads, source = arrivals[name]
            index = bisect.bisect_right(times_of, times[cycle.step]) - 1
            if index < 0:
                problems.append(f"step {cycle.step} {name}: a value with no sample by then")
                continue
            schema, descriptor_set = source.schemas[name]
            if not compare.equal_outputs([payloads[index]], [value.payload], messages.MessageFactory(descriptor_set), schema).equal:
                problems.append(f"step {cycle.step} {name}: not the recording's value")
    return problems


def test_rct_syt_lms_02_one_cycle_per_step_unmixed(tmp_path):
    """`RCT:SYT-LMS-02`, `RCT:SYS-0024` Accept. `.c1`: consecutive steps, values equal the recording's. FAIL: a skipped or
    repeated step while not lapped, or a value from another step. `.c2`: on `F-LM-TWICE` the step with two runs of the
    paired stage has two values on each of its per-run ports, each equal to the recording's, in run order. FAIL: one
    value, another order, or no step with two runs."""
    lab = cut_c()
    tapped = tap_case(lab, tmp_path, "lms02_tap")
    times = {s["step"]: s["time_ns"] for s in tapped.steps}
    held = held_run(lab, tmp_path, "lms02a")
    try:
        region = LiveRegion(held.name)
        _end(held, region)
        recording = Recording(held.recording)
    finally:
        held.close()
    steps = [c.step for c in region.cycles()]
    assert steps == list(range(len(times))), f"RCT:SYT-LMS-02.c1: steps {steps[:3]}..{steps[-3:]} of {len(times)}"
    problems = _values_equal_the_recording(region, times, recording, Recording(lab.recording))
    assert not problems, f"RCT:SYT-LMS-02.c1: {problems[:4]}"

    all_sim = lab_case("running_example", "all_simulated")
    edited = edit_recording(all_sim, tmp_path / "paired.mcap", pair_controls)
    twice_tap = tap_case(all_sim, tmp_path, "lms02_twice_tap", change=lambda s: point_at_recording(s, edited))
    held = held_run(all_sim, tmp_path, "lms02b", change=lambda s: point_at_recording(s, edited))
    try:
        region = LiveRegion(held.name)
        _end(held, region)
        recording = Recording(held.recording)
    finally:
        held.close()
    names = [p["name"] for p in region.description().ports]
    at = {s["step"]: s["time_ns"] for s in twice_tap.steps}
    controls: dict[int, list[int]] = {}
    for _i, t, m in recording.decoded("B.control"):
        controls.setdefault(t, []).append(m.sig_header.measurement_counter)
    doubles = [k for k, t in at.items() if len(controls.get(t, [])) == 2]
    assert doubles, "RCT:SYT-LMS-02.c2: no step with two runs, so the case could not fail"
    cycles = {c.step: c for c in region.cycles()}
    for step in doubles:
        for port in ("control", "refSync", "out"):
            topic = f"B.{port}"
            expected = [m.sig_header.measurement_counter for _i, t, m in recording.decoded(topic) if t == at[step]]
            got = [recording.decode(topic, v.payload).sig_header.measurement_counter for v in cycles[step].values if names[v.port] == topic]
            assert got == expected and len(got) == 2, f"RCT:SYT-LMS-02.c2: step {step} {topic}: {got} against {expected}"


def test_rct_syt_lms_03_no_torn_read_accepted():
    """`RCT:SYT-LMS-03`, `RCT:SYS-0025` Accept. `.c1`: 60 s of `F-STRESS` (a 2-slot ring written at full speed, one
    reader copying in a loop): every accepted cycle decodes and matches the writer's log. FAIL: one mismatch or decode
    error."""
    done = subprocess.run([str(tool_path("lm_stress")), "--seconds", "60"], capture_output=True, text=True, timeout=300)
    fields = dict(part.split("=") for part in done.stdout.split())
    print(done.stdout.strip())
    assert done.returncode == 0 and int(fields["mismatches"]) == 0 and int(fields["decode_errors"]) == 0, \
        f"RCT:SYT-LMS-03.c1: {done.stdout.strip()} {done.stderr[-200:]}"
    assert int(fields["accepted"]) > 1000 and int(fields["steps"]) > 1000, f"RCT:SYT-LMS-03.c1: too little was written or read: {done.stdout.strip()}"


def test_rct_syt_lms_04_a_suspended_reader_costs_nothing(tmp_path):
    """`RCT:SYT-LMS-04`, `RCT:SYS-0026` Accept. `.c1`: with the inspector suspended throughout, equal step counts and
    identical outputs to a run with no reader. FAIL: fewer steps, a stall, or any difference."""
    lab = cut_c()
    plain, plain_recording = ran(lab, tmp_path, "plain")
    steps = len(tap_case(lab, tmp_path, "lms04_steps").steps)
    held = held_run(lab, tmp_path, "lms04", ring=2)
    try:
        follower = held.follow("dump", "--follow")
        time.sleep(0.4)
        suspend(follower.process)
        region = LiveRegion(held.name)
        held.release()
        finished = held.finish(timeout=120)
        written = region.status().write_sequence
        follower.kill()
    finally:
        held.close()
    assert finished.returncode == 0, f"RCT:SYT-LMS-04.c1: the run with a suspended reader failed (a stall?): {finished.stderr[-300:]}"
    assert written == steps, f"RCT:SYT-LMS-04.c1: {written} cycles written for {steps} steps"
    topics = [t for t in plain_recording.topics() if not t.startswith(PROBE_STAGE + ".")]
    differences = compare_recordings(Recording(held.recording), plain_recording, topics)
    assert not differences, f"RCT:SYT-LMS-04.c1: outputs differ: {differences[:3]}"


def test_rct_syt_lms_05_a_reader_cannot_write(tmp_path):
    """`RCT:SYT-LMS-05`, `RCT:SYS-0027` Accept. `.c1`: a test reader writing one byte into its mapping gets an access
    fault, and the next step is normal. FAIL: the write succeeds."""
    held = held_run(cut_c(), tmp_path, "lms05")
    try:
        region = LiveRegion(held.name)
        before = region.copy()
        wrote = subprocess.run([str(tool_path("lm_reader")), held.name, "--write-byte", "--timeout-ms", "10000"],
                               capture_output=True, text=True, timeout=60)
        assert "write succeeded" not in wrote.stdout and wrote.returncode != 0, \
            f"RCT:SYT-LMS-05.c1: the write did not fault: exit {wrote.returncode}, {wrote.stdout!r}"
        assert region.copy() == before, "RCT:SYT-LMS-05.c1: the writer's memory changed"
        _end(held, region)
    finally:
        held.close()
    assert [c.step for c in region.cycles()] == list(range(len(region.cycles()))) and region.status().outcome == 1, \
        "RCT:SYT-LMS-05.c1: the steps after the fault are not normal"


def test_rct_syt_lms_06_heartbeat_and_run_id(tmp_path):
    """`RCT:SYT-LMS-06`, `RCT:SYS-0028` Accept. `.c1`: the heartbeat rises at every step. FAIL: a step without a rise.
    `.c2`: two runs under one name have different run ids. FAIL: the same id."""
    lab = cut_c()
    steps = len(tap_case(lab, tmp_path, "lms06_steps").steps)
    first = held_run(lab, tmp_path / "one", "lms06")
    try:
        region = LiveRegion(first.name)
        run_id = region.status().run_id
        beats = []
        first.release()
        while region.status().status != 3:
            beats.append(region.status().heartbeat)
        first.finish()
    finally:
        first.close()
    assert region.status().heartbeat == steps, f"RCT:SYT-LMS-06.c1: heartbeat {region.status().heartbeat} after {steps} steps"
    assert beats == sorted(beats), "RCT:SYT-LMS-06.c1: the heartbeat fell"
    second = held_run(lab, tmp_path / "two", "lms06", distinct_from=run_id)
    try:
        other = LiveRegion(second.name).status().run_id
        second.release()
        second.finish()
    finally:
        second.close()
    assert other != run_id, "RCT:SYT-LMS-06.c2: the same run id twice"


def test_rct_syt_lms_07_images_by_reference(tmp_path):
    """`RCT:SYT-LMS-07`, `RCT:SYS-0029` Accept. `.c1`: on the camera topology no image bytes are inline and every
    reference resolves to its step. FAIL: inline bytes, or a reference to another step or nothing."""
    lab = lab_case("camera", "bulk")

    def enlarge(setup: dict) -> None:
        setup["outputs"]["livemeas"]["bulk_slot_count"] = 600
        setup["outputs"]["livemeas"]["bulk_slot_size"] = 69632

    held = held_run(lab, tmp_path, "lms07", change=enlarge, held_source=dict(CAM, bulk=True), ring=200)
    try:
        region = LiveRegion(held.name)
        _end(held, region)
    finally:
        held.close()
    names = [p["name"] for p in region.description().ports]
    references = 0
    for cycle in region.cycles():
        for value in cycle.values:
            if names[value.port] not in ("source.Cam", f"{PROBE_STAGE}.in"):
                continue
            assert value.payload == b"" and value.bulk is not None, f"RCT:SYT-LMS-07.c1: step {cycle.step}: image bytes inline or no reference"
            sequence, step, port, payload = region.bulk_slot(value.bulk[0])
            assert (sequence, step, port) == (value.bulk[1], cycle.step, value.port) and payload, \
                f"RCT:SYT-LMS-07.c1: step {cycle.step}: the reference resolves to step {step}"
            references += 1
    assert references >= 40, f"RCT:SYT-LMS-07.c1: only {references} references"


def test_rct_syt_lms_08_wrong_layout_version_refused(tmp_path):
    """`RCT:SYT-LMS-08`, `RCT:SYS-0030` Accept. `.c1`: a reader built with the layout version decremented refuses,
    naming both versions, and reads no cycle. FAIL: it attaches, or the message lacks a version."""
    held = held_run(cut_c(), tmp_path, "lms08")
    try:
        refused = subprocess.run([str(tool_path("lm_reader")), held.name, "--layout-version", "0", "--timeout-ms", "10000"],
                                 capture_output=True, text=True, timeout=60)
        held.release()
        held.finish()
    finally:
        held.close()
    assert refused.returncode == 6 and "layout version is 1" in refused.stderr and "reads layout version 0" in refused.stderr, \
        f"RCT:SYT-LMS-08.c1: exit {refused.returncode}, {refused.stderr!r}"
    assert refused.stdout.strip() == "", f"RCT:SYT-LMS-08.c1: the refusing reader printed {refused.stdout!r}"


def test_rct_syt_lms_09_oversize_port_marked(tmp_path):
    """`RCT:SYT-LMS-09`, `RCT:SYS-0031` Accept. `.c1`: on the camera topology with `bulk` empty, the 65536-byte frame is
    marked omitted in the steps it is the newest, the other frames inline, and the run completes. FAIL: the run stops,
    or the port is silently missing."""
    lab = lab_case("camera", "oversize")
    held = held_run(lab, tmp_path, "lms09", held_source=dict(CAM, bulk=False), ring=400)
    try:
        region = LiveRegion(held.name)
        finished = _end(held, region)
        recording = Recording(lab.recording)
    finally:
        held.close()
    names = [p["name"] for p in region.description().ports]
    cam = [(c.step, v) for c in region.cycles() for v in c.values if names[v.port] == "source.Cam"]
    omitted = [(s, v) for s, v in cam if v.omitted]
    assert finished.returncode == 0 and region.status().outcome == 1, "RCT:SYT-LMS-09.c1: the run did not complete"
    assert omitted, "RCT:SYT-LMS-09.c1: the oversize frame is silently missing (no value is marked omitted)"
    assert all(v.payload == b"" for _s, v in omitted), "RCT:SYT-LMS-09.c1: an omitted value carries bytes"
    assert [v for _s, v in cam if not v.omitted] and all(len(v.payload) < 4000 for _s, v in cam if not v.omitted), \
        "RCT:SYT-LMS-09.c1: another frame was marked omitted or is not inline"
    steps = [c.step for c in region.cycles()]
    assert steps == list(range(len(steps))) and steps and region.status().dropped_cycles == 0, "RCT:SYT-LMS-09.c1: a step is missing"
