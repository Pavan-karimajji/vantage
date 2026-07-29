# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`HistoryView`, `FrameTree`, `Interaction`, `LayerCtx`
(sim_architecture.md §5.3, sim_requirements.md, sim_api_reference.md §5).
Together with `model.ProjectModel`, these are everything a layer provider may
legitimately need -- gives it the tick, a read-only windowed history, the
frame graph and the project model, so the bans in `sim_api_reference.md` §5
(no disk, no renderer, no held state) cost nothing.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from adas_sim.core.tick import Pose2D, Tick
from adas_sim.model.project import ProjectModel


@dataclass(frozen=True, slots=True)
class HistoryView:
    """A read-only window over earlier ticks -- never the whole session,
    never forward, never held across calls (a provider is a pure function of
    its arguments; handing it the full session would invite it to become a
    second analysis engine).
    """

    _ticks: tuple[Tick, ...]

    def last(self, n: int) -> tuple[Tick, ...]:
        """The last `n` windowed ticks, oldest first."""
        if n <= 0:
            return ()
        return self._ticks[-n:]

    def since_s(self, span_s: float) -> tuple[Tick, ...]:
        """Every windowed tick within `span_s` seconds of the most recent one."""
        if not self._ticks:
            return ()
        cutoff = self._ticks[-1].t_s - span_s
        return tuple(t for t in self._ticks if t.t_s >= cutoff)

    def __len__(self) -> int:
        return len(self._ticks)

    def __repr__(self) -> str:
        return f"<HistoryView ticks={len(self._ticks)}>"


@dataclass(frozen=True, slots=True)
class FrameTree:
    """Static (model) + dynamic (`tick.pose`) transforms between named frames
    (`scene/frames.py`'s frame graph, R-COORD-1).

    **Scoped to `ego`<->`world` for now.** That pair is always resolvable
    from `tick.pose` alone; `sensor:<id>`/`image:<cam>` need a static pose
    that is not generically available (`model/project.py`'s own scoping note:
    real sensor/camera poses are calibration owned by the consuming
    component, not `ProjectModel`). Extended once a component's own layer
    provider (`S-B1`) supplies one, or a later stage names a generic source.
    """

    pose: Pose2D

    def to_world(self, x_m: float, y_m: float) -> tuple[float, float]:
        """An `ego`-frame point -> `world`-frame point."""
        cos_yaw, sin_yaw = math.cos(self.pose.yaw_rad), math.sin(self.pose.yaw_rad)
        return (
            self.pose.x_m + x_m * cos_yaw - y_m * sin_yaw,
            self.pose.y_m + x_m * sin_yaw + y_m * cos_yaw,
        )

    def to_ego(self, x_m: float, y_m: float) -> tuple[float, float]:
        """A `world`-frame point -> `ego`-frame point (the inverse transform)."""
        dx, dy = x_m - self.pose.x_m, y_m - self.pose.y_m
        cos_yaw, sin_yaw = math.cos(self.pose.yaw_rad), math.sin(self.pose.yaw_rad)
        return (dx * cos_yaw + dy * sin_yaw, -dx * sin_yaw + dy * cos_yaw)

    def __repr__(self) -> str:
        return f"<FrameTree pose={self.pose!r}>"


@dataclass(frozen=True, slots=True)
class Interaction:
    """Cursor (in the layer's own frame, metres), selection, modifiers,
    toggles (sim_visualization_spec.md §7.5, sim_requirements.md) -- carried
    on `LayerCtx`, never an event callback, so a provider stays a pure
    function of `(tick, ctx)`. Everything defaults to "nothing is happening":
    a Scene built with no live cursor (every stage before `S-B3`'s Qt shell)
    never has to construct one by hand.
    """

    cursor: tuple[float, float] | None = None
    selection: frozenset[str] = frozenset()
    modifiers: frozenset[str] = frozenset()
    toggles: Mapping[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "toggles", MappingProxyType(dict(self.toggles)))

    def __repr__(self) -> str:
        return f"<Interaction selection={sorted(self.selection)} toggles={dict(self.toggles)}>"


@dataclass(frozen=True, slots=True)
class LayerCtx:
    """Everything a layer provider may read (sim_architecture.md §5.3)."""

    model: ProjectModel
    history: HistoryView
    frames: FrameTree
    interaction: Interaction = field(default_factory=Interaction)

    def __repr__(self) -> str:
        return f"<LayerCtx project={self.model.project!r} history={len(self.history)}>"
