# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim check <scenario-set> [--report <path>]` -- headless, no rendering,
exits non-zero on any failed expectation (`sim_scenarios_and_expectations.md`
SS6, `sim_api_reference.md` SS10). Argument parsing only (`GT-9`);
`check.runner.check_scenarios` is the real, directly-testable engine.
"""

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
        help="a directory to search for a dll:/stubdll: stage's library (repeatable, contracts.loader.resolve_library)",
    )
    parser.add_argument(
        "--config", type=Path,
        help="config path forwarded to each stage's adasInit -- adasInit(NULL)'s own bundle "
             "resolution is S-C5, not yet built, so a real dll:/stubdll: stage needs this explicitly",
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
