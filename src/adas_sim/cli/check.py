# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim check <scenario-set>` -- evaluate `expect:` blocks headless.

Runs every scenario in the directory and evaluates its acceptance criteria.
Exits non-zero if any expectation fails, so it works as a CI gate. `--report`
writes the result as a file.
"""

# Design refs: `GT-9` (no logic here -- `check/` is the engine) · `R-SIM-8` expectations are data

from __future__ import annotations

import argparse
from pathlib import Path

from adas_sim.check.report import format_report_md, suite_passed, write_report
from adas_sim.check.runner import check_scenarios


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim check", description=__doc__)
    parser.add_argument("scenario_set", type=Path, help="a scenario file, or a directory of scenarios")
    parser.add_argument("--report", type=Path, help="write the report here (.md text, or .json by extension)")
    parser.add_argument(
        "--search", type=Path, action="append", default=[],
        help="a directory to search for a dll:/stubdll: stage's library "
            "(repeatable)",
    )
    parser.add_argument(
        "--config", type=Path,
        help="config path forwarded to each stage's adasInit; falls back to the "
            "bundle beside the library",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    results = check_scenarios(args.scenario_set, search=args.search, config_path=args.config)

    print(format_report_md(results), end="\n")
    if args.report:
        write_report(results, args.report)
        print(f"wrote {args.report}")

    return 0 if suite_passed(results) else 1
