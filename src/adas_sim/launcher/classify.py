# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`SI-22 launcher` -- `classify` (`WP-28`, `IMP-0342`): runs
`graph.coherence.classify()` (`WP-20`'s transitive fix, `IMP-0176`/
`IMP-0177`) against a `Pipeline` and reports which `BROKEN` findings remain
unresolved after any granted `graph.waiver.Waiver`s, offering the SAME two
remedies the graph package itself provides -- `coherence.remedies()`
(promote every stale stage, the one structural remedy `WP-20` phase 2
landed) and `waiver.waive()` (waive with a written reason, `WP-20` phase 3).
No third remedy is invented here: `graph/waiver.py`'s own top note names
this launcher as "whichever `WP` first makes coherence classification part
of an actual run" -- the module that finally wires the waiver mark in, not
a place to grow a new kind of fix.

Takes a `Pipeline`, never a `Selection` -- callable both from
`launcher/model.py::Selection.working_pipeline` (a selection in progress)
and from `launcher/write.py::launch` (a pipeline reloaded from a written
file), so the two call sites can never classify differently by construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from adas_sim.diagnostics.errors import EXIT_CODES
from adas_sim.graph import coherence, waiver

if TYPE_CHECKING:
    from adas_sim.graph.pipeline import Pipeline


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    """`SW-0342`'s own selection-time answer. `findings` is every
    `coherence.classify()` result, in declaration order, unfiltered -- an
    `ORPHAN` never blocks (`SW-0182`) so it never appears in `blocking`.
    `can_launch` is exactly `not blocking` -- the single fact `launcher/
    write.py::launch` (and a future "Launch" button) reads."""

    findings: tuple[coherence.Finding, ...]
    blocking: tuple[coherence.Finding, ...]
    can_launch: bool


def classify(pipeline: "Pipeline", waivers: tuple[waiver.Waiver, ...] = ()) -> ClassificationResult:
    """`IMP-0342`: classify `pipeline`, then subtract every `BROKEN` finding
    a granted waiver already covers (`waiver.still_blocking`). Called again
    on every selection change (`SW-0342`'s own `Shall`) -- cheap and
    side-effect-free, same purity `coherence.classify` itself guarantees
    (`SW-0177`)."""
    findings = coherence.classify(pipeline)
    blocking = waiver.still_blocking(findings, waivers)
    return ClassificationResult(findings=findings, blocking=blocking, can_launch=not blocking)


def remedies_for(finding: coherence.Finding) -> tuple[coherence.Remedy, ...]:
    """`IMP-0342`: the remedies offered inline for one finding -- a thin
    pass-through to `coherence.remedies`, kept here so a caller reaches
    both classification and remedies through one module."""
    return coherence.remedies(finding)


class LaunchBlocked(Exception):
    """`SW-0342`'s block, raised by `launcher/write.py::launch` (never by
    `classify` itself, which only reports) when a `ClassificationResult`
    still has a `blocking` finding after every granted waiver. Carries the
    situational `coherence` exit code the same way `graph.waiver.
    WaiverForbidden` does -- a specific call site's own decision, not a
    derived `SimError.kind` default (`diagnostics/errors.py`'s own note)."""

    exit_code = EXIT_CODES["coherence"]

    def __init__(self, blocking: tuple[coherence.Finding, ...]) -> None:
        self.blocking = blocking
        text = "; ".join(coherence.render_finding(f) for f in blocking)
        super().__init__(f"launch blocked -- {text}")
