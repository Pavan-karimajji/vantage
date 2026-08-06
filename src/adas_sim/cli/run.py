# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim run <scenario> --pipeline <p> [--record <out>]` -- argument parsing
only (`GT-9`). Drives a `Source` AND executes the pipeline live
(`sim_resim_and_recording.md` §9: "produces an artifact: optional, executes
a SUT: yes (live)") -- `--record` is the only difference from `sim record`:
without it, ticks execute and nothing is written; with it, `Recorder`
(`sources/recorder.py`) writes every declared port exactly as `sim run
--record` always has (`sim_architecture.md`'s own migration table).

`--source`/`--script` reuse `cli.record`'s own stand-in for scenario-driven
source selection (see that module's docstring) -- `--source`/`--script`
choose which `Source` drives the run; which scenario schema section that
choice should someday be read from is unrelated to `S-C3`'s own job (the
schema itself, now built, `contracts/scenario.py`) and stays a stand-in.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from adas_sim.cli.record import _build_source, _tick_count
from adas_sim.contracts.pipeline import Pipeline
from adas_sim.contracts.scenario import load_scenario
from adas_sim.core.manifest import build_manifest
from adas_sim.sources.recorder import Recorder


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim run", description=__doc__)
    parser.add_argument("scenario", type=Path, help="scenario YAML")
    parser.add_argument("--pipeline", type=Path, required=True, help="the pipeline YAML to execute")
    parser.add_argument("--record", type=Path, help="also write a recording to this path")
    parser.add_argument("--source", choices=["synthetic", "carla"], default="synthetic")
    parser.add_argument("--script", type=Path, help="--source synthetic only: a YAML script of per-tick bytes")
    parser.add_argument("--ticks", type=int, help="ticks to run (defaults to --script's own length, --source synthetic only)")
    parser.add_argument("--dt-ms", type=float, default=50.0, help="tick period in milliseconds")
    parser.add_argument("--project", default="base")
    parser.add_argument(
        "--config", type=Path,
        help="config path forwarded to each stage's adasInit -- adasInit(NULL)'s own bundle "
             "resolution is S-C5, not yet built, so a real dll:/stubdll: stage needs this explicitly",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source = _build_source(args)
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
