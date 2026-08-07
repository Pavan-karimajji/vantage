# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim view <session>` -- open the viewer on a recording.

Loads the recording, resolves the config bundle it was produced with, and opens
the window. `--workspace` picks a saved panel arrangement, `--at` opens at a
tick, `--preset` picks a viewpoint.
"""

# Design refs: `GT-9` · `R-SIM-13` the viewer renders a `Session` only · `ST-D3-1`

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
        help="the scenario YAML this recording was run against; draws its "
            "expect: windows on the timeline strip",
    )
    parser.add_argument(
        "--pipeline", type=Path, default=None,
        help="show the pipeline panel for this pipeline (read-only; toggling "
            "mode/impl writes a run manifest rather than re-running)",
    )
    parser.add_argument(
        "--search", type=Path, action="append", default=[],
        help="a directory to search for --pipeline's dll:/stubdll: stages (repeatable)",
    )
    parser.add_argument(
        "--config", type=Path, default=None,
        help="config path forwarded to --pipeline's adasInit; falls back to the "
            "bundle beside the library",
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
