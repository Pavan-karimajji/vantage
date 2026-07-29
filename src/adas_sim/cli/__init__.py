# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Argument parsing only (GT-9, sim_api_reference.md §10). `sim = adas_sim.cli:main`
is the sole process entry point, so the console is reconfigured to UTF-8 here
once (P-4) and nowhere else needs to."""

from __future__ import annotations

import argparse
import sys

from adas_sim.cli import doctor
from adas_sim.core.console import reconfigure_console_utf8


def main(argv: list[str] | None = None) -> int:
    reconfigure_console_utf8()
    argv = list(sys.argv[1:]) if argv is None else list(argv)

    parser = argparse.ArgumentParser(prog="sim")
    subparsers = parser.add_subparsers(dest="verb", required=True)
    subparsers.add_parser("doctor", help="report the environment (DG-3)")

    args, remainder = parser.parse_known_args(argv)
    if args.verb == "doctor":
        return doctor.run(remainder)
    return 1  # unreachable: "doctor" is the only registered verb so far
