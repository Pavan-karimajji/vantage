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

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from adas_sim.graph.pipeline import Pipeline
from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.graph.feasible import (
    CutFeasibility, ModuleManifest, RecordingIndex, RecordingTopic, feasible_cuts as _feasible_cuts,
)
from adas_sim.session.signals import resolve_series
from adas_sim.session.tick import Tick
from adas_sim.io.base import RunManifest
from adas_sim.ingest.map import AbsentPort, ProvidedPort

#: `CutFeasibility`'s real home is `graph/feasible.py` now (`WP-20` phase 5,
#: `IMP-0185`) -- imported above and re-exposed under this module's own
#: name so `from adas_sim.session.session import CutFeasibility` keeps
#: working for any existing caller.


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
    #: `S-C9`: the ingest map's declared `provides:`, keyed by the bare,
    #: pipeline-stage-agnostic `manifest_port` (`ProvidedPort.manifest_port`)
    #: -- what this *file* can supply, independent of what a particular
    #: pipeline calls its stage. `known_ports` above is the run-relative
    #: view (`self.<port>` resolution); this is the file-level view
    #: (`feasible_cuts`). Both are derived from the same ingest pass, never
    #: two separate mechanisms.
    provides: Mapping[str, ProvidedPort] = field(default_factory=dict)
    #: `S-C9`: declared-absent ports (`ProvidedPort`'s sibling, `AbsentPort`),
    #: keyed by port name -- named at load, never discovered as a tick-0
    #: failure (`R-SIM-23`'s own "a known hole declared is a startup answer").
    absent: Mapping[str, AbsentPort] = field(default_factory=dict)
    #: `S-C5`/`ST-C5-2`: this recording's own embedded config bundle, straight
    #: from `RecordingReader.config_bundle_bytes()` (`R-SIM-6`) -- `b""` when
    #: the recording predates bundle embedding or the codec never wrote one.
    #: A viewer resolves its `ProjectModel`'s `embedded` tier from this
    #: (`model.project.extract_embedded_bundle`), never by re-opening the file.
    config_bundle_bytes: bytes = b""

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
                where="adas_sim.session.session.Session.at", hint="",
            ) from None

    def signal(self, path: str, *, project: str = "base") -> tuple[tuple[int, object], ...]:
        """`path`'s value at every tick (`NR-SIM-8`, `sim_api_reference.md`
        §2.3) -- delegates to `core/signals.resolve_series`. No import cycle
        (unlike `open()`'s deferred import of `core/runner` below): that
        function takes `self.ticks`, never a `Session`, so `core/signals.py`
        never needs to import this module back."""
        return resolve_series(self.ticks, path, project=project)

    def feasible_cuts(self, pipeline: Pipeline) -> tuple[CutFeasibility, ...]:
        """`IMP-0185`, `MOVE` (`WP-20` phase 5): relocated to `graph/
        feasible.py::feasible_cuts`, re-typed onto plain `RecordingIndex`/
        `ModuleManifest` data instead of a live `Session`/`Pipeline`. Kept
        here as a thin wrapper -- builds the two from this `Session`'s own
        `provides`/`absent` fields and `pipeline`'s own stage manifests, so
        every existing caller (`sim doctor`, `test_c9_ingest.py`) is
        unaffected."""
        index = RecordingIndex(
            topics={
                port.manifest_port: RecordingTopic(proto_type=port.proto_type, origin=port.origin.value)
                for port in self.provides.values()
            },
            absent={port.port: port.reason for port in self.absent.values()},
        )
        stage_manifests = {
            stage.name: ModuleManifest(name=stage.name, outputs=pipeline.manifest_for(stage.name).outputs)
            for stage in pipeline.stages
        }
        return _feasible_cuts(index, stage_manifests)

    def has_simulated_output(self) -> bool:
        """`AR-57`: whether ANY port in this run ever carried
        an `origin="simulated"` value (`R-SIM-12`'s own origin tag) --
        true iff some `mode: simulate` stage genuinely executed and its
        output was captured, false for a purely stimulus-only recording
        (source/truth/mocked data alone, no stage ever ran against it).
        The **no-pipeline** answer to "can this file show me a component's
        own computed result" -- `feasible_cuts` above needs a `Pipeline`
        to name which stage; this needs nothing but the recording itself,
        because the origin tag is already carried per `PortValue` and this
        only asks whether any of them says so. No component name (`R-SIM-1`)
        -- a fact about this run's own tags, never what any one function
        would have computed."""
        return any(port.origin == "simulated" for tick in self.ticks for port in tick.ports.values())

    def seek_ns(self, t_ns: int) -> int:
        """The index of the tick whose `t_ns` is the greatest value `<=
        t_ns` (boundary-exact); clamps to tick 0 if `t_ns` precedes it."""
        if not self.ticks:
            raise AuthoringError(
                expected="a non-empty session", found="0 ticks",
                where="adas_sim.session.session.Session.seek_ns", hint="",
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
