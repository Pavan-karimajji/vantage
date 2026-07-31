# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`Session` -- the viewer's ONLY input (R-SIM-13, sim_api_reference.md §2.3).
Splits executing from viewing, which is what makes backwards seek possible at
all (`S-B2`'s purpose).

**Naming note.** Api reference's `Session` sketch types `events:
Sequence[Event]` without qualifying which `Event` -- but `core/logging.py`
already has an `Event` (the closed log-line vocabulary, `N-10`, from `S-A1`).
A timeline marker (a state transition, a bookmark) is a different concept
than a log event; naming both classes `Event` would be exactly the kind of
collision `N-3` exists to prevent. Named `SessionEvent` here instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from adas_sim.core.errors import AuthoringError
from adas_sim.core.signals import resolve_series
from adas_sim.core.tick import Tick
from adas_sim.io.base import RunManifest


@dataclass(frozen=True, slots=True)
class SessionEvent:
    """A timeline marker: a state transition, a bookmark, an expectation
    result. Deeper structure (state-lane transitions, `sim check` results)
    is `S-B3`/`S-D6`'s job; this is the shape those stages extend."""

    t_ns: int
    kind: str
    label: str = ""

    def __repr__(self) -> str:
        return f"<SessionEvent t_ns={self.t_ns} kind={self.kind!r}>"


@dataclass(frozen=True, slots=True)
class Session:
    """An immutable, indexable run. The viewer's ONLY input (R-SIM-13)."""

    run_id: str
    name: str
    ticks: tuple[Tick, ...]
    events: tuple[SessionEvent, ...] = ()
    meta: RunManifest = field(default_factory=RunManifest)
    #: False for a live sim -> disables recompute-from-0 (view/transport.py).
    deterministic: bool = True
    #: This run's declared port universe -- the recording's own topics,
    #: computed once at load (`S-B1Δ`, `R-SIM-21`), never re-derived per
    #: tick. What `LayerCtx.known_ports` carries into a layer provider's
    #: `self.<port>` resolution.
    known_ports: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        # Session is immutable (UT-B2-11): pass 2 must not be able to
        # corrupt what pass 1 produced. Ticks are already individually
        # immutable (core/tick.py); this locks the sequence itself too.
        object.__setattr__(self, "ticks", tuple(self.ticks))
        object.__setattr__(self, "events", tuple(self.events))

    @classmethod
    def open(cls, path: Path, *, codec: str | None = None) -> Session:
        from adas_sim.core.runner import build_session_from_recording

        return build_session_from_recording(path, codec=codec)

    def at(self, index: int) -> Tick:
        try:
            return self.ticks[index]
        except IndexError:
            raise AuthoringError(
                expected=f"a tick index in [0, {len(self.ticks)})", found=str(index),
                where="adas_sim.core.session.Session.at", hint="",
            ) from None

    def signal(self, path: str, *, project: str = "base") -> tuple[tuple[int, object], ...]:
        """`path`'s value at every tick (`NR-SIM-8`, `sim_api_reference.md`
        §2.3) -- delegates to `core/signals.resolve_series`. No import cycle
        (unlike `open()`'s deferred import of `core/runner` below): that
        function takes `self.ticks`, never a `Session`, so `core/signals.py`
        never needs to import this module back."""
        return resolve_series(self.ticks, path, project=project)

    def seek_ns(self, t_ns: int) -> int:
        """The index of the tick whose `t_ns` is the greatest value `<=
        t_ns` (boundary-exact); clamps to tick 0 if `t_ns` precedes it."""
        if not self.ticks:
            raise AuthoringError(
                expected="a non-empty session", found="0 ticks",
                where="adas_sim.core.session.Session.seek_ns", hint="",
            )
        if t_ns <= self.ticks[0].t_ns:
            return 0
        lo, hi = 0, len(self.ticks) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.ticks[mid].t_ns <= t_ns:
                lo = mid
            else:
                hi = mid - 1
        return lo

    def __len__(self) -> int:
        return len(self.ticks)

    def __repr__(self) -> str:
        return f"<Session {self.name!r} ticks={len(self.ticks)} deterministic={self.deterministic}>"
