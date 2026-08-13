# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim record <scenario> -o <out>` -- produce a recording, execute nothing.

Drives the scripted synthetic source and writes every port it emits. No
pipeline runs, so the result is stimulus only. Use `sim run` to record and
execute in one pass.

Needs a scripted YAML of per-tick bytes (`--script`).
"""

# Design refs: `GT-9` · `R-SIM-12` producing and executing are two sides ·
# `R-SIM-9` world-model and sensor-error specifics live with the tooling

from __future__ import annotations

import argparse
from pathlib import Path

from adas_sim.config.scenario import load_scenario
from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.runspec.manifest import build_manifest
from adas_sim.sources.recorder import Recorder
from adas_sim.sources.synthetic import SyntheticSource


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim record", description=__doc__)
    parser.add_argument("scenario", type=Path, help="scenario YAML")
    parser.add_argument("-o", "--output", type=Path, required=True, help="output recording (.mcap)")
    parser.add_argument("--script", type=Path, required=True, help="a YAML script of per-tick bytes")
    parser.add_argument("--ticks", type=int, help="ticks to record (defaults to --script's own length)")
    parser.add_argument("--dt-ms", type=float, default=50.0, help="tick period in milliseconds")
    parser.add_argument("--project", default="base")
    return parser


def _build_source(args: argparse.Namespace):
    """Returns `(source, source_proto_types, source_descriptor_set)` -- the
    latter two are a source's own port->proto_type map plus one shared
    `FileDescriptorSet`, passed straight through to `Recorder` so `source.*`
    topics get a real schema instead of a placeholder qualified port name
    (empty here -- the synthetic source has no real schema to offer)."""
    return SyntheticSource.from_yaml(args.script), {}, b""


def _tick_count(args: argparse.Namespace, source) -> int:
    if args.ticks is not None:
        return args.ticks
    try:
        return len(source)
    except TypeError as exc:
        raise AuthoringError(
            expected="--ticks <n>", found="--ticks absent and this source has no natural length",
            where="sim record", hint="pass --ticks explicitly",
        ) from exc


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source, source_proto_types, source_descriptor_set = _build_source(args)
    ticks = _tick_count(args, source)
    dt_ns = int(args.dt_ms * 1_000_000)

    scenario = load_scenario(args.scenario)

    meta = build_manifest(
        run_kind="sim", source_kind=source.name, project=args.project,
        scenario_name=scenario.id, scenario_path=args.scenario, recording_path=None,
    )
    recorder = Recorder(
        None, source, args.output, meta=meta,
        source_proto_types=source_proto_types, source_descriptor_set=source_descriptor_set,
    )

    upper_bound = recorder.estimate_upper_bound_bytes(ticks)
    print(f"estimated size (upper bound): {upper_bound} bytes for {ticks} tick(s)")

    recorder.open(scenario)
    revised_printed = False
    try:
        for _ in range(ticks):
            recorder.tick(dt_ns)
            if not revised_printed:
                revised = recorder.revised_estimate_bytes(ticks)
                if revised is not None:
                    print(f"revised estimate: {revised} bytes")
                    revised_printed = True
    finally:
        recorder.close()

    print(f"wrote {args.output}")
    return 0
