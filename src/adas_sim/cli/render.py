# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim render <recording> --at <tick>` -- headless snapshot to PNG.

Renders one tick with no window, and writes a provenance sidecar naming the
tick, project, scenario, pipeline, build hashes, viewport, layers and theme.
Two renders of the same tick are byte-identical.
"""

# Design refs: `GT-9` · `UT-B3-17`, `UT-B4-2`, `ST-B3-1`

from __future__ import annotations

import argparse
from pathlib import Path

from adas_sim.core.runner import build_session_from_recording
from adas_sim.render.capture import snapshot
from adas_sim.view.viewport import DEFAULT_PRESETS, Viewport


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim render", description=__doc__)
    parser.add_argument("recording", type=Path)
    parser.add_argument("--at", type=float, required=True, help="seconds into the recording")
    parser.add_argument("--preset", default=None, help="a view.viewport.DEFAULT_PRESETS name")
    parser.add_argument("--project", default="base")
    parser.add_argument("--theme", default="dark", choices=["dark", "light", "print", "forced"])
    parser.add_argument("--out", type=Path, required=True)
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    session = build_session_from_recording(args.recording)
    tick_index = session.seek_ns(int(args.at * 1e9))
    viewport = DEFAULT_PRESETS[args.preset] if args.preset else Viewport()
    snapshot(session, tick_index, viewport, None, args.out, theme=args.theme, project=args.project)
    print(f"wrote {args.out} (tick {tick_index}, t={session.at(tick_index).t_s:.3f}s)")
    return 0
