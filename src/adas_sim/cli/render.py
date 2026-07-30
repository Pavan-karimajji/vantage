# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim render <recording> --at <t> [--preset <name>] --out <fig.png>` --
argument parsing only (`GT-9`); the facts come from `core/runner.py`
(`build_session_from_recording`, `build_scene`) and `render/bev.py`
(`render_scene`), none of which import Qt (`UT-B3-17`) -- `sim render`
therefore needs **no display and no PySide6 at all**, not merely an
offscreen Qt platform (`ST-B3-1`)."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.image  # already a hard dependency of render.bev, imported below

from adas_sim.core.runner import build_scene, build_session_from_recording
from adas_sim.render.bev import render_scene
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
    scene = build_scene(session, tick_index, project=args.project)
    viewport = DEFAULT_PRESETS[args.preset] if args.preset else Viewport()
    frame = render_scene(scene, viewport, args.theme)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    matplotlib.image.imsave(args.out, frame)
    print(f"wrote {args.out} (tick {tick_index}, t={session.at(tick_index).t_s:.3f}s)")
    return 0
