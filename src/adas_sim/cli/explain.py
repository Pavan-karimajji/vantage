# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim explain <name>` -- what is this name, and where did it come from?

Resolves any name in the system -- a port, topic, layer, signal, error or id --
and prints what it is, what produced it and which document defines it. With
`--session` and `--at`, adds the value at that tick and its origin.

Prints the same record the viewer's evidence panel shows, so the headless and
GUI answers cannot drift apart.
"""

# Design refs: `GT-9` · `DG-2` · `OD-6`/`R-SIM-25` one producer, two formatters · `UT-D6-7`.
# A style token is resolved here, not in `core/explain.py`: `render/theme.py`
# sits above `core/` in the package map (`UT-A1-6`), so `core/` cannot import it.

from __future__ import annotations

import argparse
from pathlib import Path

from adas_sim.diagnostics.evidence import EVIDENCE_LABEL_WIDTH, evidence, format_evidence
from adas_sim.diagnostics.explain import explain, known_names
from adas_sim.diagnostics.suggest import near_matches
from adas_sim.core.runner import build_session_from_recording
from adas_sim.session.session import Session
from adas_sim.render.theme import THEMES, all_tokens, resolve as resolve_style_token


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim explain", description=__doc__)
    parser.add_argument("name")
    parser.add_argument("--session", required=True, type=Path)
    parser.add_argument("--at", type=int, default=None, metavar="TICK", help="report the evidence chain at this tick")
    return parser


def _explain_with_style_tokens(name: str, session: Session) -> dict[str, object]:
    if name in all_tokens():
        return {
            "kind": "style_token", "name": name,
            "colors": {theme: resolve_style_token(name, theme).color for theme in THEMES},
        }
    facts = explain(name, session)
    if facts["kind"] == "unknown":
        # Re-rank over the COMBINED candidate list rather than merging
        # core.explain's already-truncated top-3 with a second, separately
        # truncated style-token top-3: alphabetically re-sorting two
        # ranked-by-similarity lists throws away difflib's own ordering,
        # which can silently drop the actual best match (found by a real
        # test failure, not reasoned in advance).
        candidates = [*known_names(session), *all_tokens()]
        matches = near_matches(name, candidates)
        facts = {**facts, "did_you_mean": matches}
    return facts


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    session = build_session_from_recording(args.session)

    if args.at is not None:
        record = evidence(args.name, session, args.at)
        for field, text in format_evidence(record):  # UT-D3-8: the GUI evidence panel shares this formatter
            # Width derived from the field names, never typed -- see
            # `EVIDENCE_LABEL_WIDTH`.
            print(f"{field:<{EVIDENCE_LABEL_WIDTH}} {text}")
        return 0 if record.kind != "unknown" else 1

    facts = _explain_with_style_tokens(args.name, session)
    width = max((len(key) for key in facts), default=0) + 1
    for key, value in facts.items():
        print(f"{key:<{width}} {value}")
    return 0 if facts["kind"] != "unknown" else 1
