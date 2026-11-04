# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`write_scenario_recording` (`IMP-0127`, `SYS-0129`, `SYS-0130`): writes a loaded scenario through the one Python recording
writer, `adas_recording.writer.McapRecorder`, found by `recording_writer()`. No other writer is called here."""
from __future__ import annotations

from pathlib import Path

from google.protobuf import json_format

from adas_sim.io.recording_writer import recording_writer
from adas_sim.scenario.scenario_file import Scenario


def _payload(scenario: Scenario, message) -> bytes:
    type_name = scenario.topics[message.topic][0]
    instance = scenario.classes[type_name]()
    if message.header:
        json_format.ParseDict(dict(message.header), instance.sig_header)
    if message.fields:
        json_format.ParseDict(dict(message.fields), instance)
    return instance.SerializeToString(deterministic=True)


def write_scenario_recording(scenario: Scenario, out: Path) -> Path:
    """The recording of `scenario` at `out`: messages in time order, equal times in the order the scenario lists them; the
    manifest states `source_kind` `synthetic` and `run_kind` `sim`, every topic's origin is the scenario's, every topic `full`."""
    writer = recording_writer()
    specs = {topic: writer.TopicSpec(type_name, scenario.descriptor_set, origin) for topic, (type_name, origin) in scenario.topics.items()}
    manifest = {
        "source_kind": "synthetic", "run_kind": "sim", "components": [],
        "record_policies": {topic: "full" for topic in scenario.topics}, "scenario": scenario.name,
    }
    ordered = sorted(enumerate(scenario.messages), key=lambda item: (item[1].time_us, item[0]))
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with writer.McapRecorder(out, specs, manifest) as recorder:
        for _index, message in ordered:
            recorder.write(message.topic, message.time_us, _payload(scenario, message))
    return out
