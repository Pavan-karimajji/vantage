# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`load_scenario` (`IMP-0126`, `SYS-0128`, `SYS-0131`): reads a scenario file and checks every type and field of it against the
interface schemas before anything is written.

A scenario is YAML:

    scenario: <name>
    libraries: [<library>, ...]       # the schemas are the descriptor sets their manifests carry (R-SIM-11)
    topics:
      <topic>: {type: <full message name>, origin: measured|truth|mocked|simulated|overridden}
    messages:
      - {topic: <topic>, time_us: <whole microseconds>, header: {measurement_counter: .., source_timestamp_us: .., cycle_counter: .., sig_status: ..}, fields: {<field>: <value>, ...}}

`header` sets fields of the message's `sig_header`, `fields` every other field; a field not listed keeps its default. A type or a field
the schemas do not have, a topic nobody declared and an origin nobody stated end the load naming it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml

from adas_sim.diagnostics.errors import AuthoringError

ORIGINS = ("measured", "truth", "mocked", "simulated", "overridden")
_TOP = {"scenario", "libraries", "topics", "messages"}
_TOPIC = {"type", "origin"}
_MESSAGE = {"topic", "time_us", "header", "fields"}


@dataclass(frozen=True)
class ScenarioMessage:
    topic: str
    time_us: int
    header: Mapping[str, Any]
    fields: Mapping[str, Any]


@dataclass(frozen=True)
class Scenario:
    name: str
    topics: Mapping[str, tuple[str, str]]  # topic -> (full message name, origin)
    messages: tuple[ScenarioMessage, ...]
    descriptor_set: bytes
    classes: Mapping[str, type] = field(default_factory=dict)  # full message name -> message class


def _fail(found: str, where: str, expected: str, hint: str = "") -> AuthoringError:
    return AuthoringError(expected=expected, found=found, where=where, hint=hint)


def _check_keys(node: Mapping, allowed: set[str], where: str) -> None:
    for key in node:
        if key not in allowed:
            raise _fail(f"key {key!r}", where, f"one of {sorted(allowed)}")


def _merged_descriptor_set(libraries: list[Path]) -> bytes:
    from google.protobuf import descriptor_pb2

    from adas_sim.resolve.probe import probe_manifest

    merged = descriptor_pb2.FileDescriptorSet()
    seen: set[str] = set()
    for library in libraries:
        manifest = probe_manifest(library)
        one = descriptor_pb2.FileDescriptorSet()
        one.ParseFromString(manifest.descriptor_set)
        for file_proto in one.file:
            if file_proto.name not in seen:
                seen.add(file_proto.name)
                merged.file.add().CopyFrom(file_proto)
    return merged.SerializeToString()


def _classes(descriptor_set: bytes) -> dict[str, type]:
    from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

    files = descriptor_pb2.FileDescriptorSet()
    files.ParseFromString(descriptor_set)
    pool = descriptor_pool.DescriptorPool()
    by_name = {f.name: f for f in files.file}
    added: set[str] = set()

    def add(name: str) -> None:
        if name in added or name not in by_name:
            return
        for dependency in by_name[name].dependency:
            add(dependency)
        pool.Add(by_name[name])
        added.add(name)

    for name in by_name:
        add(name)
    found: dict[str, type] = {}
    for file_proto in files.file:
        for message in file_proto.message_type:
            full = f"{file_proto.package}.{message.name}" if file_proto.package else message.name
            found[full] = message_factory.GetMessageClass(pool.FindMessageTypeByName(full))
    return found


def load_scenario(path: Path) -> Scenario:
    """The scenario at `path`, every type and field checked; `AuthoringError` naming the first problem otherwise."""
    path = Path(path)
    where = str(path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise _fail(str(exc), where, "a readable YAML scenario file") from exc
    if not isinstance(raw, Mapping):
        raise _fail(type(raw).__name__, where, "a mapping at the top of the scenario")
    _check_keys(raw, _TOP, where)
    libraries = [Path(p) if Path(p).is_absolute() else (path.parent / p) for p in raw.get("libraries") or []]
    if not libraries:
        raise _fail("no `libraries`", where, "the libraries whose manifests carry the message schemas")
    descriptor_set = _merged_descriptor_set(libraries)
    classes = _classes(descriptor_set)

    topics: dict[str, tuple[str, str]] = {}
    for topic, entry in (raw.get("topics") or {}).items():
        if not isinstance(entry, Mapping):
            raise _fail(repr(entry), f"{where}: topics.{topic}", "a mapping with `type` and `origin`")
        _check_keys(entry, _TOPIC, f"{where}: topics.{topic}")
        type_name, origin = entry.get("type"), entry.get("origin")
        if type_name not in classes:
            raise _fail(f"type {type_name!r}", f"{where}: topics.{topic}", "a message type of the interface schemas",
                        f"the libraries carry {sorted(classes)[:6]}...")
        if origin not in ORIGINS:
            raise _fail(f"origin {origin!r}", f"{where}: topics.{topic}", f"one of {', '.join(ORIGINS)}", "state it, there is no default")
        topics[str(topic)] = (type_name, origin)

    messages: list[ScenarioMessage] = []
    for index, entry in enumerate(raw.get("messages") or []):
        spot = f"{where}: messages[{index}]"
        if not isinstance(entry, Mapping):
            raise _fail(repr(entry), spot, "a mapping with `topic` and `time_us`")
        _check_keys(entry, _MESSAGE, spot)
        topic = entry.get("topic")
        if topic not in topics:
            raise _fail(f"topic {topic!r}", spot, f"a topic declared under `topics` ({sorted(topics)})")
        time_us = entry.get("time_us")
        if not isinstance(time_us, int) or isinstance(time_us, bool) or time_us < 0:
            raise _fail(f"time_us {time_us!r}", spot, "a whole number of microseconds, not negative")
        descriptor = classes[topics[topic][0]].DESCRIPTOR
        header = dict(entry.get("header") or {})
        fields = dict(entry.get("fields") or {})
        if header:
            if "sig_header" not in descriptor.fields_by_name:
                raise _fail(f"`header` on {descriptor.full_name}", spot, "a message with a `sig_header` field")
            sig = descriptor.fields_by_name["sig_header"].message_type
            for key in header:
                if key not in sig.fields_by_name:
                    raise _fail(f"header field {key!r}", spot, f"one of {sorted(sig.fields_by_name)}")
        for key in fields:
            if key not in descriptor.fields_by_name:
                raise _fail(f"field {key!r}", spot, f"a field of {descriptor.full_name} ({sorted(descriptor.fields_by_name)})")
        messages.append(ScenarioMessage(topic, time_us, header, fields))
    return Scenario(str(raw.get("scenario") or path.stem), topics, tuple(messages), descriptor_set, classes)
