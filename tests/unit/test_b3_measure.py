# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 slice 11 `view/measure.py` tests: `UT-B3-4`
(docs/sim_implementation_plan.md). No Qt (`view/` stays
headless-testable)."""

from __future__ import annotations

import math

import pytest

from adas_sim.view.measure import MeasureState, measure, snap_point
from adas_sim.view.viewport import Viewport


def test_measure_distance_dx_dy_correct():
    """UT-B3-4."""
    result = measure((0.0, 0.0), (3.0, 4.0))
    assert result.dx_m == pytest.approx(3.0)
    assert result.dy_m == pytest.approx(4.0)
    assert result.distance_m == pytest.approx(5.0)


def test_measure_bearing_dead_ahead_is_zero():
    result = measure((0.0, 0.0), (10.0, 0.0))
    assert result.bearing_rad == pytest.approx(0.0)


def test_measure_bearing_turns_positive_toward_left():
    """R-COORD-1: +y is left; bearing increases turning that way."""
    result = measure((0.0, 0.0), (0.0, 10.0))
    assert result.bearing_rad == pytest.approx(math.pi / 2.0)


def test_measure_bearing_behind_is_pi():
    result = measure((0.0, 0.0), (-10.0, 0.0))
    assert abs(result.bearing_rad) == pytest.approx(math.pi)


def test_snap_picks_the_nearest_anchor_within_threshold():
    """UT-B3-4: snap picks the nearest anchor within the threshold."""
    vp = Viewport(scale_px_per_m=10.0, size_px=(900, 700))
    anchors = ((5.0, 0.0), (5.05, 0.0), (20.0, 0.0))  # two close together, one far
    snapped = snap_point((5.02, 0.0), anchors, vp, threshold_px=10.0)
    assert snapped == (5.0, 0.0)  # nearest of the two close ones


def test_snap_leaves_the_point_unchanged_outside_threshold():
    vp = Viewport(scale_px_per_m=10.0, size_px=(900, 700))
    anchors = ((50.0, 50.0),)  # far away in metres and pixels
    point = (0.0, 0.0)
    assert snap_point(point, anchors, vp, threshold_px=10.0) == point


def test_snap_threshold_is_a_screen_distance_not_a_metre_radius():
    """A wide-out zoom (few px/m) must not snap across a large metre gap
    just because the *screen* distance would have qualified at a closer
    zoom -- and a close-in zoom must snap at a smaller metre gap than a
    wide-out one would, for the same pixel threshold."""
    wide = Viewport(scale_px_per_m=1.0, size_px=(900, 700))  # 1 px/m
    close = Viewport(scale_px_per_m=100.0, size_px=(900, 700))  # 100 px/m
    anchors = ((5.0, 0.0),)

    # 5m away = 5px at wide zoom (inside a 10px threshold) but 500px at close zoom (outside it).
    assert snap_point((0.0, 0.0), anchors, wide, threshold_px=10.0) == (5.0, 0.0)
    assert snap_point((0.0, 0.0), anchors, close, threshold_px=10.0) == (0.0, 0.0)


def test_snap_with_no_anchors_returns_the_point_unchanged():
    vp = Viewport(scale_px_per_m=10.0, size_px=(900, 700))
    assert snap_point((1.0, 2.0), (), vp) == (1.0, 2.0)


def test_measure_state_ruler_round_trip_and_overlay_prims():
    state = MeasureState()
    assert state.ruler() is None
    assert state.overlay_prims() == ()

    result = state.set_ruler((0.0, 0.0), (3.0, 4.0))
    assert result.distance_m == pytest.approx(5.0)
    assert state.ruler() is result
    prims = state.overlay_prims()
    assert len(prims) == 2  # a polyline + a label
    assert prims[0].kind == "polyline"
    assert prims[1].kind == "text"

    state.clear_ruler()
    assert state.ruler() is None
    assert state.overlay_prims() == ()


def test_measure_state_range_rings_are_hidden_until_toggled_on():
    state = MeasureState()
    state.set_range_ring_radii((10.0, 20.0, 30.0))
    assert state.overlay_prims() == ()  # set, but not visible yet

    state.toggle_range_rings()
    assert state.range_rings_visible is True
    prims = state.overlay_prims()
    assert len(prims) == 3
    assert all(p.kind == "circle" for p in prims)
    assert [p.r_m for p in prims] == [10.0, 20.0, 30.0]

    state.toggle_range_rings()
    assert state.overlay_prims() == ()


def test_measure_state_annotations_are_persistent_across_ruler_and_ring_changes():
    state = MeasureState()
    state.add_annotation((1.0, 2.0), "here")
    state.set_ruler((0.0, 0.0), (1.0, 1.0))
    state.clear_ruler()

    labels = [a.label for a in state.annotations()]
    assert labels == ["here"]
    prims = state.overlay_prims()
    assert any(p.kind == "points" for p in prims)
    assert any(p.kind == "text" and p.text == "here" for p in prims)


def test_measure_state_remove_annotation():
    state = MeasureState()
    state.add_annotation((1.0, 1.0), "a")
    state.add_annotation((2.0, 2.0), "b")
    state.remove_annotation(0)
    assert [a.label for a in state.annotations()] == ["b"]


def test_measure_state_remove_annotation_out_of_range_is_a_no_op():
    state = MeasureState()
    state.add_annotation((1.0, 1.0), "a")
    state.remove_annotation(5)
    assert [a.label for a in state.annotations()] == ["a"]
