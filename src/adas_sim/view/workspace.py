# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""A component's shipped default panel arrangement (S-B3 slice 9,
`sim_visualization_spec.md` §13b, `modules/<name>/sim/workspace.yaml`).
Pure data + parsing, no Qt -- `view/` stays headless-testable. `R-SIM-1`
holds here exactly as it does for `scene/registry.py`'s layer providers:
this module reads *a* YAML file it is handed and never touches disk on its
own initiative, and it does not know what any component's panel/viewpoint/
signal names mean -- it only validates the *shape* (tabs, splits, views).

**Not built here: multiple tabs as distinct, independently-arranged panel
instances.** `MainWindow`'s dock grid is one `BevPanel`/`LayersPanel`/
`InspectorPanel`/`TimelineStrip` each (`S-B3` slices 1-8) -- a genuine
second tab with its own `BevPanel` at a different viewpoint needs a
tab-switching shell those slices did not build, and this one does not
either. `Workspace.tabs` therefore parses and carries every tab
faithfully (so a workspace.yaml's full shape is validated and testable),
but `render/viewer.py` only *applies* `tabs[0]`'s views to the existing
singleton panels: `bev`'s `viewpoint` becomes the BEV's preset, and
`timeline`'s `signals` become timeline lanes. A documented gap, not a
silent one -- the same discipline `Viewport.follow`'s rendering gap
(`Slice 7a`) was held to.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from adas_sim.core.errors import AuthoringError

_KNOWN_ORIENTATIONS = frozenset({"horizontal", "vertical"})


@dataclass(frozen=True, slots=True)
class WorkspaceView:
    """One panel instance within a tab. `viewpoint`/`signals` are opaque
    names here -- `bev`'s own preset table, `core/signals.py`'s address
    space -- this module composes, it does not validate them (§13b: "a
    workspace names panels and viewpoints, never geometry or colours")."""

    panel: str
    viewpoint: str | None = None
    signals: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class WorkspaceSplit:
    orientation: str  # "horizontal" | "vertical"
    ratio: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class WorkspaceTab:
    name: str
    views: tuple[WorkspaceView, ...]
    split: WorkspaceSplit | None = None


@dataclass(frozen=True, slots=True)
class Workspace:
    tabs: tuple[WorkspaceTab, ...]


def default_workspace() -> Workspace:
    """§13b: "a missing workspace is not an error -- the framework falls
    back to a single BEV plus the timeline"."""
    return Workspace(tabs=(
        WorkspaceTab(name="default", views=(WorkspaceView(panel="bev"), WorkspaceView(panel="timeline"))),
    ))


def parse_workspace(data: dict, *, name: str = "default") -> Workspace:
    """Parses one named workspace out of an already-loaded
    `workspace.yaml` mapping (this function never touches disk -- that is
    `load_workspace`'s job, kept separate so a test can hand this raw
    `dict`s with no file on disk at all)."""
    workspaces = data.get("workspaces") or {}
    if name not in workspaces:
        raise AuthoringError(
            expected=f"a workspace named {name!r}", found=f"available: {sorted(workspaces)}",
            where="adas_sim.view.workspace.parse_workspace",
            hint="check the workspace.yaml's top-level 'workspaces:' keys",
        )
    tabs = []
    for tab_data in workspaces[name].get("tabs") or []:
        if "name" not in tab_data:
            raise AuthoringError(
                expected="a 'name' field on every tab", found=repr(tab_data),
                where="adas_sim.view.workspace.parse_workspace", hint="",
            )
        split = None
        split_data = tab_data.get("split")
        if split_data is not None:
            orientation = split_data.get("orientation")
            if orientation not in _KNOWN_ORIENTATIONS:
                raise AuthoringError(
                    expected=f"split.orientation one of {sorted(_KNOWN_ORIENTATIONS)}",
                    found=repr(orientation), where="adas_sim.view.workspace.parse_workspace",
                    hint=f"tab {tab_data['name']!r}",
                )
            split = WorkspaceSplit(orientation=orientation, ratio=tuple(split_data.get("ratio") or ()))
        views = []
        for view_data in tab_data.get("views") or []:
            if "panel" not in view_data:
                raise AuthoringError(
                    expected="a 'panel' field on every view", found=repr(view_data),
                    where="adas_sim.view.workspace.parse_workspace", hint=f"tab {tab_data['name']!r}",
                )
            views.append(WorkspaceView(
                panel=view_data["panel"], viewpoint=view_data.get("viewpoint"),
                signals=tuple(view_data.get("signals") or ()),
            ))
        tabs.append(WorkspaceTab(name=tab_data["name"], views=tuple(views), split=split))
    return Workspace(tabs=tuple(tabs))


def load_workspace(path: Path, *, name: str = "default") -> Workspace:
    """Reads and parses `path` (a component's `sim/workspace.yaml`).
    **A missing file is not this function's problem to solve** -- the
    caller decides what "missing" means (`default_workspace()` above), the
    same "the framework falls back" framing §13b itself uses rather than a
    loader silently substituting something the caller never asked for."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return parse_workspace(data, name=name)
