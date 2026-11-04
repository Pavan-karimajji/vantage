# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`sim explain <project>` (`IMP-0147`, `SYS-0121`): the dry run. Prints the resolved configuration of a project with the layer of each
value (`launcher.dry_run.dry_run`); it calls no component and starts no engine run. The verb parses arguments and delegates."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from adas_sim.config.paths import ConfigPaths
from adas_sim.diagnostics.errors import SimError
from adas_sim.launcher.dry_run import dry_run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim explain", description=__doc__)
    parser.add_argument("project", type=Path, help="the project's configuration root")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        lines = dry_run(ConfigPaths(project_root=args.project))
    except SimError as exc:
        print(f"[sim explain] error: {exc}", file=sys.stderr)
        return exc.exit_code
    for line in lines:
        print(line)
    return 0
