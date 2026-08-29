# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim list ports|topics|signals <path>` -- enumerate one kind of name.

Takes a component library, a recording or a session, and prints the names of
the requested kind. The companion to `sim explain`, which describes one name;
this prints all of them.

**No `layers` kind.** Python layer providers retired with the rest of the
Python scene/render/player tree (`SM-12`, `docs/VIZ_Sync_Plan_v0.1.md`) --
`viz`'s own C++ `Console` (`list layers <scene_index>`) is the live
equivalent (`SM-05`'s narrative in that same document).
"""

# Design refs: `GT-9` · `DG-1`

from __future__ import annotations

import argparse
from pathlib import Path

from adas_sim.resolve.probe import probe_manifest
from adas_sim.session.session import Session
from adas_sim.plugins.registry import reader_for


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim list", description=__doc__)
    parser.add_argument("what", choices=("ports", "topics", "signals"))
    parser.add_argument("path", type=Path)
    return parser


def _list_ports(lib_path: Path) -> int:
    # `probe_manifest` (`resolve/probe.py`, `SW-0409`): reads `adasManifest()`
    # only, never opening a component handle -- this verb never needs one.
    manifest = probe_manifest(lib_path)
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
    return _list_signals(args.path)
