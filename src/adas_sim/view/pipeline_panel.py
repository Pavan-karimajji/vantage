# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`PipelinePanelState` -- pipeline-panel state (S-D3 slice 1,
`sim_visualization_spec.md` §13): a direct rendering of a loaded
`Pipeline`'s `mode:`/`impl:` fields against a run's `known_ports`, so
`measured` is offered only when the recording actually carries that
stage's declared outputs. Pure state, no pixels, no Qt -- `view/` stays
headless-testable, the same discipline `view/layers.py`'s own
`LayerTreeState` already follows.

**Discovery, not registration** (`R-VAR-2`): stages come from the
`Pipeline` the caller already loaded, never a roster this module owns.
This is also why the module names no component or function (`GT-1`) --
every stage name, mode and impl string is read from the `Pipeline`
argument, not written here.

**Severed-chain auto-close, undoably (`UT-D3-3`, S-D3 slice 5).**
`set_mode` never reimplements `R-SIM-10`'s auto-close/orphan logic -- it
delegates every toggle to `Pipeline.with_mode` (`S-C1cΔ`/`S-D6`, already
built and tested) and keeps the returned `Pipeline` as `_working`, the
panel's own live copy. `mode_overrides` (still read by
`core.manifest.write_run_manifest`) is now a DIFF between `_working` and
the original `_pipeline`, so an auto-flipped intervening stage lands in
the run manifest exactly like an explicit toggle -- there is no second
bookkeeping dict to drift from what `with_mode` actually decided.
`undo_last_auto_close` is the panel's one-line undo bar: it re-applies the
same toggle with `close_gaps=False`, forcing the gap back open and
leaving the intervening stage's `StageView.orphan` badge set.

