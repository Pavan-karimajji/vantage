# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`LayerTreeState` -- layer-tree state (S-B3 slice 2, `sim_visualization_spec.md`
§6): groups, per-layer visibility, solo/mute, per-group verbosity level, a
search filter, and persistence. Pure state, no pixels, no Qt -- `view/` stays
headless-testable (`UT-B3-1` exercises this with no window, the same
"testable with no window" bar `ST-B3-1` sets for `core/`/`view/`/`check/`).

**Discovery, not registration.** The tree has no roster of its own: `sync()`
reads whichever `Layer`s a `Scene` actually carries, so a new layer id shows
up in the panel by existing (`R-VAR-2`'s "no central roster" principle,
already applied to layer *providers* in `scene/registry.py`, extended here to
the panel that lists them).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from adas_sim.scene.types import Layer


@dataclass(frozen=True, slots=True)
class LayerInfo:
    """What the tree needs to know about one discovered layer id."""

    id: str
    group: str
    label: str
    level: int
    default_on: bool


class LayerTreeState:
    """One instance per (project, pipeline) -- `sim_visualization_spec.md`
    §6's own persistence scope (opening a recording restores that function's
    layer choices). Holds only small metadata (ids/groups/levels/labels) and
    user overrides, never `Prim`s -- `sync()` is called once per newly-seen
    `Scene`, not once per tick.
    """

    def __init__(self) -> None:
        self._known: dict[str, LayerInfo] = {}
        self._overrides: dict[str, bool] = {}
        self._group_level: dict[str, int] = {}
        self._solo_group: str | None = None
        self._muted_groups: set[str] = set()
        self._search: str = ""

    def sync(self, layers: Sequence[Layer]) -> None:
        """Registers any layer id not seen before. Never removes a
        previously-seen id (a layer absent from one tick's `Scene` -- e.g. a
        gated provider with no port this tick -- must not vanish from the
        tree and silently reset the user's choice for it)."""
        for layer in layers:
            if layer.id not in self._known:
                self._known[layer.id] = LayerInfo(
                    id=layer.id, group=layer.group, label=layer.label or layer.id,
                    level=layer.level, default_on=layer.default_on,
                )
                self._group_level.setdefault(layer.group, 1)

    def groups(self) -> tuple[str, ...]:
        return tuple(sorted({info.group for info in self._known.values()}))

    def layers_in_group(self, group: str) -> tuple[LayerInfo, ...]:
        return tuple(sorted(
            (info for info in self._known.values() if info.group == group),
            key=lambda info: info.id,
        ))

    # -- per-layer visibility -------------------------------------------------

    def set_visible(self, layer_id: str, visible: bool) -> None:
        self._overrides[layer_id] = visible

    def is_visible(self, layer_id: str) -> bool:
        """Effective visibility: an explicit user override wins; otherwise
        `default_on`, gated by the group's verbosity level, solo and mute."""
        info = self._known.get(layer_id)
        if info is None:
            return False
        if self._solo_group is not None and info.group != self._solo_group:
            return False
        if info.group in self._muted_groups:
            return False
        if info.level > self._group_level.get(info.group, 1):
            return False
        return self._overrides.get(layer_id, info.default_on)

    def visible_layer_ids(self) -> frozenset[str]:
        return frozenset(layer_id for layer_id in self._known if self.is_visible(layer_id))

    # -- group tri-state -------------------------------------------------------

    def group_state(self, group: str) -> str:
        """`"on"` / `"off"` / `"mixed"` -- the group checkbox's tri-state,
        derived from its layers' effective visibility rather than stored
        separately (there is no third piece of state to drift from the two
        that already determine it)."""
        ids = [info.id for info in self._known.values() if info.group == group]
        if not ids:
            return "off"
        states = {self.is_visible(layer_id) for layer_id in ids}
        if states == {True}:
            return "on"
        if states == {False}:
            return "off"
        return "mixed"

    def set_group_visible(self, group: str, visible: bool) -> None:
        for info in self._known.values():
            if info.group == group:
                self._overrides[info.id] = visible

    def set_group_level(self, group: str, level: int) -> None:
        self._group_level[group] = level

    # -- solo / mute -------------------------------------------------------------

    def toggle_solo(self, group: str) -> None:
        """`Alt`+click (`sim_visualization_spec.md` §6): solo again un-solos."""
        self._solo_group = None if self._solo_group == group else group

    @property
    def solo_group(self) -> str | None:
        return self._solo_group

    def toggle_mute(self, group: str) -> None:
        if group in self._muted_groups:
            self._muted_groups.discard(group)
        else:
            self._muted_groups.add(group)

    def is_muted(self, group: str) -> bool:
        return group in self._muted_groups

    # -- search ---------------------------------------------------------------

    def set_search(self, text: str) -> None:
        """A tree-widget display filter only -- narrows what the panel lists,
        never what `visible_layer_ids()` renders."""
        self._search = text.strip().lower()

    def matches_search(self, layer_id: str) -> bool:
        if not self._search:
            return True
        info = self._known.get(layer_id)
        haystack = f"{layer_id} {info.label if info else ''}".lower()
        return self._search in haystack

    # -- persistence -------------------------------------------------------------

    def to_dict(self) -> dict:
        """Plain data, no Qt (`view/` stays Qt-free) -- the caller decides
        *where* this is written (`P-7`: `QStandardPaths.AppConfigLocation`,
        the panel's job, not this module's)."""
        return {
            "overrides": dict(self._overrides),
            "group_level": dict(self._group_level),
            "solo_group": self._solo_group,
            "muted_groups": sorted(self._muted_groups),
        }

    def load_dict(self, data: dict) -> None:
        self._overrides = dict(data.get("overrides", {}))
        self._group_level = dict(data.get("group_level", {}))
        self._solo_group = data.get("solo_group")
        self._muted_groups = set(data.get("muted_groups", []))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    def load(self, path: Path) -> None:
        if not path.is_file():
            return
        self.load_dict(json.loads(path.read_text(encoding="utf-8")))
