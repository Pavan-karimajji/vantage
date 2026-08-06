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

from adas_sim.cli import doctor, explain
from adas_sim.core.console import reconfigure_console_utf8


def main(argv: list[str] | None = None) -> int:
    reconfigure_console_utf8()
    argv = list(sys.argv[1:]) if argv is None else list(argv)

    parser = argparse.ArgumentParser(prog="sim")
    subparsers = parser.add_subparsers(dest="verb", required=True)
    subparsers.add_parser("doctor", help="report the environment (DG-3)")
    subparsers.add_parser("explain", help="explain any name in the system (DG-2)", add_help=False)
    subparsers.add_parser("probe", help="what a recording provides, and what it doesn't (S-C9)", add_help=False)
    subparsers.add_parser("view", help="open the GUI viewer on a recording (S-B3)", add_help=False)
    subparsers.add_parser("render", help="headless snapshot to a PNG (S-B3)", add_help=False)
    subparsers.add_parser("convert", help="recording -> recording (S-D7)", add_help=False)
    subparsers.add_parser("export", help="recording -> CSV, port-selectable (S-D7)", add_help=False)
    subparsers.add_parser("record", help="drive a source, execute nothing (S-C2)", add_help=False)
    subparsers.add_parser("run", help="drive a source and execute a pipeline, live (S-C2)", add_help=False)
    subparsers.add_parser("resim", help="execute a pipeline against a recording (S-C2)", add_help=False)
    subparsers.add_parser("check", help="evaluate expect: against a scenario set, headless (S-C3)", add_help=False)
    subparsers.add_parser("determinism", help="compare two recordings, axis derived not flagged (S-C6)", add_help=False)
    subparsers.add_parser("batch", help="run a pipeline over a recording set, isolated per recording (S-D7)", add_help=False)
    subparsers.add_parser("list", help="list ports|topics|layers|signals for a lib/recording/session (S-D6, DG-1)", add_help=False)

    args, remainder = parser.parse_known_args(argv)
    if args.verb == "doctor":
        return doctor.run(remainder)
    if args.verb == "explain":
        return explain.run(remainder)
    if args.verb == "probe":
        # Deferred: opening a recording eventually needs a real codec (mcap),
        # same reasoning as convert/export below.
        from adas_sim.cli import probe
        return probe.run(remainder)
    if args.verb == "view":
        # Deferred: `cli.view` pulls in PySide6 (the "viewer" extra) --
        # `sim doctor`/`sim explain`/`sim render` must stay usable with
        # neither Qt nor matplotlib installed (`UT-A1-2`'s own discipline).
        from adas_sim.cli import view
        return view.run(remainder)
    if args.verb == "render":
        # Deferred: `cli.render` pulls in matplotlib (the "figures" extra),
        # same reasoning.
        from adas_sim.cli import render
        return render.run(remainder)
    if args.verb == "convert":
        # Deferred: mcap is a hard dependency of `adas_sim.io.mcap`, not of
        # `adas_sim.io`/`adas_sim.cli` themselves (`UT-A1-2`).
        from adas_sim.cli import convert
        return convert.run(remainder)
    if args.verb == "export":
        from adas_sim.cli import export
        return export.run(remainder)
    if args.verb == "record":
        from adas_sim.cli import record
        return record.run(remainder)
    if args.verb == "run":
        from adas_sim.cli import run as run_verb
        return run_verb.run(remainder)
    if args.verb == "resim":
        from adas_sim.cli import resim
        return resim.run(remainder)
    if args.verb == "check":
        from adas_sim.cli import check
        return check.run(remainder)
    if args.verb == "determinism":
        from adas_sim.cli import determinism
        return determinism.run(remainder)
    if args.verb == "batch":
        from adas_sim.cli import batch
        return batch.run(remainder)
    if args.verb == "list":
        # Deliberately NOT `adas_sim.cli.list` -- importing a submodule
        # named `list` sets a `list` attribute on the `adas_sim.cli`
        # PACKAGE module object, which IS this module's own globals()
        # (found the hard way: it shadowed the `list()` builtin used two
        # lines above this dispatch, breaking every OTHER verb once
        # anything imported `adas_sim.cli.list`).
        from adas_sim.cli import list_cmd
        return list_cmd.run(remainder)
    return 1  # unreachable: every registered verb is dispatched above
