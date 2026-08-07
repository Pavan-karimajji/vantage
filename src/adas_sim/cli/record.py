# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim record <scenario> -o <out>` -- produce a recording, execute nothing.

Drives a world model and writes every port it emits. No pipeline runs, so the
result is stimulus only. Use `sim run` to record and execute in one pass.

`--source synthetic` needs a scripted YAML of per-tick bytes (`--script`);
`--source carla` drives the scenario file itself.
"""

# Design refs: `GT-9` · `R-SIM-12` producing and executing are two sides ·
# `R-SIM-9` world-model and sensor-error specifics live with the tooling

from __future__ import annotations

import argparse
from pathlib import Path

from adas_sim.contracts.scenario import load_scenario
from adas_sim.core.errors import AuthoringError
from adas_sim.core.manifest import build_manifest
from adas_sim.sources.recorder import Recorder
from adas_sim.sources.synthetic import SyntheticSource


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim record", description=__doc__)
    parser.add_argument("scenario", type=Path, help="scenario YAML")
    parser.add_argument("-o", "--output", type=Path, required=True, help="output recording (.mcap)")
    parser.add_argument("--source", choices=["synthetic", "carla"], default="synthetic")
    parser.add_argument("--script", type=Path, help="--source synthetic only: a YAML script of per-tick bytes")
    parser.add_argument("--ticks", type=int, help="ticks to record (defaults to --script's own length, --source synthetic only)")
    parser.add_argument("--dt-ms", type=float, default=50.0, help="tick period in milliseconds")
    parser.add_argument("--project", default="base")
    return parser


def _build_source(args: argparse.Namespace):
    if args.source == "synthetic":
        if args.script is None:
            raise AuthoringError(
                expected="--script <path> with --source synthetic", found="--script absent",
                where="sim record", hint="a synthetic source needs a scripted YAML of per-tick bytes",
            )
        return SyntheticSource.from_yaml(args.script)
    # --source carla needs `CarlaSource(message_classes=...)`, resolved from
    # a real component's own manifest (`contracts.component.
    # resolve_message_classes`, R-SIM-11) -- which library to load that
    # manifest from is a live-build decision this CLI does not make for
    # you yet (MC-2's own territory, sim_implementation_plan.md S-C2).
    raise AuthoringError(
        expected="a --source carla wiring that supplies CarlaSource(message_classes=...)",
        found="--source carla: CLI wiring not yet built", where="sim record",
        hint="construct CarlaSource directly, passing message_classes resolved from a real "
             "component's manifest (contracts.component.resolve_message_classes)",
    )


def _tick_count(args: argparse.Namespace, source) -> int:
    if args.ticks is not None:
        return args.ticks
    try:
        return len(source)
    except TypeError as exc:
        raise AuthoringError(
            expected="--ticks <n>", found="--ticks absent and this source has no natural length",
            where="sim record", hint="pass --ticks explicitly for a live source (e.g. --source carla)",
        ) from exc


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source = _build_source(args)
    ticks = _tick_count(args, source)
    dt_ns = int(args.dt_ms * 1_000_000)

    scenario = load_scenario(args.scenario)

    meta = build_manifest(
        run_kind="sim", source_kind=source.name, project=args.project,
        scenario_name=scenario.id, scenario_path=args.scenario, recording_path=None,
    )
    recorder = Recorder(None, source, args.output, meta=meta)

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
