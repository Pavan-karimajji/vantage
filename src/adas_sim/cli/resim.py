# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim resim <recording> --pipeline <pipeline.yaml> [--save <out.mcap>]`
-- executes a SUT against an existing recording
(`sim_resim_and_recording.md` §9: "produces an artifact: optional, executes
a SUT: yes (from a recording)"). Argument parsing only (`GT-9`);
`resim_pipeline` is the real, directly-testable engine underneath, built on
`contracts.pipeline.Pipeline.exec` + `io.base.group_by_log_time` (both
already built) -- never a second tick-grouping implementation.

`--pipeline` is not shown in `sim_resim_and_recording.md` §9's own example
CLI line, but a resim structurally needs one (which stages exist, which
are `measured`, how they're wired) -- the same flag `sim run` already
carries.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from adas_sim.contracts.pipeline import Pipeline, _split_ref
from adas_sim.core.manifest import build_manifest
from adas_sim.io.base import Provenance, TopicInfo, group_by_log_time
from adas_sim.io.registry import reader_for, writer_for
from adas_sim.sources.recorder import topic_for


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim resim", description=__doc__)
    parser.add_argument("recording", type=Path, help="a recording to resim against")
    parser.add_argument("--pipeline", type=Path, required=True, help="the pipeline YAML to execute")
    parser.add_argument("--save", type=Path, help="write this resim's own freshly-computed tick outputs to a new recording")
    parser.add_argument("--project", default="base")
    return parser


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

    reader = reader_for(recording_path)
    try:
        topics = reader.topics()
        messages = list(reader.messages())
        groups = list(group_by_log_time(messages, expected_topics=topics.keys()))

        previous_t_ns: int | None = None
        results: list[tuple[int, dict]] = []
        for t_ns, payloads, _missing in groups:
            dt_ns = 0 if previous_t_ns is None else t_ns - previous_t_ns
            previous_t_ns = t_ns

            stimulus = {
                port: payloads[topic_for(f"source.{port}")]
                for port in source_ports if topic_for(f"source.{port}") in payloads
            }
            measured: dict[str, dict[str, bytes]] = {}
            for stage_name in measured_stage_names:
                manifest = pipeline.manifest_for(stage_name)
                recorded = {
                    port_spec.name: payloads[topic_for(f"{stage_name}.{port_spec.name}")]
                    for port_spec in manifest.outputs if topic_for(f"{stage_name}.{port_spec.name}") in payloads
                }
                if recorded:
                    measured[stage_name] = recorded

            outputs = pipeline.exec(dt_ns, stimulus, measured=measured)
            results.append((t_ns, dict(outputs)))
        return results
    finally:
        reader.close()


def _save_outputs(pipeline: Pipeline, outputs: list[tuple[int, dict]], path: Path, meta) -> None:
    """`--save`: only the freshly-computed (`mode: simulate`) stages' own
    outputs -- a `measured` stage contributed nothing new this resim, and
    the original recording already carries its bytes (`R-SIM-6`), so
    re-writing them here would be a second, redundant copy, not new
    evidence."""
    simulate_stages = [stage for stage in pipeline.stages if stage.mode == "simulate"]
    topics = {}
    for stage in simulate_stages:
        for port_spec in pipeline.manifest_for(stage.name).outputs:
            name = f"{stage.name}.{port_spec.name}"
            topics[topic_for(name)] = TopicInfo(schema_name=port_spec.proto_type or name, provenance=Provenance.SIMULATED)

    writer = writer_for(path)
    writer.open(path, meta, topics)
    for t_ns, tick_outputs in outputs:
        for stage in simulate_stages:
            for port_name, payload in tick_outputs.get(stage.name, {}).items():
                writer.write(topic_for(f"{stage.name}.{port_name}"), t_ns, payload, capture_time_ns=t_ns)
    writer.close()


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pipeline = Pipeline.load(args.pipeline)
    outputs = resim_pipeline(pipeline, args.recording)

    if args.save:
        meta = build_manifest(
            pipeline=pipeline, pipeline_path=args.pipeline, run_kind="resim", source_kind="mcap",
            project=args.project, recording_path=args.recording,
        )
        _save_outputs(pipeline, outputs, args.save, meta)
        print(f"wrote {args.save}")

    print(f"resim complete: {len(outputs)} tick(s)")
    return 0
