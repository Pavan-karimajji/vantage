# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim explain <name>` -- what is this name, and where did it come from?

Resolves any name in the system -- a port, topic, signal, error or id -- and
prints what it is, what produced it and which document defines it. With
`--session` and `--at`, adds the value at that tick and its origin.

**No style-token or layer resolution any more.** Both retired with the rest
of the Python scene/render/player tree (`SM-12`,
`docs/VIZ_Sync_Plan_v0.1.md`) -- `render/theme.py`, the module this once
imported for style tokens, is gone, and `viz`'s own C++ `Console`/`--explain`
are the live equivalent for anything rendered.
"""

# Design refs: `GT-9` · `DG-2` · `OD-6`/`R-SIM-25` one producer, two formatters · `UT-D6-7`.

from __future__ import annotations

import argparse
from pathlib import Path

from adas_sim.diagnostics.evidence import EVIDENCE_LABEL_WIDTH, evidence, format_evidence
from adas_sim.diagnostics.explain import explain
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
        for field, text in format_evidence(record):
            # Width derived from the field names, never typed -- see
            # `EVIDENCE_LABEL_WIDTH`.
            print(f"{field:<{EVIDENCE_LABEL_WIDTH}} {text}")
        return 0 if record.kind != "unknown" else 1

    facts = explain(args.name, session)
    width = max((len(key) for key in facts), default=0) + 1
    for key, value in facts.items():
        print(f"{key:<{width}} {value}")
    return 0 if facts["kind"] != "unknown" else 1
