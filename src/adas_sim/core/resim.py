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

from collections.abc import Callable, Mapping
from pathlib import Path

from adas_sim.contracts.pipeline import Pipeline, _split_ref
from adas_sim.core.errors import AuthoringError
from adas_sim.io.base import Provenance, RunManifest, TopicInfo, group_by_log_time
from adas_sim.io.ingest import IngestRecordingReader, discover_ingest_maps
from adas_sim.io.registry import reader_for, writer_for


def _topic_to_port_name(topic: str) -> str:
    return ".".join(topic.strip("/").split("/"))


def _validate_measured_stages_against_recording(
    pipeline: Pipeline, topics: Mapping[str, TopicInfo], port_name_of: Mapping[str, str],
) -> None:
    """`UT-C2-9`'s own hard-error half: a resim against a recording whose
    port manifest differs from a `mode: measured` stage's own declared
    outputs -- missing entirely, or a schema/`proto_type` mismatch --
    refuses to start, naming both. `Pipeline.load`'s own `recording=`
    parameter cannot do this for a real resim: it expects bare,
    non-ingest-mapped topic keys (a vestige from before `S-C9`'s ingest
    maps existed), and nothing in this codebase's real CLI ever wires it
    up -- silently proceeding today means a measured stage with a missing
    or mismatched output is fed an empty `measured` dict and produces
    neutral/wrong output with no symptom (the tick loop below's own
    `if ... in port_payloads` guard). This runs against the SAME
    ingest-mapped topic index `resim_pipeline` already built -- no second
    reader, no full `Session` decode just to pre-flight one resim."""
    available = {port: topics[topic] for topic, port in port_name_of.items()}
    for stage in pipeline.stages:
        if stage.mode != "measured":
            continue
        manifest = pipeline.manifest_for(stage.name)
        for port_spec in manifest.outputs:
            qualified = f"{stage.name}.{port_spec.name}"
            info = available.get(qualified)
            if info is None:
                raise AuthoringError(
                    expected=f"the recording to contain stage '{stage.name}''s output '{port_spec.name}'",
                    found="missing", where=f"stage '{stage.name}' (mode: measured)",
                    hint="record this stage's outputs, or set mode: simulate or off",
                )
            if info.schema_name and port_spec.proto_type and info.schema_name != port_spec.proto_type:
                raise AuthoringError(
                    expected=f"'{qualified}' to carry {port_spec.proto_type!r}",
                    found=f"the recording carries {info.schema_name!r}",
                    where=f"stage '{stage.name}' (mode: measured)",
                    hint="this recording was produced by a different component manifest -- "
                         "resim against a matching recording",
                )


def _port_name_to_topic(name: str) -> str:
    """Inverse of `_topic_to_port_name` -- private one-line copy, same
    reasoning as that function's own docstring (`sources/recorder.py`'s
    `topic_for` is not imported for a one-liner)."""
    return name.replace(".", "/")


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


