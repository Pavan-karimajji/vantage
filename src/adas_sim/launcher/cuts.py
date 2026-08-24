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
itself -- `IMP-0410`/`WP-21`'s real *producer* (reading an actual file into
one) does not exist yet, so a caller today builds one by hand, exactly as
`UT-GRF-27`'s own `F-INDEX` fixture does."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from adas_sim.graph.feasible import CutFeasibility, ModuleManifest, RecordingIndex, feasible_cuts

if TYPE_CHECKING:
    from adas_sim.launcher.model import Selection


def cuts_for_recording(selection: "Selection", index: RecordingIndex) -> tuple[CutFeasibility, ...]:
    """`IMP-0345`: every stage in `selection.working_pipeline`, computed
    with nothing opened beyond `index` -- a stage that never resolved a
    component (no `manifest_for`, e.g. an unset `stub:`) is skipped, since
    it has no declared outputs to check `measured` against."""
    pipeline = selection.working_pipeline
    manifests: dict[str, ModuleManifest] = {}
    for stage in pipeline.stages:
        try:
            manifest = pipeline.manifest_for(stage.name)
        except KeyError:
            continue
        manifests[stage.name] = ModuleManifest(name=stage.name, outputs=manifest.outputs)
    return feasible_cuts(index, manifests)


def cuts_for_all(
    selection: "Selection", indices: Mapping[Path, RecordingIndex],
) -> dict[Path, tuple[CutFeasibility, ...]]:
    """`IMP-0345`'s "per recording" plural: one `cuts_for_recording` call
    per entry in `indices` -- `selection.recordings` is the launcher's own
    candidate list (`SW-0346`), `indices` is the caller-supplied index for
    each (same purity as the singular form above)."""
    return {path: cuts_for_recording(selection, index) for path, index in indices.items()}
