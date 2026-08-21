# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`IMP-0189`/`SW-0189` -- explicit signal-header binding: which source
channel (already-declared, remapped port names -- never a new addressing
grammar, `R-SIM-21`) supplies a signal's reception-independent time
(`t_source`), its wrapping sequence counter, and its validity/status flag.
A map with **no** header binding for a signal is accepted -- that signal's
timing is reconstructed no better than reception order -- and is reported
at `RECEPTION_TIME`, the ladder's bottom rung (`IMP-0050`'s
`CycleReconstructor`, `bus.hpp::Rung`).

`Rung` here is a **local, by-name mirror** of `bus.hpp`'s C++ enum
(`SourceCycleId`/`HeaderCounter`/`SourceTime`/`ReceptionTime`) for this
module's own reporting purpose only -- it is not the cross-cutting,
`SV-8`-tracked Python vocabulary `WP-11`'s `check_closed_sets.py` still
carries as `NOT_YET` (that mirror, when it lands, is `bus`'s own
`IMP`/`WP`, not this one). `header.py` never reaches `SOURCE_CYCLE_ID`: a
recording's own embedded cycle marking is `CycleReconstructor`'s fact
(rung 1), discovered from the bytes, never declared in an ingest map.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Rung(StrEnum):
    SOURCE_CYCLE_ID = "source_cycle_id"
    HEADER_COUNTER = "header_counter"
    SOURCE_TIME = "source_time"
    RECEPTION_TIME = "reception_time"


#: The ladder's own order (`IMP-0050`), best first -- printed by `explain`
#: exactly like `description.py::TIER_ORDER`, never re-derived per call.
RUNG_ORDER: tuple[Rung, ...] = (
    Rung.SOURCE_CYCLE_ID, Rung.HEADER_COUNTER, Rung.SOURCE_TIME, Rung.RECEPTION_TIME,
)


@dataclass(frozen=True, slots=True)
class HeaderBinding:
    """Each field names a **port** (this run's remapped name, `map.py`'s
    own `_manifest_port` convention) -- never a raw topic string and never
    a byte offset. `None` means this channel is not declared for the
    signal; all three `None` is the "no header binding" case `IMP-0189`
    names explicitly as accepted."""

    t_source: str | None = None
    counter: str | None = None
    status: str | None = None

    def __repr__(self) -> str:
        return f"<HeaderBinding t_source={self.t_source!r} counter={self.counter!r} status={self.status!r}>"


def rung_for(binding: HeaderBinding | None) -> Rung:
    """The best rung this binding can support -- `header.py` never claims
    `SOURCE_CYCLE_ID` (that is discovered from bytes, not declared)."""
    if binding is None:
        return Rung.RECEPTION_TIME
    if binding.counter:
        return Rung.HEADER_COUNTER
    if binding.t_source:
        return Rung.SOURCE_TIME
    return Rung.RECEPTION_TIME
