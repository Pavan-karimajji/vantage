# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`SI-22 launcher` -- `cuts_for_recording` (`WP-28`, `IMP-0345`): per
recording, which stages could be set `mode: measured` given what that file
actually carries. A second caller of `graph.feasible.feasible_cuts`
(`WP-20` phase 5) alongside `Session.feasible_cuts` (`sim doctor`) --
never a second implementation (`R-SIM-23`'s own closed-vocabulary
discipline extends to callers, not only to the ingest map).

Takes a `RecordingIndex` the caller already has, same as `feasible_cuts`
itself -- a caller may build one by hand (`UT-GRF-27`'s own `F-INDEX`
fixture) or read a real file into one (`resolve.probe.describe_recording`).

**The two build it with different keys, and this module is where they
meet** (found live 2026-08-28, driving the POC demo through this API):
`feasible_cuts` looks a stage's declared output up by its **bare** port
name (`"fn.out"`) -- that is what every one of its own tests pins, and what
`Session.feasible_cuts` supplies via `manifest_port` -- while
`describe_recording` keys by the recording's **topic**
(`"/stage/fn.out"`). Each side is correct and separately tested; nothing
tested the join, so a real recording produced *every* cut infeasible,
silently, including the one that had just run for 100 ticks. `_bare_keyed`
below is the translation, and it is done per stage so a topic is only ever
matched against the stage that actually produced it."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from adas_sim.graph.feasible import CutFeasibility, ModuleManifest, RecordingIndex, feasible_cuts

if TYPE_CHECKING:
    from adas_sim.launcher.model import Selection


def _bare_keyed(index: RecordingIndex, stage: str) -> RecordingIndex:
    """`index` restricted to the topics `stage` produced, re-keyed by the
    bare port name `feasible_cuts` matches on.

    A topic is canonically `"/<producer>/<port>"` (`io::CanonicalTopic`'s
    own spelling, which the readers now normalise to), so the port is
    everything after the producer segment -- and the producer segment must
    equal `stage`, which is what keeps two stages that both declare
    `outputs` from matching each other's topic.

    An index that is ALREADY bare-keyed (hand-built, `F-INDEX`-shaped, or
    `Session.feasible_cuts`') passes through untouched: no key starts with
    `"/<stage>/"`, so the restricted view is empty and the original is
    returned. That is what keeps `UT-LNC-04`'s existing hand-built fixtures
    meaningful rather than silently emptied by this translation."""
    prefix = f"/{stage}/"
    bare = {
        topic[len(prefix):]: entry
        for topic, entry in index.topics.items()
        if topic.startswith(prefix)
    }
    if not bare:
        return index
    return RecordingIndex(topics=bare, absent=index.absent)


def cuts_for_recording(selection: "Selection", index: RecordingIndex) -> tuple[CutFeasibility, ...]:
    """`IMP-0345`: every stage in `selection.working_pipeline`, computed
    with nothing opened beyond `index` -- a stage that never resolved a
    component (no `manifest_for`, e.g. an unset `stub:`) is skipped, since
    it has no declared outputs to check `measured` against.

    `feasible_cuts` is called once PER STAGE, against that stage's own
    bare-keyed view (`_bare_keyed`), rather than once with every stage's
    manifests against one shared index. Same function, same answers, but a
    topic can no longer satisfy a different stage's identically-named port
    -- an ambiguity the bare-key contract cannot express on its own."""
    pipeline = selection.working_pipeline
    results: list[CutFeasibility] = []
    for stage in pipeline.stages:
        try:
            manifest = pipeline.manifest_for(stage.name)
        except KeyError:
            continue
        results.extend(feasible_cuts(
            _bare_keyed(index, stage.name),
            {stage.name: ModuleManifest(name=stage.name, outputs=manifest.outputs)},
        ))
    return tuple(results)


def cuts_for_all(
    selection: "Selection", indices: Mapping[Path, RecordingIndex],
) -> dict[Path, tuple[CutFeasibility, ...]]:
    """`IMP-0345`'s "per recording" plural: one `cuts_for_recording` call
    per entry in `indices` -- `selection.recordings` is the launcher's own
    candidate list (`SW-0346`), `indices` is the caller-supplied index for
    each (same purity as the singular form above)."""
    return {path: cuts_for_recording(selection, index) for path, index in indices.items()}
