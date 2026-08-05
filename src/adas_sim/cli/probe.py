# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim probe <lib>|<recording>` -- argument parsing and layout only
(`GT-9`); the facts themselves come from either side. ONE verb, two kinds
of file, auto-detected (`sim_learn.md` SS5's own worked example runs both
a component library and a recording through this same verb -- there is
no second verb): a registered recording-codec extension (`.mcap`/`.csv`,
`io/registry.py`'s own table) means "what does this file provide" via
`Session.provides`/`Session.absent` (`core/runner.py`, `S-C9`); anything
else is tried as a component library via the generic ABI (`S-D6`,
`sim_resim_and_recording.md` §9: `"sim probe <lib> # port set from
adasManifest"`) -- **no mapping step, ever** (`sim_architecture.md` §5.16.1):
the port set printed is exactly `adasManifest()`'s own bytes, decoded, never
hand-maintained.

Answers "what does this file/library provide, and what is it known not to"
*before* a run starts (`R-SIM-23`'s own framing for the recording half) --
the same facts `sim_implementation_plan.md` S-C9 asks the (not-yet-built)
Bench start page to grey cuts by, and the same facts a from-scratch
component onboards itself with (`R-SIM-16`: "a new component is probed,
wired and run without one edit inside `modules/sim`").
"""

from __future__ import annotations

import argparse
from pathlib import Path

from adas_sim.contracts.component import CtypesSilComponent, PortSpec
from adas_sim.core.session import Session
from adas_sim.io.registry import is_registered_recording_extension


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
