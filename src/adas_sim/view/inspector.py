# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`InspectorState` -- the docked inspector's state (S-B3 slice 5,
`sim_visualization_spec.md` §7.2): resolves `pick_id`s to the declared
`Prim.fields` of the prim that carries them, pin, copy-as-text. Pure state,
no pixels, no Qt -- `view/` stays headless-testable, the same discipline
`view/layers.py` established.

**Values are never cached.** `entries()` re-derives from the *current*
`Scene` every call, so "an entity that disappears is dropped, not shown
stale" (`UT-B3-2`) is just what re-deriving does -- there is no separate
staleness check to get wrong. `pinned` only survives *deselection*; it does
not survive the entity's actual disappearance from the world.
"""

from __future__ import annotations

from dataclasses import dataclass

from adas_sim.scene.types import Prim, Scene


@dataclass(frozen=True, slots=True)
class InspectorEntry:
    """One resolved row for the panel: a picked (or pinned) entity's
    declared fields, as of the current tick."""

    pick_id: str
    fields: tuple[tuple[str, str], ...]
    pinned: bool


def _find_prim(scene: Scene, pick_id: str) -> Prim | None:
    for layer in scene.layers:
        for prim in layer.prims:
            if prim.pick_id == pick_id:
                return prim
    return None


class InspectorState:
    """Pin state only -- selection itself lives on `Interaction`
    (`core/history.py`), not duplicated here (`§7.1`'s selection already
    persists across ticks by `pick_id`; this class adds *pin*, which is the
    one thing selection does not cover: staying in the panel after
    deselecting)."""

    def __init__(self) -> None:
        self._pinned: set[str] = set()

    def toggle_pin(self, pick_id: str) -> None:
        if pick_id in self._pinned:
            self._pinned.discard(pick_id)
        else:
            self._pinned.add(pick_id)

    def is_pinned(self, pick_id: str) -> bool:
        return pick_id in self._pinned

    def entries(self, scene: Scene, selection: frozenset[str]) -> tuple[InspectorEntry, ...]:
        """Selected entities first, then pinned-but-not-selected ones --
        both sorted for a deterministic order (`selection`/`_pinned` are
        sets). A `pick_id` absent from `scene` this tick is dropped
        (`UT-B3-2`), whether it came from selection or a pin."""
        wanted = sorted(selection) + sorted(self._pinned - selection)
        entries: list[InspectorEntry] = []
        for pick_id in wanted:
            prim = _find_prim(scene, pick_id)
            if prim is None:
                continue
            entries.append(InspectorEntry(pick_id=pick_id, fields=prim.fields or (), pinned=pick_id in self._pinned))
        return tuple(entries)


def copy_as_text(entry: InspectorEntry) -> str:
    """Plain formatting for a copy-to-clipboard action (§7.2) -- pure, so
    the Qt panel only has to hand the result to a clipboard."""
    lines = [entry.pick_id, *(f"{name}: {value}" for name, value in entry.fields)]
    return "\n".join(lines)
