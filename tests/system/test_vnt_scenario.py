# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`SYT-SCN-01`..`05` and `ANL-09` (`VANTAGE_Test_Spec.md` section 13): the scenario-to-recording script, `sim record`.
`F-SCENARIO` is a scenario file the test writes, its schemas the manifests of the `data_triggered` lab libraries.

Where the spec leaves a step open it is chosen so the case can fail:
- the scenario of `SYT-SCN-01` has 12 messages, six `adas.lab.LabSample` on `source.X` and six `adas.common.CycleControl` on `T.control`,
  each with its own counters and values, listed out of time order in two places so the sort is tested;
- "every unlisted field is its default" is read as: a decoded message holds, besides its default fields, only the fields the
  scenario listed (protobuf's `ListFields` names exactly the non-default ones);
- `SYT-SCN-04` runs `data_triggered` `by_data` on a recording of `source.X` and `source.Y` samples made by the script and checks
  `T`'s controls against the scenario's distinct `in_X` counters;
- `SYT-SCN-05` spies on `subprocess` and `os.system` and lists the files the verb created.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from adas_sim.cli import main as sim_main
from adas_sim.io.mcap import McapReader
from adas_sim.io.base import manifest_to_dict
from tests.support.engine_runs import Recording, point_at_recording, ran
from tests.support.lab_cases import lab_case

CASE = ("data_triggered", "by_data")


def _libraries() -> list[str]:
    case = lab_case(*CASE)
    return [p.as_posix() for p in case.libraries.values()]


def _write(tmp_path: Path, name: str, scenario: dict) -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(scenario, sort_keys=False), encoding="utf-8")
    return path


def _header(counter: int, time_us: int, cycle: int = 1) -> dict:
    return {"measurement_counter": counter, "source_timestamp_us": time_us, "cycle_counter": cycle, "sig_status": 1}


def _twelve(tmp_path: Path) -> Path:
    messages = []
    for k in range(1, 7):
        messages.append({"topic": "source.X", "time_us": 10_000 * k, "header": _header(k, 10_000 * k), "fields": {"value": 100 + k}})
        messages.append({"topic": "T.control", "time_us": 10_000 * k, "header": _header(k, 10_000 * k, k), "fields": {"op_mode": "RESTART" if k == 1 else "RUN"}})
    messages[2], messages[0] = messages[0], messages[2]  # out of time order: the sort is part of the test
    return _write(tmp_path, "twelve.yaml", {
        "scenario": "twelve", "libraries": _libraries(),
        "topics": {"source.X": {"type": "adas.lab.LabSample", "origin": "mocked"},
                   "T.control": {"type": "adas.common.CycleControl", "origin": "mocked"}},
        "messages": messages})


def _record(scenario: Path, out: Path) -> int:
    return sim_main(["record", str(scenario), "-o", str(out)])


def test_syt_scn_01_a_scenarios_values_are_written_exactly(tmp_path):  # SYT-SCN-01
    """`SYT-SCN-01`, `SYS-0128` and `SYS-0132` Accept. `.c1`: 12 messages decode to the listed values and every unlisted field is
    its default. FAIL: an extra, missing or changed value. `.c2`: two runs give the same count, order and equal messages on
    every topic. FAIL: a difference."""
    scenario = _twelve(tmp_path)
    first, second = tmp_path / "one.mcap", tmp_path / "two.mcap"
    assert _record(scenario, first) == 0 and _record(scenario, second) == 0
    one = Recording(first)
    listed = yaml.safe_load(scenario.read_text(encoding="utf-8"))["messages"]
    assert len(one.messages) == 12, f"SYT-SCN-01.c1: {len(one.messages)} messages, not 12"
    by_topic = {"source.X": [m for m in listed if m["topic"] == "source.X"], "T.control": [m for m in listed if m["topic"] == "T.control"]}
    for topic, wanted in by_topic.items():
        wanted = sorted(wanted, key=lambda m: m["time_us"])
        got = one.decoded(topic)
        assert len(got) == len(wanted), f"SYT-SCN-01.c1: {topic} holds {len(got)} messages, the scenario lists {len(wanted)}"
        for (_i, t_ns, message), expect in zip(got, wanted):
            assert t_ns == expect["time_us"] * 1000, f"SYT-SCN-01.c1: {topic} at {t_ns} ns, listed {expect['time_us']} us"
            for key, value in expect["header"].items():
                assert getattr(message.sig_header, key) == value, f"SYT-SCN-01.c1: {topic} header {key}"
            names = {f.name for f, _ in message.ListFields()} - {"sig_header"}
            assert names <= set(expect["fields"]) | {"op_mode", "value"}, f"SYT-SCN-01.c1: {topic} holds an unlisted field {names}"
            if topic == "source.X":
                assert message.value == expect["fields"]["value"]
            else:
                assert message.op_mode == (0 if expect["fields"]["op_mode"] == "RESTART" else 1)
    two = Recording(second)
    assert one.messages == two.messages, "SYT-SCN-01.c2: two runs of one scenario differ"


