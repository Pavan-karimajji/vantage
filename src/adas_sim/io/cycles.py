# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-09`, `cycles` item (`SW-0030`..`SW-0032`): the declared cycle set a
recording carries -- each stage's own sample period (`R-SIM-18`,
`io.base.ComponentBuildInfo.period_ns`), discovered from the recording
alone, never from a caller-supplied configuration. `viz/cpp/viz/player/
stepping.cpp::NextCycleBoundary` (`WP-09`'s own C++ half, `IMP-0029`) reads
exactly this shape from the recording's embedded run manifest.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from adas_sim.io.base import RunManifest


class _MetaReader(Protocol):
    def meta(self) -> RunManifest: ...


@dataclass(frozen=True, slots=True)
class Cycle:
    """`WP-09` (`SW-0031`): one declared cycle -- `name` is the owning
    stage's own name, `index` its position in discovery order, `period_ns`
    its declared sample period as an integer (the two-clock discipline the
    recording model already uses, never a float)."""

    name: str
    index: int
    period_ns: int


def discover(reader: _MetaReader) -> list[Cycle]:
    """`WP-09` (`SW-0030`): derives the cycle set from `reader` alone --
    every stage `reader.meta().components` declares a nonzero `period_ns`
    for. No configuration parameter exists to pass; the set changes only
    when the recording does."""
    manifest = reader.meta()
    return [
        Cycle(name=component.name, index=index, period_ns=component.period_ns)
        for index, component in enumerate(manifest.components)
        if component.period_ns > 0
    ]


def run_of(topic: str, log_time_ns: int, *, period_ns: int) -> int:
    """`WP-09` (`SW-0032`): which run of a `period_ns`-period cycle
    `log_time_ns` falls in -- a lookup (integer division), never a
    reconstruction from surrounding messages. `topic` names what this run
    number is being attributed to; it is not itself part of the
    computation, since attribution is the caller's own concern."""
    del topic  # attribution-only, per this function's own docstring
    return log_time_ns // period_ns
