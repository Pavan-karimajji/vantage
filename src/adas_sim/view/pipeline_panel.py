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

**Narrowed vs §13, this pass.** `impl:` is read-only: the spec's dropdown
of alternative implementations needs a directory scan of on-disk component
manifests that does not exist anywhere in this framework yet (`sim list
ports <lib>` reads one manifest given an explicit path; nothing discovers
candidates). Also not built here: per-port override expansion, the
severed-chain flag/undo bar, compare-against-recorded, and the manifest
round-trip (`UT-D3-3`/`UT-D3-4`/`UT-D3-5`/`UT-D3-6`/`UT-D3-8`, `ST-D3-1`
stay unticked in `sim_implementation_plan.md`). What this pass proves:
discovery-driven rendering and a mode toggle that never discards `impl`
(`UT-D3-1` partial, `UT-D3-2`, `UT-D3-7`).
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from adas_sim.contracts.pipeline import Pipeline

_VALID_MODES = ("simulate", "measured", "off")


@dataclass(frozen=True, slots=True)
class StageView:
    """What the panel needs to render one row -- `mode` is the CURRENT
    displayed mode (the stage's own declared mode, or a user override from
    `PipelinePanelState.set_mode`), never conflated with the two."""

    name: str
    mode: str
    impl: str | None
    measured_available: bool
    measured_unavailable_reason: str  # "" exactly when measured_available


class PipelinePanelState:
    """One instance per (pipeline, recording) pairing -- mirrors
    `LayerTreeState`'s own "one instance per (project, pipeline)" scope.
    `known_ports` is the run-relative port universe (`Session.known_ports`'s
    own shape: qualified `<stage>.<port>` names), computed once by the
    caller -- this class never re-derives it and never opens a recording
    itself."""

    def __init__(self, pipeline: Pipeline, known_ports: Collection[str]) -> None:
        self._pipeline = pipeline
        self._known_ports = frozenset(known_ports)
        self._mode_overrides: dict[str, str] = {}

    def stages(self) -> tuple[StageView, ...]:
        return tuple(self._view(stage) for stage in self._pipeline.stages)

    @property
    def pipeline(self) -> Pipeline:
        """The underlying `Pipeline`, unchanged -- `core.manifest.
        write_run_manifest`'s `pipeline=` argument (stage/impl/inputs come
        from here; only `mode` may differ, via `mode_overrides` below)."""
        return self._pipeline

    @property
    def mode_overrides(self) -> dict[str, str]:
        """Every stage this session actually toggled, stage name -> mode --
        a snapshot (mutating the returned dict does not affect this state).
        `core.manifest.write_run_manifest`'s own input for "the panel emits
        a run manifest" (`UT-D3-4`)."""
        return dict(self._mode_overrides)

    def _view(self, stage) -> StageView:
        available, reason = self._measured_availability(stage)
        mode = self._mode_overrides.get(stage.name, stage.mode)
        return StageView(
            name=stage.name, mode=mode, impl=stage.impl,
            measured_available=available, measured_unavailable_reason=reason,
        )

    def _measured_availability(self, stage) -> tuple[bool, str]:
        if not stage.impl:
            return False, "stage declares no impl: -- nothing to take measured output from"
        try:
            manifest = self._pipeline.manifest_for(stage.name)
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
        reversible with one click) -- this method touches only the mode
        override map, `impl` is always read from the original `Stage`."""
        if mode not in _VALID_MODES:
            raise ValueError(f"mode must be one of {_VALID_MODES}, got {mode!r}")
        if mode == "measured" and not self._measured_availability_for(stage_name):
            raise ValueError(
                f"stage {stage_name!r} has no measured output in this recording -- "
                "the panel must not offer this choice, see measured_unavailable_reason"
            )
        self._mode_overrides[stage_name] = mode

    def _measured_availability_for(self, stage_name: str) -> bool:
        for stage in self._pipeline.stages:
            if stage.name == stage_name:
                return self._measured_availability(stage)[0]
        raise KeyError(stage_name)
