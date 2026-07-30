# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim render <recording> --at <t> [--preset <name>] --out <fig.png|fig.svg>`
-- argument parsing only (`GT-9`); the facts come from `core/runner.py`
(`build_session_from_recording`) and `render/capture.py` (`snapshot`, `S-B4`),
neither of which import Qt (`UT-B3-17`) -- `sim render` therefore needs
**no display and no PySide6 at all**, not merely an offscreen Qt platform
(`ST-B3-1`). `snapshot` also writes the `--out` sidecar (`UT-B4-2`) and
picks raster vs. vector from `--out`'s own suffix (`D5`)."""

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
