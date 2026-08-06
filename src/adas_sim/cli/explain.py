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
completed at `S-D6` (`UT-D6-7`).

`_explain_with_style_tokens` is the one place this file carries more than
argument parsing (`GT-9`): a style token is a `render/theme.py` concept, and
`render/` sits ABOVE `core/` in the package map (`sim_api_reference.md` §1,
`UT-A1-6`), so `core.explain.explain` cannot check it. `cli/` is allowed to
import `render/` (`sim doctor`/`sim explain` stay light regardless --
`render/theme.py` itself imports neither Qt nor matplotlib), so the one
extra branch lives here rather than growing a second "explain" module.
"""

from __future__ import annotations

import argparse
import difflib
from pathlib import Path

from adas_sim.core.evidence import evidence, format_evidence
from adas_sim.core.explain import explain, known_names
from adas_sim.core.runner import build_session_from_recording
from adas_sim.core.session import Session
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
        matches = difflib.get_close_matches(name, candidates, n=3, cutoff=0.6)
        facts = {**facts, "did_you_mean": matches}
    return facts


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    session = build_session_from_recording(args.session)

    if args.at is not None:
        record = evidence(args.name, session, args.at)
        for field, text in format_evidence(record):  # UT-D3-8: the GUI evidence panel shares this formatter
            print(f"{field:<20} {text}")
        return 0 if record.kind != "unknown" else 1

    facts = _explain_with_style_tokens(args.name, session)
    for key, value in facts.items():
        print(f"{key:<20} {value}")
    return 0 if facts["kind"] != "unknown" else 1
