# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`sim convert <in> <out>` -- recording -> recording, refused when either
side lacks `round_trips` (`R-SIM-14`, `S-D7`). Argument parsing plus the
copy itself (`GT-9`): every fact comes from `io/registry.py`'s
`RecordingReader`/`RecordingWriter` Protocols, nothing reinterprets a
message along the way."""

from __future__ import annotations

import argparse
from pathlib import Path

from adas_sim.core.errors import AuthoringError
from adas_sim.io.registry import reader_for, writer_for


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sim convert", description=__doc__)
    parser.add_argument("recording_in", type=Path)
    parser.add_argument("recording_out", type=Path)
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # Deferred: mcap (the only registered reader) is a hard dependency of
    # `adas_sim.io.mcap`, not of `adas_sim.io` itself (`UT-A1-2`).
    import adas_sim.io.mcap  # noqa: F401

    reader = reader_for(args.recording_in)
    try:
        if not reader.capabilities.round_trips:
            raise AuthoringError(
                expected="a source codec with round_trips=True",
                found=f"{args.recording_in.suffix!r} lacks round_trips",
                where=str(args.recording_in), hint="an export (write-only) cannot be a convert source",
            )
        writer = writer_for(args.recording_out)
        if not writer.capabilities.round_trips:
            raise AuthoringError(
                expected="a destination codec with round_trips=True",
                found=f"{args.recording_out.suffix!r} lacks round_trips",
                where=str(args.recording_out), hint="pick a round-tripping output format",
            )

        meta = reader.meta()
        topics = reader.topics()
        # `config_bundle_bytes()` is an extra beyond the Protocol's minimum
        # (`io/mcap.py`'s own docstring, `sim_api_reference.md` §11) -- carried
        # through when both sides support it, never silently dropped.
        get_bundle = getattr(reader, "config_bundle_bytes", None)
        open_kwargs = {"config_bundle_bytes": get_bundle()} if get_bundle is not None else {}

        writer.open(args.recording_out, meta, topics, **open_kwargs)
        message_count = 0
        for topic, log_time_ns, payload in reader.messages():
            writer.write(topic, log_time_ns, payload)
            message_count += 1
        writer.close()
        print(f"wrote {args.recording_out} ({len(topics)} topics, {message_count} messages)")
        return 0
    finally:
        reader.close()
