# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim doctor` -- argument parsing and layout only (GT-9); the facts
themselves come from `adas_sim.core.diagnostics.doctor_report`."""

from __future__ import annotations

import argparse

from adas_sim.core.diagnostics import doctor_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim doctor", description=__doc__)
    return parser


def run(argv: list[str] | None = None) -> int:
    build_parser().parse_args(argv)
    for key, value in doctor_report().items():
        print(f"{key:<22} {value}")
    return 0
