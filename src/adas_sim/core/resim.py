# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`resim_pipeline` -- the real, directly-testable resim engine
(`sim_resim_and_recording.md` §9, `contracts.pipeline.Pipeline.exec` +
`io.base.group_by_log_time`, both already built). Moved here from
`cli/resim.py` (`S-C3`): `cli/` and `app/` carry no logic (`sim_api_reference.md`
§1, `GT-9`), and `check/` -- which needs this same tick-by-tick execution to
evaluate a scenario's `expect:` against a live resim -- may never import
`cli/` (same package-map rule). `cli/resim.py` now calls this, unchanged in
every other respect.

**Ingest-wrapped, like `core/runner.py`'s own replay path** (`S-C9`,
`R-SIM-23`): a recording this framework did not produce (a component's
legacy bridge export, another team's run) carries its own topic
vocabulary, remapped to port names by whatever `modules/*/sim/ingest/*.yaml`
matches. Skipped for a recording this framework DID produce -- its topics
already equal port names (`R-SIM-6`), so wrapping is a no-op either way
(`io/ingest.py`'s own docstring).

`_topic_to_port_name` is a private one-line copy of `core/runner.py`'s own
function (the topic <-> qualified-port-name naming convention), not an
import from it -- both modules keep their own copy rather than one
importing the other for a one-liner, same reasoning `core/runner.py` itself
gives for not importing `sources/recorder.py`'s inverse.
"""

from __future__ import annotations

from pathlib import Path

from adas_sim.contracts.pipeline import Pipeline, _split_ref
from adas_sim.io.base import group_by_log_time
from adas_sim.io.ingest import IngestRecordingReader, discover_ingest_maps
from adas_sim.io.registry import reader_for


def _topic_to_port_name(topic: str) -> str:
    return ".".join(topic.strip("/").split("/"))


def _wired_source_ports(pipeline: Pipeline) -> set[str]:
    ports: set[str] = set()
    for stage in pipeline.stages:
        if stage.mode == "off":
            continue
        for ref in stage.inputs.values():
            producer_name, port = _split_ref(ref)
            if producer_name == "source":
                ports.add(port)
    return ports


def resim_pipeline(pipeline: Pipeline, recording_path: Path) -> list[tuple[int, dict]]:
    """Runs `pipeline` tick by tick against `recording_path`: `mode:
    measured` stages are fed their recorded output bytes for that tick
    (`Pipeline.exec`'s own `measured=` kwarg, `S-C1c`, unchanged);
    `mode: simulate` stages execute live. Returns `(t_ns, outputs)` per
    tick, `outputs` keyed exactly as `Pipeline.exec` returns it -- every
    stage's port bytes this tick, by stage name then port name.
    """
    source_ports = _wired_source_ports(pipeline)
    measured_stage_names = [stage.name for stage in pipeline.stages if stage.mode == "measured"]

    reader = IngestRecordingReader(reader_for(recording_path), discover_ingest_maps())
    try:
        topics = reader.topics()
        # Every topic key, in port-name space -- a no-op for a topic an
        # ingest map already remapped to its final port name (S-C9), and
        # the slash->dot conversion for one this framework recorded itself.
        port_name_of = {topic: _topic_to_port_name(topic) for topic in topics}
        messages = list(reader.messages())
        groups = list(group_by_log_time(messages, expected_topics=topics.keys()))

        previous_t_ns: int | None = None
        results: list[tuple[int, dict]] = []
        for t_ns, payloads, _missing in groups:
            dt_ns = 0 if previous_t_ns is None else t_ns - previous_t_ns
            previous_t_ns = t_ns
            port_payloads = {port_name_of[topic]: payload for topic, payload in payloads.items()}

            stimulus = {
                port: port_payloads[f"source.{port}"]
                for port in source_ports if f"source.{port}" in port_payloads
            }
            measured: dict[str, dict[str, bytes]] = {}
            for stage_name in measured_stage_names:
                manifest = pipeline.manifest_for(stage_name)
                recorded = {
                    port_spec.name: port_payloads[f"{stage_name}.{port_spec.name}"]
                    for port_spec in manifest.outputs if f"{stage_name}.{port_spec.name}" in port_payloads
                }
                if recorded:
                    measured[stage_name] = recorded

            outputs = pipeline.exec(dt_ns, stimulus, measured=measured)
            results.append((t_ns, dict(outputs)))
        return results
    finally:
        reader.close()
