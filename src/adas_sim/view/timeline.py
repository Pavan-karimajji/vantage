# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`TimelineState` -- which signals are lane'd, and the user's bookmarks
(S-B3 slice 8, `sim_visualization_spec.md` §7.3). Pure state, no pixels, no
Qt -- `view/` stays headless-testable, the same discipline `view/layers.py`
established. Resolving an address to a value is `core/signals.py`'s job
("one resolver, five consumers", `NR-SIM-8`); this module only tracks
*which* addresses are lane'd and in what kind, never a resolved value --
"values update live as the tick changes, including while scrubbing" (§7.2,
carried over here) falls out of never caching one.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EventMarker:
    """A state lane's transition (§7.3) -- `UT-B3-3`: one of these at
    every transition, and only there."""

    tick_index: int
    label: str


@dataclass(frozen=True, slots=True)
class Bookmark:
    tick_index: int
    label: str = ""


def event_markers(series: Sequence[tuple[int, object]]) -> tuple[EventMarker, ...]:
    """`UT-B3-3`. `series` is a `core/signals.resolve_series` result:
    `(tick_index, value)` pairs. A marker fires exactly where consecutive
    values differ -- never on every tick, never on a value repeating its
    predecessor."""
    markers: list[EventMarker] = []
    previous: object = None
    have_previous = False
    for tick_index, value in series:
        if have_previous and value != previous:
            markers.append(EventMarker(tick_index=tick_index, label=f"{previous} -> {value}"))
        previous = value
        have_previous = True
    return tuple(markers)


class TimelineState:
    """Which signals are lane'd, and the user's bookmarks. **No disk
    persistence yet** -- `view/layers.LayerTreeState` (§6) earned its
    per-(project, pipeline) `save()`/`load()` only once `MainWindow` needed
    it (`S-B3` slices 2 and 3); this class gets the same treatment if/when
    a later slice wires it in, rather than a speculative surface now.

    **Never two y-scales in one lane** (§7.3): `add_signal_lane` always
    creates a new lane for a new address; there is no "add to an existing
    lane" operation, so the one dangerous chart mistake this rule exists to
    ban is simply not representable.
    """

    def __init__(self) -> None:
        self._signal_lanes: list[str] = []
        self._state_lanes: list[str] = []
        self._bookmarks: list[Bookmark] = []

    def add_signal_lane(self, address: str) -> None:
        if address not in self._signal_lanes:
            self._signal_lanes.append(address)

    def remove_signal_lane(self, address: str) -> None:
        if address in self._signal_lanes:
            self._signal_lanes.remove(address)

    def add_state_lane(self, address: str) -> None:
        if address not in self._state_lanes:
            self._state_lanes.append(address)

    def remove_state_lane(self, address: str) -> None:
        if address in self._state_lanes:
            self._state_lanes.remove(address)

    def signal_lanes(self) -> tuple[str, ...]:
        return tuple(self._signal_lanes)

    def state_lanes(self) -> tuple[str, ...]:
        return tuple(self._state_lanes)

    def add_bookmark(self, tick_index: int, label: str = "") -> None:
        if any(b.tick_index == tick_index for b in self._bookmarks):
            return
        self._bookmarks.append(Bookmark(tick_index=tick_index, label=label))

    def remove_bookmark(self, tick_index: int) -> None:
        self._bookmarks = [b for b in self._bookmarks if b.tick_index != tick_index]

    def bookmarks(self) -> tuple[Bookmark, ...]:
        return tuple(sorted(self._bookmarks, key=lambda b: b.tick_index))

    def jump_to_event(
        self, current_tick: int, direction: int, markers: Sequence[EventMarker],
    ) -> int | None:
        """`[`/`]` (§5's transport table, "Jump to event"): the nearest
        marker or bookmark strictly before (`direction < 0`) or after
        (`direction > 0`) `current_tick`; `None` if there is none that way."""
        ticks = sorted({m.tick_index for m in markers} | {b.tick_index for b in self._bookmarks})
        if direction > 0:
            candidates = [t for t in ticks if t > current_tick]
            return min(candidates) if candidates else None
        candidates = [t for t in ticks if t < current_tick]
        return max(candidates) if candidates else None
