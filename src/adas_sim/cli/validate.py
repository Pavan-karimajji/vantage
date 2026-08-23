# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim validate <project_root>` -- lint a project's own configuration with
no recording and no binary present (`IMP-0165`).

Runs every check the config layer alone can make -- schema, `FileKind`,
version, per-file, then merge -- and reports PASS, or the first authoring
error found, naming the file/line/value. Never opens a recording or a
component library (`ANL-SW-34`): this module cannot fail on anything but
the configuration itself.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from adas_sim.config import validate_only
from adas_sim.config.paths import ConfigPaths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim validate", description=__doc__)
    parser.add_argument("project_root", type=Path, help="the project's own configuration root")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    validate_only(ConfigPaths(project_root=args.project_root))
    print(f"{args.project_root}: config valid")
    return 0
