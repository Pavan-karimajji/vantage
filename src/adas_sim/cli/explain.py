# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim explain <name> [--session]` -- argument parsing and layout only
(GT-9); the facts come from `adas_sim.core.explain.explain`. First version,
seeded at `S-B2` (DG-2); the CLI surface table's full shape
(`sim_api_reference.md` §10) lands at `S-D6`."""

from __future__ import annotations

import argparse
from pathlib import Path

from adas_sim.core.explain import explain
from adas_sim.core.runner import build_session_from_recording


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim explain", description=__doc__)
    parser.add_argument("name")
    parser.add_argument("--session", required=True, type=Path)
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    session = build_session_from_recording(args.session)
    facts = explain(args.name, session)
    for key, value in facts.items():
        print(f"{key:<20} {value}")
    return 0 if facts["kind"] != "unknown" else 1
