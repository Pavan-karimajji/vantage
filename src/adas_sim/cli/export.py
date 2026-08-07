# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim export <in> <out> --ports …` -- recording to a flat file.

Writes a selected port subset to a declared column schema, carrying the source
recording's timebase and origin tags.

An export is lossy and terminal: it is never accepted back as a resim input.
"""

# Design refs: `GT-9` · `R-SIM-14` an export is lossy and terminal, never a resim input

from __future__ import annotations

import argparse
from pathlib import Path

from adas_sim.io.csv import CsvWriter
from adas_sim.io.registry import reader_for


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim export", description=__doc__)
    parser.add_argument("recording_in", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--ports", default=None, help="comma-separated dotted port names (N-2); default: every port")
    parser.add_argument("--on-missing", default="error", choices=["error", "blank", "omit-column"])
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # Deferred, same reasoning as `cli/convert.py`: mcap is a hard
    # dependency of `adas_sim.io.mcap`, not of `adas_sim.io` itself.
    import adas_sim.io.mcap  # noqa: F401

    reader = reader_for(args.recording_in)
    try:
        meta = reader.meta()
        topics = reader.topics()
        ports = [p.strip() for p in args.ports.split(",")] if args.ports else None
        writer = CsvWriter(ports=ports, on_missing=args.on_missing)
        writer.open(args.out, meta, topics)
        message_count = 0
        for topic, log_time_ns, capture_time_ns, payload in reader.messages():
            writer.write(topic, log_time_ns, payload, capture_time_ns=capture_time_ns)
            message_count += 1
        writer.close()
        print(f"wrote {args.out} ({message_count} messages)")
        return 0
    finally:
        reader.close()
