# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim view <session> [--preset] [--at]` (`sim_api_reference.md` §10) --
argument parsing only (`GT-9`); launching the GUI is `app/gui.launch`'s
job, not this module's -- **not** `app/cli.py`, since `app/` is the GUI
and holds no logic of its own either."""

from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim view", description=__doc__)
    parser.add_argument("session", type=Path)
    parser.add_argument("--project", default="base")
    parser.add_argument("--workspace", type=Path, default=None, help="a component's sim/workspace.yaml")
    parser.add_argument("--preset", default=None, help="a view.viewport.DEFAULT_PRESETS name")
    parser.add_argument("--at", type=float, default=None, help="seconds into the recording to open at")
    parser.add_argument(
        "--scenario", type=Path, default=None,
        help="the scenario YAML this recording was run against -- draws its expect: windows on the "
             "timeline strip (sim_visualization_spec.md SS7.3). Explicit, never guessed: a recording's "
             "own run manifest carries only the scenario's name (RunManifest.scenario), not a path back "
             "to the file",
    )
    parser.add_argument(
        "--pipeline", type=Path, default=None,
        help="S-D3: shows the pipeline panel (read-only this slice -- mode/impl as declared, toggling "
             "writes a run manifest via File > Save Run Manifest, does not re-run anything live). "
             "Explicit, never guessed, same reasoning as --scenario",
    )
    parser.add_argument(
        "--search", type=Path, action="append", default=[],
        help="a directory to search for --pipeline's dll:/stubdll: stages (repeatable)",
    )
    parser.add_argument(
        "--config", type=Path, default=None,
        help="S-D3 slice 4 (ST-D3-1): config path forwarded to --pipeline's adasInit for a real Run -- "
             "same 'adasInit(NULL) bundle auto-resolution is not built yet' caveat as sim resim --config",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # Deferred: PySide6 is an optional extra ("viewer", pyproject.toml) --
    # every other `sim` verb, including `sim render`, must stay importable
    # with no Qt installed at all (`UT-A1-2`'s own discipline, extended
    # from protobuf to Qt).
    from adas_sim.app.gui import launch

    return launch(
        args.session, project=args.project, workspace_path=args.workspace,
        preset=args.preset, at_s=args.at, scenario_path=args.scenario,
        pipeline_path=args.pipeline, pipeline_search=args.search, pipeline_config=args.config,
    )
