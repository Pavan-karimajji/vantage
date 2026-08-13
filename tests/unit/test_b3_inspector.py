# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 slice 5 `view/inspector.py` tests: `UT-B3-2`
(docs/sim_implementation_plan.md) plus pin/copy-as-text. No Qt -- `view/`
stays headless-testable (`UT-B3-17`'s own layering, extended)."""

from __future__ import annotations

from adas_sim.scene.types import Layer, Prim, Scene
from adas_sim.player.panels.inspector import InspectorState, copy_as_text

_OBJ_7 = Prim(kind="box", cx_m=10.0, cy_m=1.0, length_m=4.5, width_m=1.8, style="object.label",
              pick_id="object.7", fields=(("dist_x", "10.00 m"), ("dist_y", "1.00 m")))
_OBJ_9 = Prim(kind="box", cx_m=20.0, cy_m=-2.0, length_m=4.5, width_m=1.8, style="object.label",
              pick_id="object.9", fields=(("dist_x", "20.00 m"),))


def _scene(*prims: Prim) -> Scene:
    return Scene(layers=(Layer(id="sim.test", group="sim", prims=prims),))


def test_entries_resolves_selected_pick_ids_to_the_prims_declared_fields():
    """UT-B3-2 (resolution half)."""
    state = InspectorState()
    entries = state.entries(_scene(_OBJ_7, _OBJ_9), frozenset({"object.7"}))
    assert len(entries) == 1
    assert entries[0].pick_id == "object.7"
    assert entries[0].fields == (("dist_x", "10.00 m"), ("dist_y", "1.00 m"))
    assert entries[0].pinned is False


def test_a_selected_id_absent_from_the_scene_is_dropped_not_stale():
    """UT-B3-2 (the "not shown stale" half): re-derived from the current
    Scene every call, so an entity that leaves is simply not there."""
    state = InspectorState()
    entries = state.entries(_scene(_OBJ_9), frozenset({"object.7", "object.9"}))
    assert [e.pick_id for e in entries] == ["object.9"]


def test_pin_survives_deselection():
    state = InspectorState()
    state.toggle_pin("object.7")
    entries = state.entries(_scene(_OBJ_7, _OBJ_9), frozenset())  # nothing selected
    assert [e.pick_id for e in entries] == ["object.7"]
    assert entries[0].pinned is True


def test_pin_does_not_survive_the_entity_actually_disappearing():
    """A pin is a promise to keep watching, not a cached last-known value."""
    state = InspectorState()
    state.toggle_pin("object.7")
    entries = state.entries(_scene(_OBJ_9), frozenset())  # object.7 left the world
    assert entries == ()


def test_toggle_pin_is_a_real_toggle():
    state = InspectorState()
    assert state.is_pinned("object.7") is False
    state.toggle_pin("object.7")
    assert state.is_pinned("object.7") is True
    state.toggle_pin("object.7")
    assert state.is_pinned("object.7") is False


def test_selection_comes_before_pinned_only_entries_and_both_are_sorted():
    state = InspectorState()
    state.toggle_pin("object.9")
    entries = state.entries(_scene(_OBJ_7, _OBJ_9), frozenset({"object.7"}))
    assert [e.pick_id for e in entries] == ["object.7", "object.9"]


def test_an_id_both_selected_and_pinned_appears_once():
    state = InspectorState()
    state.toggle_pin("object.7")
    entries = state.entries(_scene(_OBJ_7, _OBJ_9), frozenset({"object.7"}))
    assert [e.pick_id for e in entries] == ["object.7"]
    assert entries[0].pinned is True


def test_copy_as_text_formats_the_pick_id_and_every_field():
    entry = InspectorState().entries(_scene(_OBJ_7), frozenset({"object.7"}))[0]
    assert copy_as_text(entry) == "object.7\ndist_x: 10.00 m\ndist_y: 1.00 m"


def test_a_prim_with_no_declared_fields_yields_an_empty_field_list():
    bare = Prim(kind="box", cx_m=0.0, cy_m=0.0, length_m=4.5, width_m=1.8, style="ego.body", pick_id="ego")
    entries = InspectorState().entries(_scene(bare), frozenset({"ego"}))
    assert entries[0].fields == ()
