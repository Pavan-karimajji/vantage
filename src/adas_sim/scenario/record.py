# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`sim record <scenario> -o <out>` (`IMP-0125`, `SYS-0134`, `R-SIM-12`): produces a recording from a scenario file of explicit
values and executes nothing: no engine is started and no component is called. The verb parses arguments and delegates."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from adas_sim.diagnostics.errors import SimError
from adas_sim.scenario.scenario_file import load_scenario
from adas_sim.scenario.write import write_scenario_recording


def record_scenario(scenario_path: Path, out: Path) -> Path:
    """Loads and checks `scenario_path`, then writes its recording to `out`; nothing is written when the load fails."""
    return write_scenario_recording(load_scenario(scenario_path), out)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim record", description=__doc__)
    parser.add_argument("scenario", type=Path, help="scenario file (YAML) of explicit values")
    parser.add_argument("-o", "--output", type=Path, required=True, help="the recording to write (.mcap)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        written = record_scenario(args.scenario, args.output)
    except SimError as exc:
        print(f"[sim record] error: {exc}", file=sys.stderr)
        return exc.exit_code
    print(f"wrote {written}")
    return 0


run = main  # the verb table calls every verb's `run` (`orchestrate/verbs.py`)
