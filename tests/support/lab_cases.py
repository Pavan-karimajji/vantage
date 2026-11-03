# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""IMP-0040: find a lab case's run setup, recording and libraries in the lab build; copy a setup with one change or
a recording with one edit.

Test support for the system tests that run on the lab's cases (``F-CAT``, ``F-CASE``, ``F-SETUP-EDIT``,
``F-REC-EDIT``; ``VANTAGE_Test_Spec.md``).

``lab_case`` finds, for a topology, scenario and resim case, the run setup, the recording and the libraries the
lab wrote and built: ``<lab>/lab/<topology>/<scenario>.<case>.run.json``, ``<lab>/lab/<topology>/<scenario>.mcap``
and the ``index.json`` of the newest ``<lab>/conan_workarea/build-sil-*`` (``LAB_INDEX`` names one explicitly,
as the lab's own ``find_index`` does). ``<lab>`` is ``VANTAGE_LAB_ROOT`` or the ``vantage-lab`` checkout beside this
one. When any of it is missing, or the libraries are another operating system's, the test is skipped with the reason
printed; nothing is generated here.

``edit_setup`` copies the setup with one change. ``edit_recording`` reads the recording, lets the test change its
message list, and writes the result through the one Python recording writer, ``adas_recording`` of the ``interfaces``
package, found through the ``interfaces_python`` entry of the same ``index.json`` (no sibling ``interfaces``
checkout is needed). The topics, their schemas and origins, and the ``manifest`` are the original's; the writer
refuses what a recording must state, so an edited file is still a conforming recording.
"""
from __future__ import annotations

import copy
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping

import pytest
import yaml

VANTAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCENARIO = "base"

#: A recorded message: topic, logging time in integer ns, payload.
Message = tuple[str, int, bytes]


@dataclass(frozen=True)
class LabCase:
    """One resim case of one scenario of one topology, as the lab built it."""

    topology: str
    scenario: str
    case: str
    setup: Path          # the lab's run setup for this case; never edited in place
    recording: Path      # the scenario's recording
    index: Path          # the lab build's index.json
    libraries: dict      # stage name -> library path
    interfaces_python: Path | None  # the interfaces package's python/ folder, where adas_recording is
    expect: str          # the scenario's expectation: exact, diverges, refused_at_load
    case_entry: dict     # the catalogue's resim entry (``measured``, ``jump_to_ms`` ...)


def lab_root() -> Path:
    explicit = os.environ.get("VANTAGE_LAB_ROOT")
    return Path(explicit) if explicit else VANTAGE_ROOT.parent / "vantage-lab"


def _find_index(root: Path, topology: str) -> Path | None:
    explicit = os.environ.get("LAB_INDEX")
    if explicit:
        return Path(explicit)
    found = sorted((root / "conan_workarea").glob(f"build-sil-*/lab/{topology}/index.json"))
    return found[-1] if found else None


def _not_built(reason: str) -> None:
    message = f"lab not built: {reason}"
    print(message, file=sys.stderr)
    pytest.skip(message)


def lab_case(topology: str, case: str, scenario: str = DEFAULT_SCENARIO) -> LabCase:
    """The case's files, or ``pytest.skip`` with the reason when the lab is not built."""
    root = lab_root()
    catalogue = root / "catalogue" / f"{topology}.yaml"
    if not catalogue.is_file():
        _not_built(f"no catalogue file {catalogue}")
    declared = yaml.safe_load(catalogue.read_text(encoding="utf-8"))
    entry = next((s for s in declared.get("scenarios", []) if s.get("name") == scenario), None)
    if entry is None:
        _not_built(f"{catalogue} has no scenario {scenario!r}")
    case_entry = next((c for c in entry.get("resim", []) if c.get("name") == case), None)
    if case_entry is None:
        _not_built(f"{catalogue} scenario {scenario!r} has no resim case {case!r}")

    out_dir = root / "lab" / topology
    setup = out_dir / f"{scenario}.{case}.run.json"
    recording = out_dir / f"{scenario}.mcap"
    for needed in (setup, recording):
        if not needed.is_file():
            _not_built(f"{needed} is missing (run `lab_tools car {topology} {scenario}` and `lab_tools setup {topology} {scenario}`)")
    index = _find_index(root, topology)
    if index is None or not index.is_file():
        _not_built(f"no built libraries for {topology} (no conan_workarea/build-sil-*/lab/{topology}/index.json, no LAB_INDEX)")
    described = json.loads(index.read_text(encoding="utf-8"))
    libraries = {name: Path(item["library"]) for name, item in described.get("components", {}).items()}
    missing = [str(p) for p in libraries.values() if not p.is_file()]
    if missing:
        _not_built(f"{index} names libraries that are not on this machine (built on another operating system?): {missing[0]}")
    python_dir = described.get("interfaces_python")
    return LabCase(topology, scenario, case, setup, recording, index, libraries,
                   Path(python_dir) if python_dir else None, entry.get("expect", "exact"), dict(case_entry))


def edit_setup(case: LabCase, dest_dir: Path, change: Callable[[dict], None], *, name: str = "edited",
               outputs: Path | None = None) -> Path:
    """A copy of the case's run setup with ``change(setup_dict)`` applied, in ``dest_dir``; the lab's file is left
    alone. ``outputs``, when given, becomes ``outputs.path`` (so a run does not write into the lab's folder)."""
    setup = copy.deepcopy(json.loads(case.setup.read_text(encoding="utf-8")))
    change(setup)
    if outputs is not None:
        setup["outputs"]["path"] = Path(outputs).as_posix()
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{case.scenario}.{case.case}.{name}.run.json"
    path.write_text(json.dumps(setup, indent=1), encoding="utf-8")
    return path


def read_recording(path: Path) -> tuple[list[Message], dict, dict, Mapping[str, tuple[str, bytes]]]:
    """``(messages, manifest, topic_provenance, {topic: (schema name, descriptor set)})`` of one recording, in file
    order, read with the mcap package's reader."""
    from mcap.reader import make_reader

    messages: list[Message] = []
    schemas: dict[str, tuple[str, bytes]] = {}
    manifest: dict = {}
    provenance: dict = {}
    with open(path, "rb") as handle:
        reader = make_reader(handle)
        summary = reader.get_summary()
        for channel in summary.channels.values():
            schema = summary.schemas[channel.schema_id]
            schemas[channel.topic] = (schema.name, bytes(schema.data))
        for record in reader.iter_metadata():
            if record.name == "manifest":
                manifest = yaml.safe_load(record.metadata["yaml"])
            elif record.name == "topic_provenance":
                provenance = dict(record.metadata)
        for _schema, channel, message in reader.iter_messages(log_time_order=False):
            messages.append((channel.topic, message.log_time, bytes(message.data)))
    return messages, manifest, provenance, schemas


def edit_recording(case: LabCase, dest: Path, edit: Callable[[list[Message]], Iterable[Message]], *,
                   drop_topics: Iterable[str] = (), exclude_topics: Iterable[str] = ()) -> Path:
    """The case's recording with ``edit(messages)`` applied (it returns the messages to write, in order) written to
    ``dest`` through ``adas_recording``'s writer. A split into files is two calls with complementary edits.
    ``drop_topics`` leaves a topic out of the file altogether (the writer otherwise declares every topic of the
    original, so a topic whose messages were all removed would still be in the file's index). ``exclude_topics`` is
    that, and the manifest lists each such topic as ``excluded`` (a topic left out on purpose, ``R-SIM-6``)."""
    if case.interfaces_python is None:
        pytest.skip("lab not built: the index.json has no interfaces_python entry, so the recording writer cannot be found")
    if str(case.interfaces_python) not in sys.path:
        sys.path.insert(0, str(case.interfaces_python))
    from adas_recording.writer import McapRecorder, TopicSpec

    messages, manifest, provenance, schemas = read_recording(case.recording)
    edited = list(edit(list(messages)))
    excluded = set(exclude_topics)
    dropped = set(drop_topics) | excluded
    topics = {topic: TopicSpec(name, data, provenance.get(topic)) for topic, (name, data) in schemas.items()
              if topic not in dropped}
    block = {k: v for k, v in manifest.items() if k != "manifest_version"}
    if dropped and "record_policies" in block:
        block["record_policies"] = {k: ("excluded" if k in excluded else v)
                                    for k, v in block["record_policies"].items() if k in excluded or k not in dropped}
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with McapRecorder(dest, topics, block) as writer:
        for topic, log_time_ns, payload in edited:
            if log_time_ns % 1000:  # the writer's unit is the microsecond; never truncate a time silently
                raise ValueError(f"{topic}: logging time {log_time_ns} ns is not a whole number of microseconds")
            writer.write(topic, log_time_ns // 1000, payload)
    return dest
