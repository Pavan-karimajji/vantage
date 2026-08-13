# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`PlotState` -- which signals one plot panel shows, and how (S-B3 slice
10, `sim_visualization_spec.md` §7.4). Pure state, no pixels, no Qt --
`view/` stays headless-testable. A user opens several plot panels (unlike
`view/timeline.py`'s one fixed strip); each gets its own `PlotState`.

**One address space, four panel types, one resolver** (`NR-SIM-8`): a
`PlotState` never resolves a value itself -- `core/signals.py` does that,
same as `view/timeline.py`. This module only tracks *which* addresses a
panel wants and *how* (lane-per-signal for `timeseries`/`state`, exactly
`x`/`y`/optional `color` for `xy`, exactly one address for
`distribution`), so a resolver call is never duplicated across panel types.
"""

from __future__ import annotations

from adas_sim.diagnostics.errors import AuthoringError

#: Closed set -- adding a fifth panel type is a framework change with a
#: reason, the same discipline `scene/types.py`'s `Prim` catalogue holds.
KNOWN_KINDS = frozenset({"timeseries", "xy", "state", "distribution"})

#: `timeseries`/`state` share lane bookkeeping (§7.3's "never two y-scales
#: in one lane", carried over unchanged from `view/timeline.TimelineState`).
_LANE_KINDS = frozenset({"timeseries", "state"})


class PlotState:
    """One plot panel's configuration. `kind` is fixed at construction --
    a panel does not change type after being opened, the reference
    console's own model (retyping a panel mid-session is a different
    feature nobody asked for)."""

    def __init__(self, kind: str) -> None:
        if kind not in KNOWN_KINDS:
            raise AuthoringError(
                expected=f"one of {sorted(KNOWN_KINDS)}", found=repr(kind),
                where="adas_sim.player.panels.plots.PlotState", hint="",
            )
        self.kind = kind
        self._lanes: list[str] = []
        self.x: str | None = None
        self.y: str | None = None
        self.color: str | None = None
        self.address: str | None = None

    def _require_kind(self, *allowed: str) -> None:
        if self.kind not in allowed:
            raise AuthoringError(
                expected=f"a panel of kind {allowed}", found=f"kind={self.kind!r}",
                where="adas_sim.player.panels.plots.PlotState", hint="",
            )

    # -- timeseries / state: one lane per signal, never merged -----------------

    def add_lane(self, address: str) -> None:
        self._require_kind(*_LANE_KINDS)
        if address not in self._lanes:
            self._lanes.append(address)

    def remove_lane(self, address: str) -> None:
        self._require_kind(*_LANE_KINDS)
        if address in self._lanes:
            self._lanes.remove(address)

    def lanes(self) -> tuple[str, ...]:
        return tuple(self._lanes)

    # -- xy: exactly x, y, optional color ---------------------------------------

    def set_xy(self, x: str, y: str, color: str | None = None) -> None:
        self._require_kind("xy")
        self.x, self.y, self.color = x, y, color

    # -- distribution: exactly one address ---------------------------------------

    def set_distribution(self, address: str) -> None:
        self._require_kind("distribution")
        self.address = address

    def __repr__(self) -> str:
        return f"<PlotState kind={self.kind!r}>"
