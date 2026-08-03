# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim probe <recording>` -- argument parsing and layout only (`GT-9`); the
facts themselves are `Session.provides`/`Session.absent`, computed once at
load (`core/runner.py`, `S-C9`). Answers "what does this file provide, and
what is it known not to" *before* a run starts (`R-SIM-23`'s own framing) --
the same facts `sim_implementation_plan.md` S-C9 asks the (not-yet-built)
Bench start page to grey cuts by.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from adas_sim.core.session import Session


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim probe", description=__doc__)
    parser.add_argument("recording", type=Path, help="path to a recording")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    session = Session.open(args.recording)

    print(f"recording        {args.recording}")
    print(f"run_id           {session.run_id}")
    print(f"manifest known   {session.meta.known}")
    print(f"ticks            {len(session)}")

    print(f"provides ({len(session.provides)}):")
    for name, provided in sorted(session.provides.items()):
        print(f"  {name:<28} {provided.proto_type or '(no schema)':<32} origin={provided.origin.value} topic={provided.topic}")

    print(f"absent ({len(session.absent)}):")
    for name, absent in sorted(session.absent.items()):
        print(f"  {name:<28} {absent.reason}")

    return 0
