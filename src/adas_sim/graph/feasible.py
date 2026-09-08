# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`SI-11 graph` -- `feasible_cuts` (`WP-20` phase 5, `IMP-0185`/`IMP-0411`),
relocated and re-typed from `session/session.py::Session.feasible_cuts`.
`Session.feasible_cuts` becomes a thin wrapper that builds a `RecordingIndex`
from its own `provides`/`absent` fields and a `ModuleManifest` per stage from
`pipeline.manifest_for(...).outputs`, then delegates here -- existing
callers (`sim doctor`, `test_c9_ingest.py`) keep working unchanged, still
calling `Session.feasible_cuts(pipeline)`.

**`RecordingIndex`/`ModuleManifest` (`IMP-0411`) are the consumer-side
shape only.** Their fields are exactly `SW-0410`'s own declared Shall
clause (a `RecordingIndex` per named recording, a `ModuleManifest` per
named module) -- implementing what is already specified, not inventing
`WP-21`'s content. `WP-21`'s own `IMP-0410` is the real *producer*: reading
an actual recording/library and populating these from it. Until that
lands, both types are built by hand -- `Session.feasible_cuts`'s own
`provides`/`absent` fields today, or a test's own literal instances
(`UT-GRF-27`'s `F-INDEX`: "a hand-written index and manifest set ... no
file on disk and no library present")."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.resolve.component import PortSpec


@dataclass(frozen=True, slots=True)
class RecordingTopic:
    """One topic's declared facts (`SW-0410`'s own field list). Only
    `proto_type` and `origin` are consumed by `feasible_cuts` today --
    `message_count`/the two timestamps/`highest_rung` exist because
    `SW-0410` declares them as part of the index's shape, for whichever
    future consumer (`sim probe`, a volume estimate) needs them; they
    default to "unknown" values rather than a guessed number (`NR-SIM-4`)."""

    proto_type: str
    message_count: int = 0
    first_timestamp_ns: int | None = None
    last_timestamp_ns: int | None = None
    highest_rung: int = 0
    origin: str = ""


@dataclass(frozen=True, slots=True)
class RecordingIndex:
    """Per-topic facts for one recording, plain data -- no open file
    handle, no reader (`SW-0177`'s "computable with nothing opened"
    discipline, applied here to feasibility rather than coherence).
    `absent` is `R-SIM-23`'s own declared-hole vocabulary (port name ->
    the reason this family never carries it) -- a hole DECLARED here
    produces a named reason in `feasible_cuts`' own `missing` text; a port
    in neither `topics` nor `absent` gets a generic one (`UT-C9-2`'s own
    two-reason distinction, preserved from `Session.provides`/`Session.
    absent`, this type's own predecessor shape)."""

    topics: Mapping[str, RecordingTopic] = field(default_factory=dict)
    absent: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ModuleManifest:
    """One stage's declared output ports -- deliberately narrower than
    `resolve.component.ComponentManifest` (no version/build_id/
    descriptor_set/period_ns): those come from a loaded library, and
    `feasible_cuts` never loads one (`SW-0177`-style purity). A real
    `ComponentManifest.outputs` already has this shape; `ModuleManifest`
    is what a HAND-WRITTEN test case builds without one (`UT-GRF-27`)."""

    name: str
    outputs: tuple[PortSpec, ...] = ()


@dataclass(frozen=True, slots=True)
class CutFeasibility:
    """One pipeline stage's answer to "can this recording drive it as
    `mode: measured`" (`R-SIM-23`, `CR-SIM-21` made mechanical) -- a query,
    never a load-time assertion (`graph/pipeline.py::_validate_wiring` is
    that). Relocated verbatim from `session/session.py`, `Session`'s own
    former home for this type -- moving here avoids a circular import
    (`Session` now depends on `graph.feasible`, not the reverse)."""

    stage: str
    feasible: bool
    #: One entry per missing/mismatched output port, human-readable and
    #: naming the port -- `()` when `feasible` is `True`.
    missing: tuple[str, ...] = ()

    def __repr__(self) -> str:
        return f"<CutFeasibility stage={self.stage!r} feasible={self.feasible}>"


def feasible_cuts(index: RecordingIndex, stage_manifests: Mapping[str, ModuleManifest]) -> tuple[CutFeasibility, ...]:
    """`IMP-0185`, `MOVE`: per stage in `stage_manifests` (iterated in the
    mapping's own order), whether `index` carries every declared output
    port with a matching `proto_type` (`UT-C9-3`: a mismatch is refused,
    never coerced), each miss naming the port and why (missing entirely, or
    a declared-absent reason if `index` carries one -- `UT-C9-2`)."""
    results: list[CutFeasibility] = []
    for stage_name, manifest in stage_manifests.items():
        missing: list[str] = []
        for spec in manifest.outputs:
            entry = index.topics.get(spec.name)
            if entry is None:
                reason = index.absent.get(spec.name, "not provided by this recording")
                missing.append(f"{spec.name}: {reason}")
            elif entry.proto_type != spec.proto_type:
                missing.append(
                    f"{spec.name}: recording provides {entry.proto_type!r}, "
                    f"pipeline expects {spec.proto_type!r}"
                )
        results.append(CutFeasibility(stage=stage_name, feasible=not missing, missing=tuple(missing)))
    return tuple(results)


def check_measured_supported(stage_name: str, outputs: Iterable[PortSpec], recording_topics: Iterable[str]) -> None:
    """`IMP-0111`, `MOVE`: relocated from `graph/pipeline.py::_validate_wiring`'s
    own inline `mode: measured` check -- a `measured` stage's declared
    output topics must all be present in the recording, refused at load
    naming every missing one. Load-time (`AuthoringError`, blocking), unlike
    `feasible_cuts` above, which is a query computed before a mode choice is
    even made (`R-SIM-23`'s "declared before the run, not discovered by
    failing one")."""
    topics = set(recording_topics)
    missing = [spec.name for spec in outputs if spec.name not in topics]
    if missing:
        raise AuthoringError(
            expected=f"the recording to contain stage '{stage_name}''s output topics",
            found=f"missing: {', '.join(missing)}", where=f"stage '{stage_name}' (mode: measured)",
            hint="record this stage's outputs, or set mode: simulate or off",
        )
