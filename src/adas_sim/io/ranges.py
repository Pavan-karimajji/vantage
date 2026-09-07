# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-10`, `ranges` item (`SW-0033`..`SW-0035`): named spans in a
recording's own timebase, for a batch run to honour or ignore
(`R-SIM-6`'s recording model, `SYS-0021`). `write`/`read` use the same
JSON-safe-mapping-through-a-meta-block shape the run manifest and the
config bundle already travel by, so a range lives WITH the recording,
never beside it in a side-car file.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Range:
    """`WP-10` (`SW-0033`): a named span expressed in the recording's own
    integer-nanosecond timebase (`log_time_ns`) -- `start_ns`/`end_ns` are
    the only fields. No wall-clock field is defined to be tempted by, so a
    stored range means the same ticks on any host, clock or timezone."""

    name: str
    start_ns: int
    end_ns: int

    def contains(self, tick_ns: int) -> bool:
        """`WP-10` (`SW-0035`): inclusive at both bounds -- stated here
        because the boundary case is the one a caller decides by accident."""
        return self.start_ns <= tick_ns <= self.end_ns


class RangeStore(Protocol):
    """`WP-10`'s own `F-STORE` contract: ranges travel through whatever
    already carries a recording's other meta blocks (the run manifest, the
    config bundle) -- a real recording's meta-block writer/reader already
    matches this shape once ranges are serialized to JSON-safe mappings,
    and a lightweight test double can implement just this."""

    def write_ranges(self, ranges: Sequence[Mapping[str, object]]) -> None: ...

    def read_ranges(self) -> Sequence[Mapping[str, object]]: ...


def write(store: RangeStore, ranges: Sequence[Range]) -> None:
    """`WP-10` (`SW-0034`): every field a `Range` has, and nothing else --
    the same discipline `manifest_to_dict` follows for the run manifest."""
    store.write_ranges([{"name": r.name, "start_ns": r.start_ns, "end_ns": r.end_ns} for r in ranges])


def read(store: RangeStore) -> tuple[Range, ...]:
    """`WP-10` (`SW-0034`): the inverse of `write` -- name and bounds
    restored unchanged, in the order they were written."""
    return tuple(
        Range(name=str(d["name"]), start_ns=int(d["start_ns"]), end_ns=int(d["end_ns"]))
        for d in store.read_ranges()
    )
