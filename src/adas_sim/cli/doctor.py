# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim doctor` -- report the environment, and what is missing.

Prints the interpreter, install mode, platform, console encoding and line
endings, plus whichever optional extras are present.

With `--component <path>`, checks one component against what the framework
needs from it -- manifest, config bundle, plug-ins -- and names each absence as
a gap. It reports; it never fixes.
"""

# Design refs: `GT-9` · `DG-3` · facts live in `core/diagnostics.py` · `UT-D6-8`, `UT-C5-8`

from __future__ import annotations

import argparse
from pathlib import Path

from adas_sim.diagnostics.diagnostics import doctor_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim doctor", description=__doc__)
    parser.add_argument("--pipeline", type=Path, default=None, help="a pipeline YAML to diagnose (library resolution, config bundle agreement)")
    parser.add_argument(
        "--search", type=Path, action="append", default=[],
        help="a directory to search for a dll:/stubdll: stage's library (repeatable)",
    )
    parser.add_argument("--recording", type=Path, default=None, help="a recording to diagnose (codec readability, feasible cuts)")
    parser.add_argument("--config", type=Path, default=None, help="an explicit config path, same meaning as sim resim --config")
    parser.add_argument("--plugin-root", type=Path, default=None, help="an explicit plug-in bundle directory (PluginBundle.resolve's explicit tier)")
    parser.add_argument("--project", default="base", help="falls back to 'base' (R-VAR-4)")
    parser.add_argument(
        "--config-source", choices=["embedded", "library", "checkout"], default=None,
        help="force the config-bundle agreement check onto one tier (UT-C5-8); "
            "'embedded' requires --recording",
    )
    parser.add_argument(
        "--component", type=Path, default=None,
        help="a component's root directory (e.g. modules/<name>); report it "
            "against the component checklist (ST-D6-4)",
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
        plugin_root=args.plugin_root, component_root=args.component,
    )
    for key, value in report.items():
        if isinstance(value, (list, dict)):
            print(f"{key}:")
            _print(value, indent="  ")
        else:
            print(f"{key:<22} {value}")
    return 1 if report["problems"] else 0
