# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`SI-11 graph` -- transitive coherence (`WP-20`), the package's own named
"one correctness defect": `graph/build.py::Pipeline.severed_chains()`
inspects exactly one hop upstream and one hop downstream of a `measured`
stage. A `simulate -> measured -> measured -> simulate` chain -- two
consecutive `measured` stages -- produces no finding there: the first
`measured` stage's own one-hop downstream scan only considers `simulate`
consumers, so it never notices the second `measured` stage; the second
`measured` stage's own one-hop upstream scan only considers `simulate`
producers, so it never notices the first. Both stages independently report
"nothing wrong" while a downstream `simulate` stage silently consumes
recorded (not live) data believing the chain to it is real (`R-SIM-10`).

This module replaces the one-hop scan with a transitive graph closure and a
three-outcome classification (`Verdict`, `SW-0176`) in place of
`severed_chains()`'s single yes/no:

- **`NORMAL`** -- every `simulate` stage's live output either feeds another
  `simulate` stage directly, or feeds nothing that matters.
- **`ORPHAN`** (warning, never blocks) -- a `simulate` stage's output feeds
  one or more `measured` stages, and NONE of them has a `simulate` stage
  transitively downstream. The upstream stage computes into nothing: wasted
  work, not corrupted data (`SW-0182`).
- **`BROKEN`** (blocks by default) -- a `simulate` stage's output feeds a
  `measured` stage that DOES have a `simulate` stage transitively
  downstream (through zero or more further `measured` stages). That
  downstream stage consumes the recording's bytes for that path, not the
  upstream stage's live computation, and has no way to know the difference
  (`SW-0178`).

