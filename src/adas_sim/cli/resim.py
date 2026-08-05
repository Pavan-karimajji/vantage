# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim resim <recording> --pipeline <pipeline.yaml> [--save <out.mcap>]`
-- executes a SUT against an existing recording
(`sim_resim_and_recording.md` §9: "produces an artifact: optional, executes
a SUT: yes (from a recording)"). Argument parsing only (`GT-9`);
`resim_pipeline` (`core/resim.py`, moved there at `S-C3` -- `check/` needs
the same engine and may never import `cli/`) is the real, directly-testable
engine underneath, built on `contracts.pipeline.Pipeline.exec` +
`io.base.group_by_log_time` (both already built) -- never a second
tick-grouping implementation.

`--pipeline` is not shown in `sim_resim_and_recording.md` §9's own example
CLI line, but a resim structurally needs one (which stages exist, which
are `measured`, how they're wired) -- the same flag `sim run` already
carries.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from adas_sim.contracts.pipeline import Pipeline
from adas_sim.core.manifest import build_manifest
from adas_sim.core.resim import resim_pipeline
from adas_sim.io.base import Provenance, TopicInfo
from adas_sim.io.registry import writer_for
from adas_sim.sources.recorder import topic_for


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim resim", description=__doc__)
    parser.add_argument("recording", type=Path, help="a recording to resim against")
    parser.add_argument("--pipeline", type=Path, required=True, help="the pipeline YAML to execute")
    parser.add_argument("--save", type=Path, help="write this resim's own freshly-computed tick outputs to a new recording")
    parser.add_argument(
        "--search", type=Path, action="append", default=[],
        help="a directory to search for a dll:/stubdll: stage's library (repeatable, contracts.loader.resolve_library)",
    )
    parser.add_argument("--project", default="base")
    parser.add_argument(
        "--config", type=Path,
        help="config path forwarded to each stage's adasInit -- adasInit(NULL)'s own bundle "
             "resolution is S-C5, not yet built, so a real dll:/stubdll: stage needs this explicitly",
    )
    return parser


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
    pipeline = Pipeline.load(args.pipeline, search=args.search)
    pipeline.init_components(args.config)
    try:
        outputs = resim_pipeline(pipeline, args.recording)
    finally:
        pipeline.shutdown_components()

    if args.save:
        meta = build_manifest(
            pipeline=pipeline, pipeline_path=args.pipeline, run_kind="resim", source_kind="mcap",
            project=args.project, recording_path=args.recording,
        )
        _save_outputs(pipeline, outputs, args.save, meta)
        print(f"wrote {args.save}")

    print(f"resim complete: {len(outputs)} tick(s)")
    return 0
