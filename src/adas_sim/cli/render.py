# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim render <recording> --at <tick>` -- headless snapshot to PNG.

Renders one tick with no window, and writes a provenance sidecar naming the
tick, project, scenario, pipeline, build hashes, viewport, layers and theme.
Two renders of the same tick are byte-identical.

`--plugin-root` names a component's built library directory (carries
`sim/plugin.yaml` and `config/`, packed by the build) -- without it, only
the framework's own generic layers (ego/frame/trail) render; a component's
real layers (e.g. a driving function's zone/warning) need their plug-in
imported first. Repeatable, same meaning as `vantage.py`'s own flag.
"""

# Design refs: `GT-9` · `UT-B3-17`, `UT-B4-2`, `ST-B3-1` · `R-SIM-20`

from __future__ import annotations

import argparse
from pathlib import Path

from adas_sim.core.runner import build_session_from_recording
from adas_sim.resolve.plugins import register_plugin_root
from adas_sim.config.project import ProjectModel
from adas_sim.render.capture import snapshot
from adas_sim.player.panels.viewport import DEFAULT_PRESETS, Viewport


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim render", description=__doc__)
    parser.add_argument("recording", type=Path)
    parser.add_argument("--at", type=float, required=True, help="seconds into the recording")
    parser.add_argument("--preset", default=None, help="a view.viewport.DEFAULT_PRESETS name")
    parser.add_argument("--project", default="base")
    parser.add_argument("--theme", default="dark", choices=["dark", "light", "print", "forced"])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--plugin-root", type=Path, action="append", default=[],
        help="a component's built library directory (carries sim/plugin.yaml); repeatable",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    session = build_session_from_recording(args.recording)
    tick_index = session.seek_ns(int(args.at * 1e9))
    viewport = DEFAULT_PRESETS[args.preset] if args.preset else Viewport()

    # AR-55's fix, applied here too: the first plugin root's own config/
    # directory, so a component's layer code reads calibration from the
    # DEPLOYED copy it was actually packed with, not a source-checkout
    # fallback that does not exist beside a real build.
    config_library_dir = None
    for root in args.plugin_root:
        resolved = register_plugin_root(root)
        if config_library_dir is None:
            config_library_dir = resolved
    model = ProjectModel.resolve(project=args.project, library_dir=config_library_dir)

    snapshot(session, tick_index, viewport, None, args.out, theme=args.theme, project=args.project, model=model)
    print(f"wrote {args.out} (tick {tick_index}, t={session.at(tick_index).t_s:.3f}s)")
    return 0
