# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Conformance kit for the `"reader"` extension point (`SW-0358`).

Checks a reader factory (`Callable[[Path], RecordingReader]`, `plugins.
registry.register`'s own `reader=` shape) actually satisfies `io.base.
RecordingReader`'s Protocol against a real sample recording: the four
required methods are present and callable, a class-level `capabilities` is
declared, and a real `meta()`/`topics()`/`messages()` pass does not raise.

The shipped template plug-in for this point is `io.jsonl.JsonlReader`,
already registered for `.jsonl` (`DD-04`'s one-codec-implementation rule
means this kit exercises the real thing rather than a second, parallel
"just for conformance" reader)."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from adas_sim.io.base import RecordingReader
from adas_sim.plugins.conformance.result import ConformanceResult

REQUIRED_METHODS = ("meta", "topics", "messages", "close")


def check_reader(factory: Callable[[Path], RecordingReader], sample_path: Path) -> ConformanceResult:
    problems: list[str] = []
    reader = factory(sample_path)
    if not hasattr(type(reader), "capabilities"):
        problems.append("missing a class-level `capabilities` attribute")
    for name in REQUIRED_METHODS:
        if not callable(getattr(reader, name, None)):
            problems.append(f"missing a callable `{name}`")
    if not problems:
        try:
            reader.meta()
            reader.topics()
            list(reader.messages())
        except Exception as exc:  # noqa: BLE001 -- reported as a conformance finding, not raised
            problems.append(f"meta()/topics()/messages() raised: {exc!r}")
        finally:
            reader.close()
    return ConformanceResult(ok=not problems, problems=tuple(problems))
