# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-A2 `ObjectModel`/`Footprint` tests: UT-A2-4, UT-A2-5
(docs/sim_implementation_plan.md)."""

from __future__ import annotations

from adas_sim.model.objects import Footprint, ObjectModel

_FALLBACK = Footprint(length_m=1.0, width_m=1.0)
_CLASS_TABLE = {
    "motorcycle": Footprint(length_m=2.10, width_m=0.80),
    "car": Footprint(length_m=4.50, width_m=1.80),
}


def test_footprint_precedence_per_object_geometry_wins():
    """UT-A2-4: a per-object `geometry` argument wins outright."""
    model = ObjectModel(class_table=_CLASS_TABLE, fallback=_FALLBACK)
    override = Footprint(length_m=9.9, width_m=9.9)
    assert model.footprint("car", geometry=override) == override


def test_footprint_precedence_class_table_wins_without_geometry():
    """UT-A2-4."""
    model = ObjectModel(class_table=_CLASS_TABLE, fallback=_FALLBACK)
    assert model.footprint("motorcycle") == _CLASS_TABLE["motorcycle"]


def test_footprint_falls_back_and_the_fallback_is_marked_assumed():
    """UT-A2-4: without geometry and without a class-table entry, the
    declared fallback -- and assumed_geometry is True."""
    model = ObjectModel(class_table=_CLASS_TABLE, fallback=_FALLBACK)
    resolved = model.footprint("unknown_class")
    assert resolved.length_m == _FALLBACK.length_m
    assert resolved.width_m == _FALLBACK.width_m
    assert resolved.assumed_geometry is True


def test_fallback_is_forced_to_assumed_geometry_even_if_constructed_without_it():
    """A caller cannot accidentally create a fallback that claims to be measured."""
    model = ObjectModel(class_table={}, fallback=Footprint(length_m=1.0, width_m=1.0, assumed_geometry=False))
    assert model.footprint("anything").assumed_geometry is True


def test_two_different_classes_resolve_to_different_footprints():
    """UT-A2-5."""
    model = ObjectModel(class_table=_CLASS_TABLE, fallback=_FALLBACK)
    car = model.footprint("car")
    motorcycle = model.footprint("motorcycle")
    assert car != motorcycle
