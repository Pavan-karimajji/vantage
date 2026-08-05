# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim list ports|topics|layers|signals <path>` (`DG-1`,
`sim_naming_and_diagnostics.md` §2): "everything named is discoverable at
run time... no name is knowable only from source." Argument parsing and
formatting only (`GT-9`) -- every fact below comes from a source that
already exists (`adasManifest`, the recording's own topic index, an emitted
`Scene`, `Session.known_ports`), never a second, hand-maintained list.

    sim list ports <lib>          from adasManifest
    sim list topics <recording>   from the topic index
    sim list layers <session>     from the emitted Scene
    sim list signals <session>    the port-level address space (see below)

**`signals`, scoped honestly.** `DG-1`'s own wording is "ports x fields, the
one address space" -- the full claim needs each port's message class
resolved from its embedded schema and its fields walked recursively
(nested messages, repeated fields). That is real, separate work; what is
built here is the PORT-level address space only (every `known_ports` entry,
sorted) -- a real, useful subset, not the full field-level claim. Widening
this to field paths is the natural next slice, not attempted here.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from adas_sim.contracts.component import CtypesSilComponent
from adas_sim.core.runner import build_static_scene
from adas_sim.core.session import Session
from adas_sim.io.registry import reader_for


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim list", description=__doc__)
    parser.add_argument("what", choices=("ports", "topics", "layers", "signals"))
    parser.add_argument("path", type=Path)
    return parser


def _list_ports(lib_path: Path) -> int:
    component = CtypesSilComponent(lib_path)
    manifest = component.manifest
    print(f"inputs ({len(manifest.inputs)}):")
    for port in manifest.inputs:
        print(f"  {port.name:<28} {port.proto_type}")
    print(f"outputs ({len(manifest.outputs)}):")
    for port in manifest.outputs:
        print(f"  {port.name:<28} {port.proto_type}")
    return 0


def _list_topics(recording_path: Path) -> int:
    reader = reader_for(recording_path)
    try:
        topics = reader.topics()
        print(f"topics ({len(topics)}):")
        for name in sorted(topics):
            info = topics[name]
            print(f"  {name:<28} {info.schema_name or '(no schema)':<32} origin={info.provenance.value}")
        return 0
    finally:
        reader.close()


def _list_layers(session_path: Path) -> int:
    session = Session.open(session_path)
    scene = build_static_scene(session, 0)
    print(f"layers ({len(scene.layers)}):")
    for layer in scene.layers:
        default = "on" if layer.default_on else "off"
        print(f"  {layer.id:<28} group={layer.group:<16} prims={len(layer.prims):<4} default={default}")
    return 0


def _list_signals(session_path: Path) -> int:
    session = Session.open(session_path)
    print(f"signals, port-level ({len(session.known_ports)}) -- see this module's own docstring:")
    for name in sorted(session.known_ports):
        print(f"  {name}")
    return 0


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.what == "ports":
        return _list_ports(args.path)
    if args.what == "topics":
        return _list_topics(args.path)
    if args.what == "layers":
        return _list_layers(args.path)
    return _list_signals(args.path)
