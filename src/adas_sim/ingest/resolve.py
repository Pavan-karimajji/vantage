# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-01`, `resolver` item (`SW-0004`..`SW-0007`): per-port resolution of an
ingest map's ordered `from:` candidate list (`ingest/map.py::ProvidedPort.
candidates`) against a recording's real topic index. A pure function over
plain data -- no file is opened here, so ordering and match-reporting are
testable with a `dict[str, TopicInfo]` stand-in (`R-SIM-23`'s own "renames
and tags only": resolution never computes a value, it only picks which
declared address, if any, this recording actually carries).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from adas_sim.io.base import TopicInfo


@dataclass(frozen=True, slots=True)
class Resolution:
    """One port's resolution outcome (`SW-0005`) -- exactly one per port,
    so nothing downstream re-derives whether a port resolved. `chosen` is
    the matched candidate address, or `None` when every candidate was
    absent or type-mismatched (`SW-0007`'s "exhausted candidates")."""

    port: str
    chosen: str | None = None


@dataclass(frozen=True, slots=True)
class Unresolved:
    """A port whose candidates were tried and none matched -- distinct in
    type from `Absent` below (`SW-0007`): this port was expected and
    looked for, never a spelling of "we never expected it.\""""

    port: str


@dataclass(frozen=True, slots=True)
class Absent:
    """A port the ingest map declares `absent:` (`ingest/map.py::
    AbsentPort`'s own reason) -- never attempted, so never confusable with
    `Unresolved` above by type alone."""

    port: str
    reason: str


def resolve_port(
    port: str,
    candidates: Sequence[str],
    index: Mapping[str, TopicInfo],
    *,
    proto_type: str = "",
) -> Resolution:
    """Tries `candidates` in the declared order (`SW-0004`), stopping at
    the first present in `index` whose payload type matches `proto_type`
    (`SW-0006`) -- a mismatched candidate is skipped, never coerced.
    `proto_type` empty (the port declares none) skips the type check
    entirely. Returns exactly one `Resolution` either way; `chosen` is
    `None` when every candidate was absent or type-mismatched."""
    for candidate in candidates:
        info = index.get(candidate)
        if info is None:
            continue
        if proto_type and info.schema_name != proto_type:
            continue
        return Resolution(port=port, chosen=candidate)
    return Resolution(port=port, chosen=None)
