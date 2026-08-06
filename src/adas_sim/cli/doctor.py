# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim doctor [--pipeline P [--search DIR ...] [--config C] [--project NAME]]
[--recording R] [--config-source embedded|library|checkout]` -- argument
parsing and layout only (GT-9); the facts themselves come from
`adas_sim.core.diagnostics.doctor_report`. With no flags, exactly the S-A1
environment slice; `--pipeline`/`--recording` add library resolution,
config-bundle agreement, codec capabilities and recording-cut feasibility
(DG-3, S-D6/`UT-D6-8`). `--config-source` forces the bundle-agreement check
onto exactly one resolution tier instead of the normal priority order
(`UT-C5-8`) -- `embedded` needs `--recording` to have something to force
against. Non-zero exit on anything that would break a real run."""

from __future__ import annotations

import argparse
from pathlib import Path

from adas_sim.core.diagnostics import doctor_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim doctor", description=__doc__)
    parser.add_argument("--pipeline", type=Path, default=None, help="a pipeline YAML to diagnose (library resolution, config bundle agreement)")
    parser.add_argument(
        "--search", type=Path, action="append", default=[],
        help="a directory to search for a dll:/stubdll: stage's library (repeatable)",
    )
    parser.add_argument("--recording", type=Path, default=None, help="a recording to diagnose (codec readability, feasible cuts)")
    parser.add_argument("--config", type=Path, default=None, help="an explicit config path, same meaning as sim resim --config")
    parser.add_argument("--project", default="base", help="falls back to 'base' (R-VAR-4)")
    parser.add_argument(
        "--config-source", choices=["embedded", "library", "checkout"], default=None,
        help="force the config-bundle agreement check onto exactly one tier (UT-C5-8); "
             "'embedded' requires --recording",
    )
    return parser


def _print(value: object, *, indent: str = "") -> None:
    if isinstance(value, list):
        if not value:
            print(f"{indent}(none)")
        for item in value:
            _print(item, indent=indent + "  ")
    elif isinstance(value, dict):
        for key, sub in value.items():
            if isinstance(sub, (list, dict)):
                print(f"{indent}{key}:")
                _print(sub, indent=indent + "  ")
            else:
                print(f"{indent}{key:<28} {sub}")
    else:
        print(f"{indent}{value}")


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = doctor_report(
        pipeline_path=args.pipeline, search=args.search, recording_path=args.recording,
        config_path=args.config, project=args.project, config_source=args.config_source,
    )
    for key, value in report.items():
        if isinstance(value, (list, dict)):
            print(f"{key}:")
            _print(value, indent="  ")
        else:
            print(f"{key:<22} {value}")
    return 1 if report["problems"] else 0
