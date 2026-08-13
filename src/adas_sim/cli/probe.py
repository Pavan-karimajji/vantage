# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim probe <lib>|<recording>` -- what does this thing provide?

Given a component library, prints the port set read from `adasManifest()`.
Given a recording, prints the ports it provides, the ports it is known not to
carry, and which pipeline cuts it therefore supports.

One verb, two kinds of file, told apart by extension. Answers the question
before a run starts rather than by failing one.
"""

# Design refs: `GT-9` · `R-SIM-23` feasible cuts are a property of the recording ·
# `R-SIM-16` a component onboards itself -- the port set is `adasManifest()`'s
# own bytes, decoded, never a hand-maintained mapping

from __future__ import annotations

import argparse
from pathlib import Path

from adas_sim.resolve.component import CtypesSilComponent, PortSpec
from adas_sim.session.session import Session
from adas_sim.plugins.registry import is_registered_recording_extension


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim probe", description=__doc__)
    parser.add_argument("path", type=Path, help="a component library (dll:/stubdll:) or a recording")
    return parser


def _print_port(port: PortSpec) -> None:
    optional = " optional" if port.optional else ""
    owner = f" owner={port.owner_function}" if port.owner_function else ""
    period = f" period_us={port.period_us}" if port.period_us else ""
    print(f"  {port.name:<28} {port.proto_type:<40}{optional}{owner}{period}")


def _probe_library(path: Path) -> int:
    component = CtypesSilComponent(path)
    manifest = component.manifest
    print(f"library          {path}")
    print(f"component        {manifest.component}")
    print(f"version          {manifest.version}")
    print(f"abi_version      {manifest.abi_version}")
    print(f"build_id         {manifest.build_id}")
    print(f"project          {manifest.project or '(unset)'}")
    print(f"config_bundle    {manifest.config_bundle_sha256 or '(unresolved -- adasInit(NULL) will fail)'}")
    print(f"period_ns        {manifest.period_ns or '(undeclared -- runs every tick)'}")
    print(f"inputs ({len(manifest.inputs)}):")
    for port in manifest.inputs:
        _print_port(port)
    print(f"outputs ({len(manifest.outputs)}):")
    for port in manifest.outputs:
        _print_port(port)
    return 0


def _probe_recording(path: Path) -> int:
    session = Session.open(path)

    print(f"recording        {path}")
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


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if is_registered_recording_extension(args.path.suffix):
        return _probe_recording(args.path)
    return _probe_library(args.path)
