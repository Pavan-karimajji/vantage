# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`SI-11 graph` -- `with_mode` (`WP-20` phase 4, `IMP-0183`/`IMP-0184`),
relocated from `graph/pipeline.py::Pipeline.with_mode`. `Pipeline.with_mode`
stays as a thin wrapper (nothing calling the method breaks). The one real
behaviour change this move makes: gap-closing now runs on
`coherence.classify()` (`WP-20` phase 2's transitive fix) instead of the
one-hop `Pipeline.severed_chains()` -- so toggling a mode on
`simulate -> measured -> measured -> simulate` now actually closes the
whole chain, not just the one-hop case `severed_chains()` could see.

`with_port_mode` (`IMP-0400`) is new: a per-port override on top of a
stage's own mode, scoped narrowly to what `UT-GRF-25` asks (override one
output port, visible in the manifest and in classification) -- `OQ-04`
("whether stage-level staging plus per-port override is sufficient
granularity") stays open; this is not a general redesign of `Stage`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from warnings import warn

from adas_sim.diagnostics.errors import AuthoringError, ProvenanceWarning
from adas_sim.graph import coherence

if TYPE_CHECKING:
    from adas_sim.graph.pipeline import Mode, Pipeline


def with_mode(pipeline: "Pipeline", stage: str, mode: "Mode", *, close_gaps: bool = True) -> "Pipeline":
    """`IMP-0183`/`IMP-0184`: returns a NEW pipeline; `impl:`/`inputs:` are
    retained on the changed stage so the toggle is reversible (`R-SIM-10`).
    With `close_gaps` (default), every stage `coherence.classify()` finds
    `BROKEN` because of this change -- transitively, not just one hop -- is
    closed by flipping its `stale` members to `simulate` too, undoably
    (the caller keeps the old object).

    `close_gaps=False` forces the gap open deliberately -- never silent:
    exactly ONE `ProvenanceWarning` names every stage `close_gaps=True`
    would have flipped, badged *"computed, not consumed"* wherever a GUI
    renders it. The run itself is never blocked here -- this is a warning a
    headless caller sees in the log, not an error (`SW-0178`'s actual
    blocking behaviour is a future run-loop caller's job, see `graph/
    coherence.py`'s own top note)."""
    from adas_sim.graph.pipeline import Pipeline, Stage

    names = {s.name for s in pipeline.stages}
    if stage not in names:
        raise AuthoringError(
            expected="a declared stage name", found=stage, where="graph.modes.with_mode",
            hint=f"declared stages: {', '.join(names)}",
        )
    new_stages = tuple(
        Stage(name=s.name, mode=mode, impl=s.impl, inputs=s.inputs, overrides=s.overrides, record=s.record)
        if s.name == stage else s
        for s in pipeline.stages
    )
    result = Pipeline(
        name=pipeline.name, stages=new_stages, version=pipeline.version, components=pipeline._components,
        faults=pipeline._faults, library_paths=pipeline.library_paths, bundle_dirs=pipeline.bundle_dirs,
    )
    to_close: set[str] = set()
    for finding in coherence.classify(result):
        if finding.verdict is coherence.Verdict.BROKEN and stage in finding.path:
            to_close.update(finding.stale)
    if not to_close:
        return result
    if not close_gaps:
        warn(ProvenanceWarning(
            f"stage(s) {', '.join(sorted(to_close))} computed, not consumed -- "
            f"setting '{stage}' to {mode!r} severed the chain to it and close_gaps=False left the gap open"
        ))
        return result
    closed_stages = tuple(
        Stage(name=s.name, mode="simulate", impl=s.impl, inputs=s.inputs, overrides=s.overrides, record=s.record)
        if s.name in to_close else s
        for s in new_stages
    )
    return Pipeline(
        name=pipeline.name, stages=closed_stages, version=pipeline.version, components=pipeline._components,
        library_paths=pipeline.library_paths, bundle_dirs=pipeline.bundle_dirs,
    )


def with_port_mode(pipeline: "Pipeline", stage: str, port: str, mode: "Mode") -> "Pipeline":
    """`IMP-0400`, `SW-0400`: overrides mode on ONE of `stage`'s declared
    OUTPUT ports rather than the whole stage -- `UT-GRF-25`'s own scope
    ("override mode on one output port; read it in the manifest and in the
    classification"). Stored on `Stage.port_modes` (a new, optional
    mapping, default empty so every existing pipeline is unaffected);
    `coherence.classify()` treats a port with an override as if its OWNING
    stage were in `mode` for the purpose of that one port's edges only --
    scoped this narrowly on purpose (`OQ-04` stays open on whether
    stage-level plus per-port is the right final granularity)."""
    from adas_sim.graph.pipeline import Pipeline, Stage

    names = {s.name for s in pipeline.stages}
    if stage not in names:
        raise AuthoringError(
            expected="a declared stage name", found=stage, where="graph.modes.with_port_mode",
            hint=f"declared stages: {', '.join(names)}",
        )
    new_stages = tuple(
        Stage(
            name=s.name, mode=s.mode, impl=s.impl, inputs=s.inputs, overrides=s.overrides, record=s.record,
            port_modes={**s.port_modes, port: mode},
        )
        if s.name == stage else s
        for s in pipeline.stages
    )
    return Pipeline(
        name=pipeline.name, stages=new_stages, version=pipeline.version, components=pipeline._components,
        faults=pipeline._faults, library_paths=pipeline.library_paths, bundle_dirs=pipeline.bundle_dirs,
    )
