# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`IMP-0121`: the inspector `vantage-inspect` (`SYT-INS-01`..`05`, `SYT-INS-07`..`12`; `SYT-INS-06` is gate `G4`'s,
`test_vnt_gate_g4.py`). Each test names its case id, cites the `Accept` it checks and asserts the FAIL side of the
case in its message. Live runs are `F-LM-HELD` (`tests/support/livemeas_runs.py`); a flawed live measurement is
`F-FLAWED-LM` (`lm_flawed`), checked while it is held open.

Where the spec leaves a step open it is chosen so the case can fail:
- `SYT-INS-02`: the engine is killed (by its pid) a few steps after the release, N is the step of the newest cycle in
  the shared memory, read here with `struct` and not with the inspector;
- `SYT-INS-05`: the paused reader is the `dump --follow` process itself, suspended through the platform API before the
  release and resumed after the run's end; N is the run's number of cycles minus the ring;
- `SYT-INS-04`: "libraries and interfaces build moved away" is a copy of the inspector executable alone in an empty
  directory, started with an environment that has no search path at all;
- `SYT-INS-12`: the "inspector built one lower" is two things: `F-READER --layout-version` of one lower against a
  held run, and the real inspector against a shared region whose layout version is one higher.
"""
from __future__ import annotations

import json
import mmap
import os
import re
import shutil
import struct
import time
from pathlib import Path

import pytest

from tests.support.engine_runs import (
    Recording, bare_environment, case_params, exact_cases, lab_compare, tool_path,
)
from tests.support.lab_cases import lab_case
from tests.support.livemeas_runs import (
    PROBE_STAGE, Following, LiveRegion, decode_body, held_run, inspect, inspector_exe, make_flawed, parse_dump,
    release_and_follow, resume, start_inspect, status_fields, suspend, wait_until,
)


def cut_c():
    return lab_case("running_example", "cut_c")


def _finish_all(held, *followers):
    finished = held.finish()
    assert finished.returncode == 0, f"the held run failed: {finished.stderr[-400:]}"
    return finished


# ---- SYT-INS-01 .. 05 -----------------------------------------------------------------------------------------------

def test_syt_ins_01_attach_prints_identity_and_state(tmp_path):
    """`SYT-INS-01`, `SYS-0075` Accept. `.c1`: while held, run id, geometry and status as the writer's, no cycle read.
    FAIL: a value differing, or a cycle read. `.c2`: after the run, status finished and the outcome. FAIL: status
    running."""
    held = held_run(cut_c(), tmp_path, "ins01")
    holder = held.hold_open()
    try:
        region = LiveRegion(held.name)
        while_held = inspect("attach", held.name)
        declared = json.loads(held.setup.read_text(encoding="utf-8"))["outputs"]["livemeas"]
        fields = status_fields(while_held.out)
        written = region.status()
        assert while_held.code == 0, while_held.err
        assert fields["status"] == "running", f"SYT-INS-01.c1: status {fields['status']!r} while held"
        assert fields["run id"] == f"{written.run_id:x}", f"SYT-INS-01.c1: run id {fields['run id']} is not the writer's {written.run_id:x}"
        assert fields["cycle slots"] == f"{declared['cycle_slot_count']} x {declared['cycle_slot_size']} bytes"
        assert fields["bulk slots"] == f"{declared['bulk_slot_count']} x {declared['bulk_slot_size']} bytes"
        assert fields["cycles written"] == "0" and "step " not in while_held.out, "SYT-INS-01.c1: a cycle was read while held"
        held.release()
        _finish_all(held)
        after = status_fields(inspect("attach", held.name).out)
        assert after["status"] == "finished", f"SYT-INS-01.c2: status {after['status']!r} after the run"
        assert after["outcome"] == "pass", f"SYT-INS-01.c2: outcome {after['outcome']!r}"
    finally:
        holder.kill()
        held.close()


def test_syt_ins_02_a_stopped_writer_is_reported_as_gone(tmp_path):
    """`SYT-INS-02`, `SYS-0076` Accept. `.c1`: no "writer gone" while it lives, "writer gone at step N" after, N the
    step of the newest cycle. FAIL: the line while it lives, or another N."""
    held = held_run(cut_c(), tmp_path, "ins02")
    holder = held.hold_open()
    try:
        region = LiveRegion(held.name)
        alive = inspect("attach", held.name)
        held.release()
        assert wait_until(lambda: region.status().write_sequence >= 5, 30, 0.0002), "the released run wrote no cycles"
        held.kill()
        assert region.status().status == 1, "the run finished before it was killed, so there is no stopped writer to report"
        newest = region.newest_step()
        gone = inspect("attach", held.name)
    finally:
        holder.kill()
        held.close()
    assert "writer gone" not in alive.out, f"SYT-INS-02.c1: the line while the writer lives: {alive.out}"
    assert f"writer gone at step {newest}" in gone.out.splitlines(), \
        f"SYT-INS-02.c1: expected 'writer gone at step {newest}', got: {gone.out}"


def test_syt_ins_03_dump_prints_one_decoded_line_per_value(tmp_path):
    """`SYT-INS-03`, `SYS-0077` Accept. `.c1`: step order, every field equal to the recording's message (decoded by
    the lab's decoder, compared by `equal_outputs`), every recorded value of a simulated stage printed. FAIL: a line
    out of order, a field differing, or a value not printed."""
    lab = cut_c()
    held = held_run(lab, tmp_path, "ins03")
    try:
        (dumped,) = release_and_follow(held, ("dump", "--follow"))
        _finish_all(held)
    finally:
        held.close()
    compare, messages = lab_compare()
    recording = Recording(lab.recording)
    lines = [l for l in parse_dump(dumped.out) if not l.port.startswith(PROBE_STAGE + ".")]
    assert dumped.code == 0 and lines, f"dump printed nothing: {dumped.err}"
    steps = [l.step for l in lines]
    assert steps == sorted(steps), "SYT-INS-03.c1: a line is out of step order"
    recorded: dict[str, dict[int, bytes]] = {}
    printed: dict[str, set[int]] = {}
    differences = []
    for line in lines:
        assert line.port in recording.schemas, f"SYT-INS-03.c1: port {line.port} printed but the recording has no such topic"
        if line.port not in recorded:
            recorded[line.port] = {}
            for _i, _t, payload in recording.of(line.port):
                recorded[line.port].setdefault(recording.decode(line.port, payload).sig_header.measurement_counter, payload)
        message = decode_body(recording, line.port, line.body)
        counter = message.sig_header.measurement_counter
        printed.setdefault(line.port, set()).add(counter)
        if counter not in recorded[line.port]:
            differences.append(f"step {line.step} {line.port}: counter {counter} is not in the recording")
            continue
        schema_name, descriptor_set = recording.schemas[line.port]
        result = compare.equal_outputs([recorded[line.port][counter]], [message.SerializeToString(deterministic=True)],
                                       messages.MessageFactory(descriptor_set), schema_name)
        if not result.equal:
            differences.append(f"step {line.step} {line.port} counter {counter}: {result.reason}")
    assert not differences, f"SYT-INS-03.c1: a field differs: {differences[:5]}"
    not_printed = []
    for stage in ("A", "B", "D", "E"):  # the simulated stages of cut_c
        for port in ("out", "refSync", "compState"):
            topic = f"{stage}.{port}"
            for counter in recorded.get(topic, {}):
                if counter not in printed.get(topic, set()):
                    not_printed.append((topic, counter))
            assert printed.get(topic), f"SYT-INS-03.c1: nothing printed for {topic}"
    assert not not_printed, f"SYT-INS-03.c1: recorded values never printed: {not_printed[:5]}"


def test_syt_ins_04_no_bindings_checkout_or_library_needed(tmp_path):
    """`SYT-INS-04`, `SYS-0078` Accept. `.c1`: `attach`, `dump` and `check` give identical output from an empty
    directory with every search path cleared and only the inspector executable present, and from the build.
    FAIL: a difference or a start failure."""
    lab = cut_c()
    alone = tmp_path / "empty"
    alone.mkdir()
    copy = alone / inspector_exe().name
    shutil.copyfile(inspector_exe(), copy)
    bare = bare_environment()
    held = held_run(lab, tmp_path, "ins04")
    try:
        normal = {verb: held.follow(verb, *(["--follow"] if verb == "dump" else []), tag=f"n_{verb}") for verb in ("dump", "check")}
        isolated = {verb: Following([str(copy), verb, held.name] + (["--follow"] if verb == "dump" else []), alone, f"i_{verb}", env=bare)
                    for verb in ("dump", "check")}
        attach_normal = inspect("attach", held.name)
        attach_isolated = inspect("attach", held.name, exe=copy, cwd=alone, env=bare)
        time.sleep(0.3)
        held.release()
        results = {(kind, verb): f.finish() for kind, group in (("normal", normal), ("isolated", isolated)) for verb, f in group.items()}
        _finish_all(held)
    finally:
        held.close()
    assert attach_isolated.code == 0, f"SYT-INS-04.c1: attach did not start from an empty directory: {attach_isolated.err}"
    assert attach_isolated.out == attach_normal.out, "SYT-INS-04.c1: attach output differs"
    for verb in ("dump", "check"):
        isolated_result, normal_result = results[("isolated", verb)], results[("normal", verb)]
        assert isolated_result.code == normal_result.code == 0, f"SYT-INS-04.c1: {verb} exits {isolated_result.code}/{normal_result.code}: {isolated_result.err}"
        assert isolated_result.out == normal_result.out, f"SYT-INS-04.c1: {verb} output differs"
    assert results[("normal", "dump")].out.strip(), "SYT-INS-04.c1: dump printed nothing, so equal outputs prove nothing"


def test_syt_ins_05_skipped_steps_are_reported(tmp_path):
    """`SYT-INS-05`, `SYS-0079` Accept. `.c1`: with a ring of 2 and `dump --follow` paused over the run and resumed,
    "N steps skipped", N the steps overwritten. FAIL: no line, or another N. `.c2`: with a ring holding the run, no
    such line. FAIL: one."""
    lab = cut_c()
    held = held_run(lab, tmp_path, "ins05a", ring=2)
    try:
        follower = held.follow("dump", "--follow")
        time.sleep(0.4)  # attached, nothing to read yet
        suspend(follower.process)
        region = LiveRegion(held.name)
        held.release()
        assert wait_until(lambda: region.status().status == 3, 60, 0.01), "the run did not finish"
        written = region.status().write_sequence
        resume(follower.process)
        paused = follower.finish()
        _finish_all(held)
    finally:
        held.close()
    skipped = re.findall(r"^(\d+) steps skipped$", paused.out, re.MULTILINE)
    assert skipped == [str(written - 2)], \
        f"SYT-INS-05.c1: expected one line '{written - 2} steps skipped' (cycles {written}, ring 2), got {skipped}"

    held = held_run(lab, tmp_path, "ins05b")
    try:
        (steady,) = release_and_follow(held, ("dump", "--follow"))
        _finish_all(held)
    finally:
        held.close()
    assert "steps skipped" not in steady.out, "SYT-INS-05.c2: a skip line with a ring that holds the run"
    assert parse_dump(steady.out), "SYT-INS-05.c2: nothing was printed, so no skip line proves nothing"


# ---- SYT-INS-07 .. 11: flawed live measurements ----------------------------------------------------------------------

def _flawed(tmp_path, tag, flaw, *, scenario="base", case="cut_c", check_args=(), recording=False):
    lab = lab_case("running_example", case, scenario)
    held = held_run(lab, tmp_path, tag)
    try:
        args = tuple(check_args) + (("--recording", str(lab.recording)) if recording else ())
        made = make_flawed(held, "f", *flaw, check_args=args)
        held.finish()
    finally:
        held.close()
    return made


def _lines(result) -> list[str]:
    return [line for line in result.out.splitlines() if line.strip()]


def test_syt_ins_07_a_gap_in_the_steps(tmp_path):
    """`SYT-INS-07`, `SYS-0081` Accept. `.c1`: `--skip-step 7` gives a finding naming 6 and 8. FAIL: none, or other
    numbers. `.c2`: the clean one gives none. FAIL: a finding."""
    flawed = _flawed(tmp_path, "ins07a", ("--skip-step", "7"))
    assert flawed.result.code == 1 and _lines(flawed.result) == ["step 8 follows step 6, expected step 7"], \
        f"SYT-INS-07.c1: {flawed.result.code} {flawed.result.out}"
    clean = _flawed(tmp_path, "ins07b", ())
    assert clean.result.code == 0 and not _lines(clean.result), f"SYT-INS-07.c2: a finding on the clean one: {clean.result.out}"


def test_syt_ins_08_a_run_without_its_ref_sync(tmp_path):
    """`SYT-INS-08`, `SYS-0082` Accept. `.c1`: `--drop-ref-sync` (one `B` refSync) gives a finding naming `B`, its step
    and `refSync`. FAIL: none, or another stage or port. `.c2`: the clean one gives none. FAIL: a finding."""
    flawed = _flawed(tmp_path, "ins08a", ("--drop-ref-sync", "B"))
    step = next(int(n.split("=")[1]) for n in flawed.notes if n.startswith("flaw step="))
    assert flawed.result.code == 1 and f"step {step}: stage B run 0 has no value on port B.refSync" in _lines(flawed.result), \
        f"SYT-INS-08.c1: {flawed.result.code} {flawed.result.out}"
    clean = _flawed(tmp_path, "ins08b", ())
    assert clean.result.code == 0 and not _lines(clean.result), f"SYT-INS-08.c2: a finding on the clean one: {clean.result.out}"


def test_syt_ins_09_a_value_that_is_not_the_recordings(tmp_path):
    """`SYT-INS-09`, `SYS-0083` Accept. `.c1`: `check --recording` on `--alter-byte` names the step and port. FAIL:
    none. (`.c2`, every exact case on `F-LM-HELD` gives none, is the next test.)"""
    flawed = _flawed(tmp_path, "ins09", ("--alter-byte", "10", "source.X"), recording=True)
    assert flawed.result.code == 1 and any(l.startswith("step 10: port source.X (origin ORIGIN_") and "payload bytes differ from the recording" in l
                                          for l in _lines(flawed.result)), \
        f"SYT-INS-09.c1: {flawed.result.code} {flawed.result.out}"


@pytest.mark.parametrize("topology,scenario,case", case_params(exact_cases()))
def test_syt_ins_09_c2_every_exact_case_gives_no_finding(tmp_path, topology, scenario, case):
    """`SYT-INS-09.c2`: `check --recording` on the exact case run on `F-LM-HELD` gives none. FAIL: a finding."""
    lab = lab_case(topology, case, scenario)
    held = held_run(lab, tmp_path, "ins09c2")
    try:
        (checked,) = release_and_follow(held, ("check", "--recording", str(lab.recording)))
        _finish_all(held)
    finally:
        held.close()
    assert checked.code == 0 and not _lines(checked), f"SYT-INS-09.c2: {topology}/{scenario}/{case}: {checked.out[:600]}"


def test_syt_ins_10_a_badge_count_that_decreases(tmp_path):
    """`SYT-INS-10`, `SYS-0084` Accept. `.c1`: `--lower-badge` on `missing_sample` gives a finding naming badge, subject
    and both steps. FAIL: none. `.c2`: the clean one gives none. FAIL: a finding."""
    flawed = _flawed(tmp_path, "ins10a", ("--lower-badge",), scenario="missing_sample", case="all_simulated")
    pattern = re.compile(r"^badge KIND_\w+ of \S+: count \d+ at step \d+ is lower than \d+ at step \d+$")
    assert flawed.result.code == 1 and len(_lines(flawed.result)) == 1 and pattern.match(_lines(flawed.result)[0]), \
        f"SYT-INS-10.c1: {flawed.result.code} {flawed.result.out}"
    clean = _flawed(tmp_path, "ins10b", (), scenario="missing_sample", case="all_simulated")
    assert clean.result.code == 0 and not _lines(clean.result), f"SYT-INS-10.c2: a finding on the clean one: {clean.result.out}"


def test_syt_ins_11_findings_and_the_exit_code(tmp_path):
    """`SYT-INS-11`, `SYS-0085` Accept. `.c1`: each flawed live measurement of `SYT-INS-06.c2` and `SYT-INS-07`..`10`
    exits 1 with as many lines as planted flaws, one per line. FAIL: exit 0, or another number of lines. `.c2`: a clean
    lab run exits 0 with no finding line. FAIL: any."""
    flaws = [
        ("drop-port", ("--drop-port", "10", "B.out"), {}),
        ("skip-step", ("--skip-step", "7"), {}),
        ("drop-ref-sync", ("--drop-ref-sync", "B"), {}),
        ("alter-byte", ("--alter-byte", "10", "source.X"), {"recording": True}),
        ("lower-badge", ("--lower-badge",), {"scenario": "missing_sample", "case": "all_simulated"}),
    ]
    for tag, flaw, extra in flaws:
        made = _flawed(tmp_path, f"ins11_{tag}", flaw, **extra)
        lines = _lines(made.result)
        assert made.result.code == 1 and len(lines) == 1, f"SYT-INS-11.c1: {tag}: exit {made.result.code}, {len(lines)} lines: {lines}"
    lab = cut_c()
    held = held_run(lab, tmp_path, "ins11_clean")
    try:
        (clean,) = release_and_follow(held, ("check", "--recording", str(lab.recording)))
        _finish_all(held)
    finally:
        held.close()
    assert clean.code == 0 and not _lines(clean), f"SYT-INS-11.c2: {clean.code} {clean.out}"


# ---- SYT-INS-12 --------------------------------------------------------------------------------------------------

def test_syt_ins_12_the_other_exits(tmp_path):
    """`SYT-INS-12`, `SYS-0086` Accept. `.c1`: exit 2 for an unknown verb, naming it. FAIL: another code, or none naming
    the verb. `.c2`: exit 6 naming the name for a name nobody holds, and exit 6 naming both versions with no cycle read
    for another layout version. FAIL: another code, or a missing name or version."""
    unknown = inspect("nosuchverb", "somename")
    assert unknown.code == 2 and "nosuchverb" in unknown.err, f"SYT-INS-12.c1: {unknown.code} {unknown.err}"
    nobody = f"vnt_nobody_{os.getpid()}"
    none = inspect("attach", nobody)
    assert none.code == 6 and nobody in none.err, f"SYT-INS-12.c2: {none.code} {none.err}"

    held = held_run(cut_c(), tmp_path, "ins12")
    try:
        lower = tool_path("lm_reader")
        import subprocess
        refused = subprocess.run([str(lower), held.name, "--layout-version", "0", "--timeout-ms", "5000"],
                                 capture_output=True, text=True, timeout=60)
        assert refused.returncode == 6 and "layout version is 1" in refused.stderr and "reads layout version 0" in refused.stderr, \
            f"SYT-INS-12.c2: F-READER one lower: {refused.returncode} {refused.stderr}"
        assert "step " not in refused.stdout, "SYT-INS-12.c2: a cycle was read by the refusing reader"
        held.release()
        held.finish()
    finally:
        held.close()

    # The real inspector against a region of another layout version (one higher), made through the platform API.
    name = f"vnt_ins12_layout_{os.getpid()}"
    size = 80 + 8 + 2 * 256
    region = mmap.mmap(-1, size, tagname=name) if os.name == "nt" else None
    if region is None:
        pytest.skip("the layout version one higher is made through a Windows named mapping here")
    try:
        header = struct.pack("<IIQIIIIIIIIIxxxxQQQ", 0x534D564C, 2, 9, 1, 1, 0, 8, 0, 2, 256, 1, 64, 0, 0, 0)
        region[: len(header)] = header
        other = inspect("attach", name)
    finally:
        region.close()
    assert other.code == 6 and "layout version is 2" in other.err and "reads layout version 1" in other.err, \
        f"SYT-INS-12.c2: the inspector on another layout version: {other.code} {other.err}"
    assert "step " not in other.out, "SYT-INS-12.c2: a cycle was read"