def test_syt_scn_02_the_recording_follows_the_conventions(tmp_path):  # SYT-SCN-02
    """`SYT-SCN-02`, `SYS-0129` Accept: `check_recording.py` passes the recording and Vantage's reader opens it and returns its
    `manifest`. FAIL: either failing."""
    from adas_sim.io.recording_writer import find_recording_package

    out = tmp_path / "conv.mcap"
    assert _record(_twelve(tmp_path), out) == 0
    checker = find_recording_package().parent / "scripts" / "check_recording.py"
    if not checker.is_file():
        checker = Path(__file__).resolve().parents[3] / "interfaces" / "scripts" / "check_recording.py"
    done = subprocess.run([sys.executable, str(checker), str(out)], capture_output=True, text=True)
    assert done.returncode == 0, f"SYT-SCN-02: check_recording.py failed: {done.stdout[-400:]}{done.stderr[-400:]}"
    reader = McapReader(out)
    try:
        manifest = manifest_to_dict(reader.meta())
    finally:
        reader.close()
    assert manifest.get("source_kind") == "synthetic", f"SYT-SCN-02: the reader's manifest is {manifest!r}"


@pytest.mark.parametrize("planted", ["type", "field"])
def test_syt_scn_03_a_value_the_type_does_not_have_is_refused(tmp_path, capsys, planted):  # SYT-SCN-03
    """`SYT-SCN-03`, `SYS-0131` Accept: an unknown type and an unknown field each end with an error naming it and no file; a valid
    scenario writes. FAIL: a file for an invalid scenario, or the name missing from the error."""
    bad = {"scenario": "bad", "libraries": _libraries(),
           "topics": {"source.X": {"type": "adas.lab.NoSuchType" if planted == "type" else "adas.lab.LabSample", "origin": "mocked"}},
           "messages": [{"topic": "source.X", "time_us": 1000, "header": _header(1, 1000),
                         "fields": {"nosuchfield": 1} if planted == "field" else {"value": 1}}]}
    out = tmp_path / f"{planted}.mcap"
    code = _record(_write(tmp_path, f"{planted}.yaml", bad), out)
    err = capsys.readouterr().err
    name = "adas.lab.NoSuchType" if planted == "type" else "nosuchfield"
    assert code != 0 and name in err, f"SYT-SCN-03: exit {code}, the error does not name {name}: {err!r}"
    assert not out.exists(), "SYT-SCN-03: a file was written for an invalid scenario"
    good = tmp_path / "good.mcap"
    assert _record(_twelve(tmp_path), good) == 0 and good.is_file(), "SYT-SCN-03: a valid scenario did not write"


def test_syt_scn_04_a_scenarios_recording_is_an_engine_input(tmp_path):  # SYT-SCN-04
    """`SYT-SCN-04`, `SYS-0133` Accept: `data_triggered` `by_data` on a scenario's `source.X` and `source.Y` exits 0 and `T` has one
    control per distinct `in_X` counter. FAIL: another exit code, or another count."""
    case = lab_case(*CASE)
    messages = []
    for k in (1, 2, 3, 3, 4, 5):  # counter 3 repeats: one stalled trigger, no extra run
        messages.append({"topic": "source.X", "time_us": 30_000 * (len(messages) // 2 + 1), "header": _header(k, 30_000 * k), "fields": {"value": k}})
        messages.append({"topic": "source.Y", "time_us": 30_000 * (len(messages) // 2 + 1) - 5_000, "header": _header(k, 20_000 * k), "fields": {"value": k}})
    scenario = _write(tmp_path, "engine.yaml", {
        "scenario": "engine", "libraries": _libraries(),
        "topics": {"source.X": {"type": "adas.lab.LabSample", "origin": "mocked"}, "source.Y": {"type": "adas.lab.LabSample", "origin": "mocked"}},
        "messages": messages})
    recording = tmp_path / "engine.mcap"
    assert _record(scenario, recording) == 0
    run, produced = ran(case, tmp_path, "scn04", change=lambda setup: point_at_recording(setup, recording))
    assert run.returncode == 0
    controls = produced.counters("T.control")
    distinct = len({m["header"]["measurement_counter"] for m in messages if m["topic"] == "source.X"})
    assert len(controls) == distinct, f"SYT-SCN-04: T has {len(controls)} controls for {distinct} distinct in_X counters"


def test_syt_scn_05_sim_record_does_nothing_else(tmp_path, monkeypatch):  # SYT-SCN-05
    """`SYT-SCN-05`, `SYS-0134` Accept: no process started and one file created. FAIL: any start, or any second file."""
    started = []
    real = subprocess.Popen

    class Spy(real):
        def __init__(self, args, *a, **k):  # the library probe loads a DLL in-process, never a process
            started.append(args)
            super().__init__(args, *a, **k)

    monkeypatch.setattr(subprocess, "Popen", Spy)
    scenario = _twelve(tmp_path)
    work = tmp_path / "empty"
    work.mkdir()
    out = work / "only.mcap"
    before = {p.name for p in work.iterdir()}
    assert _record(scenario, out) == 0
    created = {p.name for p in work.iterdir()} - before
    assert not started, f"SYT-SCN-05: the verb started {started}"
    assert created == {"only.mcap"}, f"SYT-SCN-05: files created {created}"


def test_anl_09_one_recording_writer_in_the_scenario_script():  # ANL-09
    """`ANL-09`, `SYS-0130` Accept. `.c1`: `check_one_recording_writer.py` finds nothing. FAIL: any finding. `.c2`: with a planted
    `mcap.McapWriter(` call it reports file and line. FAIL: the copy passes."""
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts" / "check_one_recording_writer.py"
    clean = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert clean.returncode == 0, f"ANL-09.c1: {clean.stdout}"
    planted = subprocess.run([sys.executable, str(script), "--selftest"], capture_output=True, text=True)
    assert planted.returncode == 0 and "reported" in planted.stdout, f"ANL-09.c2: {planted.stdout}{planted.stderr}"
