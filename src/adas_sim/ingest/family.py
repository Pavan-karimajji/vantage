# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`IMP-0191`/`SW-0191`, `IMP-0192`/`SW-0192` -- declared match rules
deciding which `IngestMap`(s) apply to a given file, and the check that
refuses two applicable maps claiming one port.

Two independent match axes, because they answer different questions asked
at different times:

- **By topic** (`IngestMap.matches`, `map.py`, unchanged by this module) --
  needs the file open, decides per *topic* once the topic set is known.
  This was, before `WP-12`, the only axis; `IngestRecordingReader` already
  used it correctly.
- **By declared rule** (`match_family`, this module, `IMP-0191`'s own
  extension) -- a file-name glob or the recording's own embedded identity
  (`identity.py::SourceIdentity`), usable *before* opening the file, which
  is what `static.py`/`description.py`'s sidecar-precedence logic needs to
  pick a family without reading the recording payload first.

`check_no_double_claim` (`IMP-0192`) is **moved** out of `map.py`'s
`IngestRecordingReader.__init__`, which called this same check inline
before `WP-12`'s multi-map matching existed as a declared concept -- the
behaviour (an `AuthoringError` naming both families and the port) is
unchanged; only its home moved, so the multi-map world `IMP-0191` creates
has one place this rule lives, not two copies free to drift.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.ingest.identity import SourceIdentity

if TYPE_CHECKING:
    from adas_sim.ingest.map import IngestMap, ProvidedPort


def match_family(
    path: Path, maps: Sequence["IngestMap"], *, identity: SourceIdentity | None = None,
) -> tuple["IngestMap", ...]:
    """Every map whose declared rule fires for `path` -- its `path_glob`
    matches the file name, or (when `identity` is already known, e.g. from
    an embedded meta block) its own `family:` equals `identity.family`.
    Neither rule opens the file; `identity` is a caller-supplied fact, not
    something this function reads off disk."""
    matched = []
    for ingest_map in maps:
        by_glob = ingest_map.path_glob is not None and fnmatch.fnmatch(path.name, ingest_map.path_glob)
        by_identity = identity is not None and ingest_map.family == identity.family
        if by_glob or by_identity:
            matched.append(ingest_map)
    return tuple(matched)


def check_no_double_claim(claims: Mapping[str, Sequence["ProvidedPort"]], *, where: str) -> None:
    """`claims`: raw topic -> every `ProvidedPort` (from every applicable
    map) claiming it. More than one claimant for a topic is an
    `AuthoringError` naming both families and the topic -- `matches:`
    exists precisely so two components' recording families do not have to
    agree on a shared topic vocabulary to coexist on one plug-in path."""
    for topic, claimants in claims.items():
        if len(claimants) > 1:
            families = sorted({c.family for c in claimants})
            raise AuthoringError(
                expected="at most one ingest map to claim a given topic",
                found=f"topic {topic!r} claimed by {families}", where=where,
                hint="narrow one map's matches: any_topic:, or fold the two families",
            )
