# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`resim_pipeline`/`resim_pipeline_merged` -- a pure-Python, in-process
tick loop over `Pipeline.exec`, moved here from `adas_sim.core.resim`
(`WP-16`, `IMP-0013`) when that module's own real callers were confirmed
retired.

**Why this lives under `tests/`, not `src/adas_sim/`:** every real production
caller of a resim now goes through `engine.bridge.run_pipeline_via_engine`
(`WP-15b`) -- driving the real `simcore`/`simengine` engine, which needs a
compiled `dll:`/`stubdll:` library on disk (`R-SIM-4`/`R-SIM-11`) and can
never accept a bare Python closure. But a handful of tests deliberately use
`resolve.component.InProcessSilComponent` + `impl: "stub:<name>"` -- a
component that IS a Python closure, with no compiled binary and no build
step -- because that is what makes them fast, portable and independent of
whatever `.dll`/`.so` this session happens to have built. `engine.bridge`'s
own docstring names exactly why that technique cannot go through the engine
(`pipeline_to_run_spec` would emit an empty `impl:` for a `components=`
-injected stage, since it has no file on disk).

So the tick loop itself is not dead: it is the one thing that still runs a
`stub:`-only pipeline at all. What is dead is running it as *production*
code -- `sim resim`/`check scenario` never call it any more, and nothing
under `src/adas_sim/` may import this module (a plain test-only helper has
no place being reachable from the shipped package). Kept content-identical
to the retired `core/resim.py` rather than rewritten, so its own proven
behaviour (measured/simulate mixing, ingest-map wrapping, merged-file
writing) carries over unchanged into its narrower role.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

from adas_sim.graph.pipeline import Pipeline, _split_ref
from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.io.base import Provenance, RunManifest, TopicInfo, group_by_log_time
from adas_sim.ingest.map import IngestRecordingReader, discover_ingest_maps
from adas_sim.plugins.registry import reader_for, writer_for


def _topic_to_port_name(topic: str) -> str:
    return ".".join(topic.strip("/").split("/"))


def _validate_measured_stages_against_recording(
    pipeline: Pipeline, topics: Mapping[str, TopicInfo], port_name_of: Mapping[str, str],
) -> None:
    """A resim against a recording whose port manifest differs from a
    `mode: measured` stage's own declared outputs -- missing entirely, or a
    schema/`proto_type` mismatch -- refuses to start, naming both, rather
    than silently feeding an empty `measured` dict and producing neutral/
    wrong output with no symptom."""
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
    (`Pipeline.exec`'s own `measured=` kwarg); `mode: simulate` stages
    execute live. Returns `(t_ns, outputs)` per tick, `outputs` keyed
    exactly as `Pipeline.exec` returns it -- every stage's port bytes this
    tick, by stage name then port name."""
    source_ports = _wired_source_ports(pipeline)
    measured_stage_names = [stage.name for stage in pipeline.stages if stage.mode == "measured"]

    reader = IngestRecordingReader(reader_for(recording_path), discover_ingest_maps())
    try:
        topics = reader.topics()
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
    """Writes a FULL merged recording at `out_path` -- every original topic
    passed through unchanged, except each `mode: simulate` stage's own
    declared output ports, which are overwritten with this resim's
    freshly-computed bytes. `core/runner.build_session_from_recording` can
    load the result with no other input."""
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
