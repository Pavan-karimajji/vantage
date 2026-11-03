# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""RCT:WP-13 (`IMP-0048`, `IMP-0052`, `IMP-0059`): an engine-run recording, and Vantage's reader, held to the
recording conventions of `RCT_Architecture.md` section 6a by the conformance check of the `interfaces` package.

  SYT-REC-03  .c3  `simengine` run twice on `running_example` `cut_c` with `outputs.path` set gives
                   byte-identical files.
  SYT-REC-04  .c1  `check_recording.py` finds nothing in the engine-run recording.
              .c2  its times and order (`log_time` never back, `publish_time` equal to it, equal times in the
                   engine's own order).
              .c3  Vantage's own reader (the C++ `Reader`, through `recording_dump`) opens the lab's `base.mcap`
                   and the engine-run recording and returns every topic, schema, origin, `manifest`,
                   `config_bundle` entry and message as the file holds it.
  IMP-0059         the engine-run recording's `config_bundle` names exactly the simulated stages, never `C`.

`check_recording.py` and its sibling checks are taken from the `adas-interfaces` package the build names
(`adas_recording.path`), beside its `python/` folder. A test whose lab output or build is missing skips with the
reason printed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from mcap.reader import make_reader

from adas_sim.diagnostics.errors import EnvironmentError_
from adas_sim.engine.bridge import resolve_simengine_executable
from adas_sim.io.recording_writer import find_recording_package
from tests.support.engine_runs import tool_path
from tests.support.lab_cases import edit_setup, lab_case

VANTAGE_ROOT = Path(__file__).resolve().parents[2]
_DUMP_CANDIDATES = (
    VANTAGE_ROOT / "conan_workarea" / "build-gtest-vs2026" / "tests" / "Release" / "recording_dump.exe",
    VANTAGE_ROOT / "conan_workarea" / "build-gtest-ubuntu_gcc" / "tests" / "recording_dump",
)
_KNOWN_BLOCKS = {"manifest", "topic_provenance", "config_bundle"}


def _skip(reason: str):
    print(reason, file=sys.stderr)
    pytest.skip(reason)


@pytest.fixture(scope="module")
def engine() -> Path:
    try:
        return resolve_simengine_executable()
    except EnvironmentError_ as exc:
        _skip(f"no built simengine found: {exc}")


@pytest.fixture(scope="module")
def checks_dir() -> Path:
    try:
        return find_recording_package().parent / "scripts"
    except EnvironmentError_ as exc:
        _skip(f"recording checks not found: {exc}")


@pytest.fixture(scope="module")
def dump_exe() -> Path:
    for candidate in _DUMP_CANDIDATES:
        if candidate.is_file():
            return candidate
    _skip(f"recording_dump is not built (build.bat -t gtest); looked for {[str(c) for c in _DUMP_CANDIDATES]}")


@pytest.fixture(scope="module")
def rewrite_exe() -> Path:
    return tool_path("rewrite_recording")


@pytest.fixture(scope="module")
def cut_c():
    return lab_case("running_example", "cut_c")


def _engine_run(engine: Path, case, directory: Path, label: str) -> Path:
    """One `simengine` run of the lab's case with `outputs.path` in `directory`; its recording."""
    recording = directory / f"{label}.mcap"

    def change(setup: dict) -> None:
        setup["outputs"]["livemeas"]["name"] = f"{setup['outputs']['livemeas']['name']}_{label}"

    setup = edit_setup(case, directory, change, name=label, outputs=recording)
    done = subprocess.run([str(engine), str(setup)], capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, f"simengine exit {done.returncode}: {done.stderr[-800:]}"
    assert recording.is_file()
    return recording


@pytest.fixture(scope="module")
def engine_recording(engine, cut_c, tmp_path_factory) -> Path:
    return _engine_run(engine, cut_c, tmp_path_factory.mktemp("engine_run"), "first")


def _check(checks_dir: Path, recording: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(checks_dir / "check_recording.py"), str(recording)], capture_output=True, text=True)


def test_syt_rec_03_c3_the_engines_writer_given_the_same_arguments_gives_the_same_bytes(rewrite_exe, engine_recording, tmp_path):  # SYT-REC-03.c3
    """`IMP-0069`: the recording is rewritten twice through the engine's reader and writer (`rewrite_recording`); the
    two files are compared with each other and with the engine's own. Two engine runs are not compared: each states
    its `process_nonce` (`IMP-0063`), so their `manifest` differs by design."""
    first, second = tmp_path / "first.mcap", tmp_path / "second.mcap"
    for target in (first, second):
        done = subprocess.run([str(rewrite_exe), str(engine_recording), str(target)], capture_output=True, text=True, timeout=300)
        assert done.returncode == 0, f"rewrite_recording exit {done.returncode}: {done.stderr[-400:]}"
    assert first.read_bytes() == second.read_bytes(), "SYT-REC-03.c3: any byte differs between two writer calls"
    assert first.read_bytes() == engine_recording.read_bytes(), "SYT-REC-03.c3: any byte differs from the engine's own file"


def test_syt_rec_04_c1_the_conformance_check_finds_nothing_in_the_engine_run_recording(checks_dir, engine_recording):  # SYT-REC-04.c1
    done = _check(checks_dir, engine_recording)
    assert done.returncode == 0, done.stdout + done.stderr


def test_the_lab_recording_conforms_too(checks_dir, cut_c):  # SYT-REC-04, the F-LAB half
    done = _check(checks_dir, cut_c.recording)
    assert done.returncode == 0, done.stdout + done.stderr


def _engine_topic_order(setup: dict) -> list[str]:
    """The order the engine offers its topics to the writer in each step: every stage's `pro` ports in stage order,
    then the `req` ports, a `req` port under its producer's address, each topic once."""
    order: list[str] = []
    for want in ("pro", "req"):
        for stage in setup["stages"]:
            if stage["mode"] == "off":
                continue
            wired = {item["port"]: f"{item['producer']}.{item['producer_port']}" for item in stage["inputs"]}
            for port in stage["ports"]:
                if port["dir"] != want:
                    continue
                topic = wired.get(port["name"], f"{stage['name']}.{port['name']}") if want == "req" else f"{stage['name']}.{port['name']}"
                if topic not in order:
                    order.append(topic)
    return order


def _in_the_engines_order(topics: list[str], setup: dict) -> bool:
    """`IMP-0061`: the messages of one instant are, first, each run committed in it -- the stage's `control`, then the
    outputs it committed -- and then every other recorded topic in the topic list's order
    (`_engine_topic_order`)."""
    position = {topic: i for i, topic in enumerate(_engine_topic_order(setup))}
    outputs = {stage["name"]: {f"{stage['name']}.{p['name']}" for p in stage["ports"] if p["dir"] == "pro"}
               for stage in setup["stages"] if stage["mode"] == "simulate"}
    i = 0
    while i < len(topics) and topics[i].endswith(".control") and topics[i].split(".", 1)[0] in outputs:
        own = outputs[topics[i].split(".", 1)[0]]
        i += 1
        seen: set[str] = set()  # the run's outputs, each once, in the order the run committed them
        while i < len(topics) and topics[i] in own and topics[i] not in seen:
            seen.add(topics[i])
            i += 1
    rest = [position[t] for t in topics[i:]]
    return rest == sorted(rest)


def test_syt_rec_04_c2_times_never_go_back_and_equal_times_keep_the_engines_order(engine_recording, cut_c):  # SYT-REC-04.c2
    setup = json.loads(cut_c.setup.read_text(encoding="utf-8"))
    with engine_recording.open("rb") as handle:
        messages = [(channel.topic, message.log_time, message.publish_time)
                    for _schema, channel, message in make_reader(handle).iter_messages(log_time_order=False)]
    assert messages, "the engine-run recording holds no message"
    previous = None
    equal_time_run: list[str] = []
    for topic, log_time, publish_time in messages:
        assert publish_time == log_time, f"{topic}: publish_time {publish_time} differs from log_time {log_time}"
        assert previous is None or log_time >= previous, f"{topic}: log_time {log_time} is before {previous}"
        if log_time != previous:
            equal_time_run = []
        equal_time_run.append(topic)
        assert _in_the_engines_order(equal_time_run, setup), (
            f"messages at {log_time} ns are out of the engine's order: {equal_time_run}")
        previous = log_time


def _canonical(topic: str) -> str:
    """`simcore::io::CanonicalTopic`: `/<producer>/<port>`, only the first dot a slash."""
    name = topic.strip("/").replace("/", ".")
    producer, dot, rest = name.partition(".")
    return f"/{producer}/{rest}" if dot else f"/{name}"


def _what_the_file_holds(path: Path) -> dict:
    """The file read with the mcap package alone: topics, blocks and messages in file order."""
    topics: dict[str, dict] = {}
    blocks: dict[str, dict[str, str]] = {}
    with path.open("rb") as handle:
        reader = make_reader(handle)
        for record in reader.iter_metadata():
            blocks.setdefault(record.name, dict(record.metadata))
        provenance = blocks.get("topic_provenance", {})
        summary = reader.get_summary()
        for channel in summary.channels.values():
            schema = summary.schemas[channel.schema_id]
            topics[_canonical(channel.topic)] = {
                "schema_name": schema.name, "origin": provenance[channel.topic],
                "schema_hex": bytes(schema.data).hex()}
        messages = [(_canonical(channel.topic), message.log_time, bytes(message.data).hex())
                    for _schema, channel, message in reader.iter_messages(log_time_order=False)]
    return {"topics": topics, "blocks": blocks, "messages": messages}


def _what_vantages_reader_returns(dump_exe: Path, path: Path) -> dict:
    done = subprocess.run([str(dump_exe), str(path)], capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, f"Vantage's reader refused {path.name}: {done.stderr}"
    topics: dict[str, dict] = {}
    blocks: dict[str, dict[str, str]] = {}
    messages = []
    for line in done.stdout.splitlines():
        item = json.loads(line)
        if item["kind"] == "topic":
            topics[item["topic"]] = {k: item[k] for k in ("schema_name", "origin", "schema_hex")}
        elif item["kind"] == "block":
            blocks.setdefault(item["block"], {})[bytes.fromhex(item["key_hex"]).decode("utf-8")] = bytes.fromhex(item["hex"]).decode("utf-8")
        else:
            messages.append((item["topic"], item["log_time_ns"], item["hex"]))
    return {"topics": topics, "blocks": blocks, "messages": messages}


@pytest.mark.parametrize("which", ["lab", "engine"])
def test_syt_rec_04_c3_vantages_reader_returns_everything_the_file_holds(dump_exe, cut_c, engine_recording, which):  # SYT-REC-04.c3
    path = cut_c.recording if which == "lab" else engine_recording
    held = _what_the_file_holds(path)
    returned = _what_vantages_reader_returns(dump_exe, path)

    assert held["blocks"].keys() <= _KNOWN_BLOCKS, f"a metadata block Vantage's reader does not read: {sorted(held['blocks'])}"
    assert returned["topics"] == held["topics"], "a changed topic, schema or origin"
    assert returned["messages"] == held["messages"], "a missing message, or a changed topic, log_time or byte"
    for name in ("manifest", "config_bundle"):
        assert returned["blocks"].get(name) == held["blocks"].get(name), f"the {name} block was not returned as written"


def test_imp_0059_the_engine_run_recording_embeds_the_simulated_stages_bundles_and_never_the_measured_one(engine_recording):  # IMP-0059
    bundle = _what_the_file_holds(engine_recording)["blocks"].get("config_bundle")
    assert bundle, "no config_bundle block"
    assert {key.split("/", 1)[0] for key in bundle} == {"A", "B", "D", "E"}  # C is measured in cut_c
    for stage in ("A", "B", "D", "E"):
        files = {key.split("/", 1)[1]: text for key, text in bundle.items() if key.startswith(f"{stage}/")}
        assert "bundle.sha256" in files and len(files) > 1, f"stage {stage} holds {sorted(files)}"
