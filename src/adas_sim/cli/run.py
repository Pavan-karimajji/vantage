# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim run <scenario> --pipeline <p.yaml>` -- drive the scripted synthetic
source and execute.

Runs a scenario live against the synthetic source with the pipeline in the
loop, and writes a session recording by default. The non-deterministic mode:
use `sim resim` to re-execute the result reproducibly.
"""

# Design refs: `GT-9` · `R-SIM-5` sim is the non-deterministic mode · `R-SIM-6` a sim run
# writes a session recording by default

from __future__ import annotations

import argparse
from pathlib import Path

from adas_sim.cli.record import _build_source, _tick_count
from adas_sim.graph.build import Pipeline
from adas_sim.config.scenario import load_scenario
from adas_sim.runspec.manifest import build_manifest
from adas_sim.sources.recorder import Recorder


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim run", description=__doc__)
    parser.add_argument("scenario", type=Path, help="scenario YAML")
    parser.add_argument("--pipeline", type=Path, required=True, help="the pipeline YAML to execute")
    parser.add_argument("--record", type=Path, help="also write a recording to this path")
    parser.add_argument("--script", type=Path, required=True, help="a YAML script of per-tick bytes")
    parser.add_argument("--ticks", type=int, help="ticks to run (defaults to --script's own length)")
    parser.add_argument("--dt-ms", type=float, default=50.0, help="tick period in milliseconds")
    parser.add_argument("--project", default="base")
    parser.add_argument(
        "--config", type=Path,
        help="config path forwarded to each stage's adasInit; falls back to the "
            "bundle beside the library",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source, _source_proto_types, _source_descriptor_set = _build_source(args)
    ticks = _tick_count(args, source)
    dt_ns = int(args.dt_ms * 1_000_000)

    scenario = load_scenario(args.scenario)
    pipeline = Pipeline.load(args.pipeline, source=source, faults=scenario.run.faults)
    pipeline.init_components(args.config)

    try:
        if args.record:
            meta = build_manifest(
                pipeline=pipeline, pipeline_path=args.pipeline, run_kind="sim", source_kind=source.name,
                project=args.project, scenario_name=scenario.id, scenario_path=args.scenario,
                component_build_shas=pipeline.component_build_shas(),
            )
            recorder = Recorder(pipeline, source, args.record, meta=meta)
            recorder.open(scenario)
            try:
                for _ in range(ticks):
                    recorder.tick(dt_ns)
            finally:
                recorder.close()
            print(f"wrote {args.record}")
        else:
            source.start(scenario)
            try:
                for _ in range(ticks):
                    pipeline.step(dt_ns, source.poll())
            finally:
                source.stop()
    finally:
        pipeline.shutdown_components()

    print(f"run complete: {ticks} tick(s)")
    return 0