Only `measured` stages act as the "gap" -- an `off` stage produces nothing
at all (excluded from `Pipeline`'s own exec/step results, `test_c1c_
pipeline.py::test_off_stage_is_absent_from_the_result_and_from_a_consumers_
inputs`), so there is no live computation to lose across it; `off` upstream
of a `measured` stage is the same "nothing computed into the gap" case
`severed_chains()`'s own docstring already names, and stays unflagged here
too."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from adas_sim.graph.build import Pipeline, Stage


class Verdict(StrEnum):
    """`SW-0176`: exactly three outcomes, no fourth, no unclassified state."""

    NORMAL = "normal"
    ORPHAN = "orphan"
    BROKEN = "broken"


@dataclass(frozen=True, slots=True)
class Finding:
    """One coherence issue. `stale` is every stage whose data provenance is
    in question (the `measured` gap stage(s) on the path, `ORPHAN` and
    `BROKEN` alike); `path` is the full ancestry from the computing
    `simulate` stage to `landing` (`BROKEN` only) in traversal order;
    `landing` is the downstream `simulate` stage where the corruption would
    actually be consumed -- `None` for `ORPHAN`, where nothing downstream
    consumes anything."""

    verdict: Verdict
    stale: tuple[str, ...]
    path: tuple[str, ...]
    landing: str | None = None


def _edges(stages: Sequence["Stage"]) -> dict[str, dict[str, str]]:
    """stage name -> {this stage's own input port name: producer stage
    name}, `"source"` references dropped -- stimulus has no upstream stage
    to be transitively stale from."""
    from adas_sim.graph.build import _split_ref

    result: dict[str, dict[str, str]] = {}
    for stage in stages:
        producers: dict[str, str] = {}
        for ref in stage.inputs.values():
            producer_name, _ = _split_ref(ref)
            if producer_name != "source":
                producers[producer_name] = producer_name
        result[stage.name] = producers
    return result


def ancestors(pipeline: "Pipeline", stage: str) -> frozenset[str]:
    """`SW-0174`: every stage `stage` transitively depends on, through any
    number of hops -- the one-hop -> closure fix `severed_chains()` itself
    needs (its upstream scan looks exactly one hop back)."""
    producers_by_stage = _edges(pipeline.stages)
    seen: set[str] = set()
    frontier = [stage]
    while frontier:
        current = frontier.pop()
        for producer in producers_by_stage.get(current, {}):
            if producer not in seen:
                seen.add(producer)
                frontier.append(producer)
    return frozenset(seen)


def descendants(pipeline: "Pipeline", stage: str) -> frozenset[str]:
    """`SW-0175`: every stage transitively fed (directly or indirectly) by
    `stage`'s output -- the downstream half of the same closure fix."""
    consumers_by_producer: dict[str, set[str]] = {}
    for consumer, producers in _edges(pipeline.stages).items():
        for producer in producers:
            consumers_by_producer.setdefault(producer, set()).add(consumer)
    seen: set[str] = set()
    frontier = [stage]
    while frontier:
        current = frontier.pop()
        for consumer in consumers_by_producer.get(current, ()):
            if consumer not in seen:
                seen.add(consumer)
                frontier.append(consumer)
    return frozenset(seen)


def _mode_by_name(pipeline: "Pipeline") -> dict[str, str]:
    return {s.name: s.mode for s in pipeline.stages}


def _immediate_consumers(pipeline: "Pipeline") -> dict[str, set[str]]:
    consumers: dict[str, set[str]] = {}
    for consumer, producers in _edges(pipeline.stages).items():
        for producer in producers:
            consumers.setdefault(producer, set()).add(consumer)
    return consumers


def _first_simulate_landings(
    start: str, *, mode_by_name: Mapping[str, str], consumers_by_producer: Mapping[str, set[str]],
) -> list[list[str]]:
    """BFS forward from `start` (a `measured` stage), returning one path
    per branch to the FIRST `simulate` stage reached on that branch --
    the walk does not continue past a live landing, since a stage beyond it
    is fed fresh input again and is a separate concern, not this finding's.
    Each returned path starts at `start` and ends at the landing stage."""
    landings: list[list[str]] = []
    frontier: list[list[str]] = [[start]]
    visited: set[str] = {start}
    while frontier:
        path = frontier.pop(0)
        current = path[-1]
        for consumer in sorted(consumers_by_producer.get(current, ())):
            if mode_by_name.get(consumer) == "simulate":
                landings.append(path + [consumer])
                continue
            if mode_by_name.get(consumer) != "measured" or consumer in visited:
                continue
            visited.add(consumer)
            frontier.append(path + [consumer])
    return landings


def classify(pipeline: "Pipeline") -> tuple[Finding, ...]:
    """`SW-0177`, `IMP-0177`: takes a `Pipeline` and nothing else -- no
    reader, no loader, no path -- so it is callable as a standalone check
    (`SW-0177`'s own Accept: no recording opened, no module loaded).

    For every `simulate` stage `U` with at least one immediate `measured`
    consumer `M`, walks forward from `M` through further `measured` stages
    only, stopping each branch at the first `simulate` stage reached (or at
    a dead end). A branch reaching a `simulate` stage is `BROKEN`
    (`SW-0178`); `M` with no branch reaching one is `ORPHAN` (`SW-0182`).
    Findings are returned in stage-declaration order, never raised -- the
    same "returned, not raised" contract `severed_chains()` already has;
    `graph/modes.py::with_mode` (`WP-20` phase 4) is what actually blocks."""
    mode_by_name = _mode_by_name(pipeline)
    consumers_by_producer = _immediate_consumers(pipeline)
    findings: list[Finding] = []

    for stage in pipeline.stages:
        if stage.mode != "simulate":
            continue
        gap_consumers = sorted(
            consumer for consumer in consumers_by_producer.get(stage.name, ())
            if mode_by_name.get(consumer) == "measured"
        )
        for gap_stage in gap_consumers:
            landings = _first_simulate_landings(
                gap_stage, mode_by_name=mode_by_name, consumers_by_producer=consumers_by_producer,
            )
            if not landings:
                findings.append(Finding(
                    verdict=Verdict.ORPHAN, stale=(gap_stage,), path=(stage.name, gap_stage),
                ))
                continue
            for landing_path in landings:
                stale = tuple(landing_path[:-1])  # every measured hop, excluding the live landing
                findings.append(Finding(
                    verdict=Verdict.BROKEN, stale=stale,
                    path=(stage.name, *landing_path), landing=landing_path[-1],
                ))
    return tuple(findings)


def render_finding(finding: Finding) -> str:
    """`SW-0178`, `IMP-0178`: human-readable text naming the path and the
    landing point -- what `graph/modes.py::with_mode` (phase 4) actually
    blocks a run with."""
    path_text = " -> ".join(finding.path)
    if finding.verdict is Verdict.BROKEN:
        return (
            f"broken chain: {path_text} -- stage(s) {', '.join(finding.stale)} inject recorded data "
            f"while '{finding.landing}' consumes it believing the chain to it is live"
        )
    return (
        f"orphan simulation: {path_text} -- stage(s) {', '.join(finding.stale)} compute live output "
        f"that nothing downstream consumes"
    )


@dataclass(frozen=True, slots=True)
class Remedy:
    """One way to resolve a `Finding`. `promote` names every stage that
    would flip to `mode: simulate` -- applying a remedy is
    `graph/modes.py::with_mode` (`WP-20` phase 4) called once per name in
    `promote`. `suggested` marks the smallest correct change; a `BROKEN`
    finding has exactly one remedy today (promote every stale stage), which
    IS the minimal fix (`SW-0179`'s own Shall: "one remedy shall promote
    every affected module ... while printing exactly what changed") -- a
    second remedy (waive with a written reason, `graph/waiver.py`, `WP-20`
    phase 3) is added once that module lands."""

    description: str
    suggested: bool
    promote: tuple[str, ...]


def remedies(finding: Finding) -> tuple[Remedy, ...]:
    """`SW-0179`, `IMP-0179`: smallest change first. An `ORPHAN` finding
    has no remedy -- it never blocks (`SW-0182`), so nothing needs fixing;
    a `BROKEN` finding's one remedy promotes every stale (`measured`) stage
    on the path back to `simulate`, closing the gap exactly as
    `Pipeline.with_mode(close_gaps=True)` already does for the one-hop
    case (`R-SIM-10`)."""
    if finding.verdict is not Verdict.BROKEN:
        return ()
    return (
        Remedy(
            description=f"promote {', '.join(finding.stale)} to mode: simulate",
            suggested=True,
            promote=finding.stale,
        ),
    )
