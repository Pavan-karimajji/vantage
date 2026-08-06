# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim explain <name> [--session] [--at <tick>]` -- argument parsing and
layout only (GT-9); the facts come from `adas_sim.core.explain.explain`
(static: what a name *is*) or, with `--at`, `adas_sim.core.evidence.evidence`
(dynamic: what a name's *value was*, at that tick -- `S-B2Δ`, `OD-6`,
`R-SIM-25`'s own CLI signature). First version, seeded at `S-B2`/`S-B2Δ`
(`DG-2`); the CLI surface table's full shape (`sim_api_reference.md` §10)
lands at `S-D6`."""

from __future__ import annotations

import argparse
from pathlib import Path

from adas_sim.core.evidence import evidence, format_evidence
from adas_sim.core.explain import explain
from adas_sim.core.runner import build_session_from_recording


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim explain", description=__doc__)
    parser.add_argument("name")
    parser.add_argument("--session", required=True, type=Path)
    parser.add_argument("--at", type=int, default=None, metavar="TICK", help="report the evidence chain at this tick")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    session = build_session_from_recording(args.session)

    if args.at is not None:
        record = evidence(args.name, session, args.at)
        for field, text in format_evidence(record):  # UT-D3-8: the GUI evidence panel shares this formatter
            print(f"{field:<20} {text}")
        return 0 if record.kind != "unknown" else 1

    facts = explain(args.name, session)
    for key, value in facts.items():
        print(f"{key:<20} {value}")
    return 0 if facts["kind"] != "unknown" else 1