def resim_pipeline(
    pipeline: Pipeline, recording_path: Path, *, on_tick: Callable[[int, int], None] | None = None,
) -> list[tuple[int, dict]]:
    """Runs `pipeline` tick by tick against `recording_path`: `mode:
    measured` stages are fed their recorded output bytes for that tick
    (`Pipeline.exec`'s own `measured=` kwarg, `S-C1c`, unchanged);
    `mode: simulate` stages execute live. Returns `(t_ns, outputs)` per
    tick, `outputs` keyed exactly as `Pipeline.exec` returns it -- every
    stage's port bytes this tick, by stage name then port name.

    `on_tick`, if given, is called `(tick_count, t_ns)` immediately after
    each tick's own `results.append` -- i.e. only once that tick has fully
    completed. `core/batch_worker.py` uses this to checkpoint progress to
    disk (`UT-D7-7`'s "last tick" gap): a process a `dll:`/`stubdll:`
    library segfaults inside never returns from this function at all, so
    the checkpoint file, not this function's return value, is the only
    record of how far a crashing run got.
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
        _validate_measured_stages_against_recording(pipeline, topics, port_name_of)
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
            if on_tick is not None:
                on_tick(len(results), t_ns)
        return results
    finally:
        reader.close()


def resim_pipeline_merged(pipeline: Pipeline, recording_path: Path, out_path: Path, *, meta: RunManifest) -> None:
    """`S-D3`'s live-resim-to-Session capability (`ST-D3-1`): writes a FULL
    merged recording at `out_path` -- every original topic passed through
    unchanged, except each `mode: simulate` stage's own declared output
    ports, which are overwritten with this resim's freshly-computed bytes
    (`schema_bytes` populated from the component's own `descriptor_set`,
    `R-SIM-11`, same fix as `Recorder._topics()`/`cli/resim.py`'s own
    `_save_outputs`, so the merged file decodes exactly like a live
    recording would). Unlike `cli/resim.py --save` (only the freshly-
    simulated stages' own bytes), the file this writes is a complete
    recording on its own -- `core/runner.build_session_from_recording` can
    load it with no other input, which is the one and only way a `Session`
    is ever built anywhere in this framework (`R-SIM-6`/`R-SIM-13`/
    `R-SIM-14`): this function does not invent a second way, it produces
    the artifact the existing way already knows how to read.

    Same engine as `resim_pipeline` (`Pipeline.exec`, single-rate) -- a
    GUI "Run" and `sim resim` must never silently diverge on the same
    pipeline+recording (`R-SIM-16`'s "one engine").
    """
    source_ports = _wired_source_ports(pipeline)
    measured_stage_names = [stage.name for stage in pipeline.stages if stage.mode == "measured"]
    simulate_stages = [stage for stage in pipeline.stages if stage.mode == "simulate"]

    reader = IngestRecordingReader(reader_for(recording_path), discover_ingest_maps())
    try:
        topics = reader.topics()
        port_name_of = {topic: _topic_to_port_name(topic) for topic in topics}
        _validate_measured_stages_against_recording(pipeline, topics, port_name_of)

        # A simulate stage's own output topics take over their channel
        # entirely -- the merged file must never carry both the base
        # recording's stale bytes and this resim's fresh ones under the
        # same topic, or a reader could not tell which is current (R-SIM-6).
        simulate_topics: dict[str, TopicInfo] = {}
        for stage in simulate_stages:
            manifest = pipeline.manifest_for(stage.name)
            for port_spec in manifest.outputs:
                topic = _port_name_to_topic(f"{stage.name}.{port_spec.name}")
                simulate_topics[topic] = TopicInfo(
                    schema_name=port_spec.proto_type or f"{stage.name}.{port_spec.name}",
                    schema_bytes=manifest.descriptor_set, provenance=Provenance.SIMULATED,
                )
        merged_topics = {topic: info for topic, info in topics.items() if topic not in simulate_topics}
        merged_topics.update(simulate_topics)

        messages = list(reader.messages())
        capture_by_topic_time = {
            (topic, log_time_ns): capture_time_ns for topic, log_time_ns, capture_time_ns, _payload in messages
        }
        groups = list(group_by_log_time(messages, expected_topics=topics.keys()))

        writer = writer_for(out_path)
        writer.open(out_path, meta, merged_topics)
        try:
            previous_t_ns: int | None = None
            for t_ns, payloads, _missing in groups:
                dt_ns = 0 if previous_t_ns is None else t_ns - previous_t_ns
                previous_t_ns = t_ns

                # Pass through every original topic this tick carried,
                # except the ones a simulate stage is about to overwrite --
                # its own real capture stamp travels with it unchanged,
                # never defaulted to reception (R-SIM-14).
                for topic, payload in payloads.items():
                    if topic in simulate_topics:
                        continue
                    writer.write(topic, t_ns, payload, capture_time_ns=capture_by_topic_time.get((topic, t_ns)))

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
                for stage in simulate_stages:
                    for port_name, payload in outputs.get(stage.name, {}).items():
                        # Freshly computed THIS tick, zero injected latency
                        # (no error model exists yet, R-SIM-9) -- reception
                        # and validity genuinely coincide, same reasoning
                        # `Recorder._write_one`'s own comment gives.
                        writer.write(_port_name_to_topic(f"{stage.name}.{port_name}"), t_ns, payload, capture_time_ns=t_ns)
        finally:
            writer.close()
    finally:
        reader.close()