**Narrowed vs §13, this pass.** `impl:` is read-only: the spec's dropdown
of alternative implementations needs a directory scan of on-disk component
manifests that does not exist anywhere in this framework yet (`sim list
ports <lib>` reads one manifest given an explicit path; nothing discovers
candidates). Also not built here: per-port override expansion,
compare-against-recorded, and the manifest round-trip is `UT-D3-4`/
`UT-D3-5`/`UT-D3-6` (already landed, slice 2). What this pass proves:
discovery-driven rendering and a mode toggle that never discards `impl`
(`UT-D3-1` partial, `UT-D3-2`, `UT-D3-7`), plus the severed-chain flag/undo
bar (`UT-D3-3`).
"""

from __future__ import annotations

import warnings
from collections.abc import Collection
from dataclasses import dataclass

from adas_sim.contracts.pipeline import Pipeline, SeveredChain, Stage

_VALID_MODES = ("simulate", "measured", "off")


@dataclass(frozen=True, slots=True)
class StageView:
    """What the panel needs to render one row -- `mode` is the CURRENT
    displayed mode (the stage's own declared mode, or a user override from
    `PipelinePanelState.set_mode`), never conflated with the two. `orphan`
    is `True` exactly when this stage is the `measured` member of a
    currently-open severed chain (`R-SIM-10`) -- the panel's cue to render
    the *"computed, not consumed"* badge."""

    name: str
    mode: str
    impl: str | None
    measured_available: bool
    measured_unavailable_reason: str  # "" exactly when measured_available
    orphan: bool = False


class PipelinePanelState:
    """One instance per (pipeline, recording) pairing -- mirrors
    `LayerTreeState`'s own "one instance per (project, pipeline)" scope.
    `known_ports` is the run-relative port universe (`Session.known_ports`'s
    own shape: qualified `<stage>.<port>` names), computed once by the
    caller -- this class never re-derives it and never opens a recording
    itself."""

    def __init__(self, pipeline: Pipeline, known_ports: Collection[str]) -> None:
        self._pipeline = pipeline  # ORIGINAL, never mutated -- mode_overrides' baseline
        self._working = pipeline  # this session's live copy -- every set_mode/undo replaces it wholesale
        self._known_ports = frozenset(known_ports)
        #: The most recent toggle, and the working pipeline just before it
        #: applied -- `undo_last_auto_close`'s only state, cleared (both to
        #: `None`/`()`) whenever a fresh toggle supersedes it. A one-line
        #: undo bar offers exactly the latest toggle, same UX as any toast.
        self._pre_toggle: Pipeline | None = None
        self._last_toggle: tuple[str, str] | None = None
        self._last_auto_closed: tuple[str, ...] = ()

    def stages(self) -> tuple[StageView, ...]:
        orphan_stages = {chain.measured for chain in self._working.severed_chains()}
        return tuple(self._view(stage, orphan=stage.name in orphan_stages) for stage in self._working.stages)

    @property
    def pipeline(self) -> Pipeline:
        """The underlying `Pipeline`, unchanged -- `core.manifest.
        write_run_manifest`'s `pipeline=` argument (stage/impl/inputs come
        from here; only `mode` may differ, via `mode_overrides` below)."""
        return self._pipeline

    @property
    def mode_overrides(self) -> dict[str, str]:
        """Every stage whose mode now differs from the pipeline as loaded --
        a snapshot (mutating the returned dict does not affect this state).
        Diffed against `_working`, not a separately-maintained dict, so an
        auto-closed intervening stage (`R-SIM-10`) lands here exactly like
        an explicit toggle -- `core.manifest.write_run_manifest`'s own input
        for "the panel emits a run manifest" (`UT-D3-4`)."""
        return {
            working.name: working.mode
            for working, original in zip(self._working.stages, self._pipeline.stages)
            if working.mode != original.mode
        }

    def severed_chains(self) -> tuple[SeveredChain, ...]:
        """Every currently-open severed chain (`R-SIM-10`) in this session's
        working pipeline -- `UT-D3-3`'s own assertion surface, and what
        `stages()` derives each row's `orphan` badge from."""
        return self._working.severed_chains()

    @property
    def last_auto_closed(self) -> tuple[str, ...]:
        """Stage(s) `set_mode`'s most recent call flipped as a side effect
        (never including the stage actually toggled) -- empty unless there
        is something to offer an undo bar for. `()` after
        `undo_last_auto_close` runs, or after a toggle that closed nothing."""
        return self._last_auto_closed

    def _view(self, stage: Stage, *, orphan: bool) -> StageView:
        available, reason = self._measured_availability(stage)
        return StageView(
            name=stage.name, mode=stage.mode, impl=stage.impl,
            measured_available=available, measured_unavailable_reason=reason,
            orphan=orphan,
        )

    def _measured_availability(self, stage: Stage) -> tuple[bool, str]:
        if not stage.impl:
            return False, "stage declares no impl: -- nothing to take measured output from"
        try:
            manifest = self._working.manifest_for(stage.name)
        except KeyError:
            return False, "component did not resolve at load -- see the pipeline's own load error"
        missing = sorted(
            f"{stage.name}.{port.name}" for port in manifest.outputs
            if f"{stage.name}.{port.name}" not in self._known_ports
        )
        if missing:
            return False, "not in recording: " + ", ".join(missing)
        return True, ""

    def set_mode(self, stage_name: str, mode: str) -> None:
        """Flipping mode never discards `impl` (§13's own ergonomic point,
        reversible with one click) -- `impl` always comes from the
        `Pipeline`'s own `Stage`, never a second field here. Delegates to
        `Pipeline.with_mode` (default `close_gaps=True`, `R-SIM-10`): any
        severed chain the change creates is auto-closed, undoably --
        `last_auto_closed` names what moved, for the panel's one-line bar."""
        if mode not in _VALID_MODES:
            raise ValueError(f"mode must be one of {_VALID_MODES}, got {mode!r}")
        if mode == "measured" and not self._measured_availability_for(stage_name):
            raise ValueError(
                f"stage {stage_name!r} has no measured output in this recording -- "
                "the panel must not offer this choice, see measured_unavailable_reason"
            )
        before = {stage.name: stage.mode for stage in self._working.stages}
        self._pre_toggle = self._working
        self._last_toggle = (stage_name, mode)
        self._working = self._working.with_mode(stage_name, mode)
        self._last_auto_closed = tuple(
            stage.name for stage in self._working.stages
            if stage.name != stage_name and before.get(stage.name) != stage.mode
        )

    def undo_last_auto_close(self) -> None:
        """The one-line bar's "Undo" action: re-applies the most recent
        toggle with `close_gaps=False`, forcing the gap back open (`R-SIM-
        10`'s "watch one stage's divergence while a downstream stage stays
        on known-good input"). The auto-flipped stage(s) revert to their
        pre-toggle mode and badge `orphan=True` instead -- never silent,
        `Pipeline.with_mode` raises a `ProvenanceWarning` naming them."""
        if self._pre_toggle is None or self._last_toggle is None or not self._last_auto_closed:
            raise ValueError("no auto-close to undo -- the last toggle closed no gap")
        stage_name, mode = self._last_toggle
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # the panel's badge IS the surfaced warning; no console noise
            self._working = self._pre_toggle.with_mode(stage_name, mode, close_gaps=False)
        self._last_auto_closed = ()

    def _measured_availability_for(self, stage_name: str) -> bool:
        for stage in self._working.stages:
            if stage.name == stage_name:
                return self._measured_availability(stage)[0]
        raise KeyError(stage_name)
