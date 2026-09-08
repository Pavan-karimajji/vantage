# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`SI-22 launcher` -- `Selection` (`WP-28`, `IMP-0341`/`IMP-0346`): the
launcher's one piece of state, held entirely in memory and turned into a
file by `launcher/write.py::to_run_config` -- never executed directly
(`CN-0175`, `IMP-0343`'s own "no code path from `Selection` to a run").

**Mode and implementation are independent, explicit selections** (`SW-0341`):
`mode_overrides`/`impl_overrides` are two separate mappings, so setting one
never discards the other -- the same guarantee `player/panels/
pipeline_panel.py::PipelinePanelState` already gives mode toggles alone
(`UT-D3-1`), extended here to cover `impl:` too, which that panel's own
docstring explicitly left read-only pending this work.

**No gate here.** `set_mode`/`set_impl` accept any declared stage and any
value -- "every combination expressible in configuration is reachable, and
nothing is reachable that is not" (`SW-0341`'s own `Accept`). Blocking on a
broken chain is `launcher/classify.py`'s job, run *after* a selection change,
never smuggled into the setter itself."""

from __future__ import annotations

import warnings
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

from adas_sim.graph.pipeline import Mode, Pipeline
from adas_sim.resolve.component import SilComponent
from adas_sim.runspec.manifest import load_run_spec
from adas_sim.diagnostics.errors import AuthoringError, ProvenanceWarning

#: `WP-03`: a group's computed third state (`SW-0018`) -- disagreeing
#: members, never assignable directly (`Selection.group_state` only ever
#: derives it, and no setter exists that could return it a different way).
GroupState = Mode | Literal["mixed"]


def _stage_names(pipeline: Pipeline) -> frozenset[str]:
    return frozenset(s.name for s in pipeline.stages)


def _require_stage(pipeline: Pipeline, stage: str, *, where: str) -> None:
    names = _stage_names(pipeline)
    if stage not in names:
        raise AuthoringError(
            expected="a declared stage name", found=stage, where=where,
            hint=f"declared stages: {', '.join(sorted(names))}",
        )


def _with_impl(pipeline: Pipeline, stage: str, impl: str) -> Pipeline:
    """Same technique `graph/modes.py::with_mode`/`with_port_mode` already
    use to return a new `Pipeline` with one field of one `Stage` changed --
    `impl:` has no dedicated method there because nothing before this
    package let a caller choose it (`pipeline_panel.py`'s own "narrowed"
    note). `coherence.classify`/`feasible_cuts` read only `mode`/`inputs`,
    never `impl`, so reusing the base pipeline's already-resolved
    `_components` here is safe for both -- `manifest_for` would still
    answer with the OLD impl's manifest, a known, narrow gap matching
    `IMP-0205`/`WP-21`'s own not-yet-built re-resolution."""
    new_stages = tuple(
        replace(s, impl=impl) if s.name == stage else s
        for s in pipeline.stages
    )
    return Pipeline(
        name=pipeline.name, stages=new_stages, version=pipeline.version, components=pipeline._components,
        faults=pipeline._faults, library_paths=pipeline.library_paths,
    )


@dataclass(frozen=True, slots=True)
class Selection:
    """One launcher session's state. `base_pipeline` is the pipeline as
    loaded from disk, never mutated in place -- every setter returns a NEW
    `Selection` (`CN-0325`'s undoability, applied to the launcher's own
    state rather than `Pipeline` alone). `search` is forwarded to
    `launcher/availability.py`, the same `search:` a real `Pipeline.load`
    would need for `dll:`/`stubdll:` stages (`resolve_library`)."""

    base_pipeline: Pipeline
    mode_overrides: Mapping[str, Mode] = field(default_factory=dict)
    impl_overrides: Mapping[str, str] = field(default_factory=dict)
    #: Candidates offered to the user (`SW-0346`'s "adding recordings") --
    #: which ONE actually drives a run is `selected_recording` below.
    recordings: tuple[Path, ...] = ()
    selected_recording: Path | None = None
    #: Display-only (`SW-0346`'s "select a layout"). Deliberately never
    #: written by `to_run_config` (`SW-0347`'s "no launcher-only fields") --
    #: no headless reader consumes a `layout:` key today, and layout/session
    #: itself moved to `viz` (`WP-25`/`WP-26`, `SYNC:SM-01`/`SM-04`).
    layout: str | None = None
    project: str = "base"
    config: Path | None = None
    search: tuple[Path, ...] = ()

    @classmethod
    def from_spec(
        cls, path: Path, *, search: tuple[Path, ...] = (),
        components: Mapping[str, SilComponent] | None = None,
    ) -> Selection:
        """`SW-0019`/`IMP-0020`: the file-and-memory convergence point --
        reloads `path` exactly as `write.py::launch` does (`Pipeline.load`,
        never trusting a caller's own stale in-memory state) plus the
        top-level `recording:`/`project:`/`config:` keys `runspec.manifest.
        load_run_spec` already reads. Every stage's mode/impl/inputs is
        already baked into the loaded `Pipeline`, so this returns a
        `Selection` with EMPTY `mode_overrides`/`impl_overrides` --
        overriding an already-resolved value would be a second source of
        truth, never a third state to reconcile."""
        pipeline = Pipeline.load(path, search=search, components=components)
        spec = load_run_spec(path)
        return cls(
            base_pipeline=pipeline, project=spec.project,
            recordings=(spec.recording,) if spec.recording is not None else (),
            selected_recording=spec.recording, config=spec.config, search=search,
        )

    @property
    def working_pipeline(self) -> Pipeline:
        """The `Pipeline` `launcher/classify.py` and `launcher/cuts.py`
        classify/query against -- every override applied, gap-closing left
        OFF (`close_gaps=False`) so a mode change never silently moves a
        second stage: closing a gap is a REMEDY the user chooses via
        `classify.py`, not a side effect of selecting one module."""
        pipeline = self.base_pipeline
        with warnings.catch_warnings():
            #: `classify.py` re-runs `coherence.classify()` on the result and
            #: reports findings through its own return value -- the Python
            #: warning `with_mode(close_gaps=False)` raises for the same
            #: fact would only be a duplicate here.
            warnings.simplefilter("ignore", ProvenanceWarning)
            for stage, mode in self.mode_overrides.items():
                pipeline = pipeline.with_mode(stage, mode, close_gaps=False)
        for stage, impl in self.impl_overrides.items():
            pipeline = _with_impl(pipeline, stage, impl)
        return pipeline

    def set_mode(self, stage: str, mode: Mode) -> Selection:
        _require_stage(self.base_pipeline, stage, where="launcher.model.Selection.set_mode")
        return replace(self, mode_overrides={**self.mode_overrides, stage: mode})

    def isolate(self, stage: str) -> Selection:
        """`SW-0017`: one operation setting `stage` to execute (`simulate`)
        and every other declared stage to replay (`measured`) -- the whole
        `mode_overrides` mapping is replaced in one step, so no stage keeps
        a stale mode from before the call, and no other field changes."""
        _require_stage(self.base_pipeline, stage, where="launcher.model.Selection.isolate")
        modes: dict[str, Mode] = {
            s.name: ("simulate" if s.name == stage else "measured") for s in self.base_pipeline.stages
        }
        return replace(self, mode_overrides=modes)

    def group_state(self, stages: Collection[str]) -> GroupState:
        """`SW-0018`: `stages`' shared mode, or `"mixed"` when they
        disagree -- read-only by construction, since this only ever
        computes from `working_pipeline`; the sole way to move it is
        `set_mode`/`isolate` on an individual member."""
        pipeline = self.working_pipeline
        modes = {stage.mode for stage in pipeline.stages if stage.name in stages}
        if len(modes) == 1:
            return next(iter(modes))
        return "mixed"

    def set_impl(self, stage: str, impl: str) -> Selection:
        _require_stage(self.base_pipeline, stage, where="launcher.model.Selection.set_impl")
        return replace(self, impl_overrides={**self.impl_overrides, stage: impl})

    def add_recording(self, path: Path) -> Selection:
        if path in self.recordings:
            return self
        return replace(self, recordings=(*self.recordings, path))

    def select_recording(self, path: Path) -> Selection:
        if path not in self.recordings:
            raise ValueError(f"{path} was never added -- call add_recording first")
        return replace(self, selected_recording=path)

    def set_layout(self, name: str) -> Selection:
        return replace(self, layout=name)


@dataclass(frozen=True, slots=True)
class GroupControlView:
    """`IMP-0021` (`SW-0020`): what a group control renders -- pure state,
    no pixels (`player/panels/pipeline_panel.py::StageView`'s own
    discipline). `selectable` is `False` exactly when `state == "mixed"` --
    there is no enabled variant for that value, so a caller cannot build a
    view that offers input against a state nothing can be assigned to."""

    state: GroupState
    selectable: bool


def group_control_view(selection: Selection, stages: Collection[str]) -> GroupControlView:
    """`SW-0020`: renders `Selection.group_state` as a control state -- the
    one place `"mixed"` becomes `selectable=False`, so every caller sees
    the same rule rather than re-deriving it per widget."""
    state = selection.group_state(stages)
    return GroupControlView(state=state, selectable=state != "mixed")
