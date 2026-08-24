# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Conformance kit for the `"exporter"` extension point (`SW-0358`).

Checks a zero-argument writer factory (`plugins.registry.register_exporter`'s
own shape) actually satisfies `io.base.RecordingWriter`'s Protocol: `open`/
`write`/`close` are present and callable, a class-level `capabilities` is
declared, and a real open/write/close pass against a scratch path does not
raise.

The shipped template plug-in for this point is `io.csv.CsvWriter`, already
registered under `"csv"` (`plugins.registry.exporter_for("csv")`) --
`R-SIM-14`'s own distinction (an export is lossy and terminal, never a
resim input) is why this kit is separate from `reader_kit`'s, even though
both exercise `RecordingWriter`-shaped objects."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from adas_sim.io.base import RecordingWriter, RunManifest
from adas_sim.plugins.conformance.result import ConformanceResult

REQUIRED_METHODS = ("open", "write", "close")


def check_exporter(factory: Callable[[], RecordingWriter], out_path: Path, meta: RunManifest) -> ConformanceResult:
    problems: list[str] = []
    writer = factory()
    if not hasattr(type(writer), "capabilities"):
        problems.append("missing a class-level `capabilities` attribute")
    for name in REQUIRED_METHODS:
        if not callable(getattr(writer, name, None)):
            problems.append(f"missing a callable `{name}`")
    if not problems:
        try:
            writer.open(out_path, meta, {})
            writer.write("/template/marker", 0, b"", capture_time_ns=0)
        except Exception as exc:  # noqa: BLE001 -- reported as a conformance finding, not raised
            problems.append(f"open()/write() raised: {exc!r}")
        finally:
            writer.close()
    return ConformanceResult(ok=not problems, problems=tuple(problems))
