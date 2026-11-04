# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`sim window <run configuration>` (`IMP-0149`): opens the launcher window on a run configuration. The verb parses arguments and
delegates to `launcher.window.LauncherWindow`."""
from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim window", description=__doc__)
    parser.add_argument("config", type=Path, help="the run configuration (a pipeline file)")
    parser.add_argument("--search", action="append", type=Path, default=[], help="a directory to find libraries in")
    parser.add_argument("--deadline-ms", type=int, default=None, help="start the batch face with this attempt deadline")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from adas_sim.launcher.model import Selection
    from adas_sim.launcher.window import LauncherWindow

    window = LauncherWindow(Selection.from_spec(args.config, search=tuple(args.search)), setup_path=args.config.with_suffix(".run.json"),
                            deadline_ms=args.deadline_ms)
    window.root.mainloop()
    return 0
