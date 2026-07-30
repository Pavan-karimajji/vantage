# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B1 `view/viewport.py` test: UT-B1-9 (docs/sim_implementation_plan.md)."""

from __future__ import annotations

import pytest

from adas_sim.view.viewport import Viewport


@pytest.mark.parametrize("x_m,y_m", [(0.0, 0.0), (10.0, 5.0), (-3.0, 7.0), (42.0, -18.5)])
def test_metre_pixel_metre_round_trips(x_m, y_m):
    """UT-B1-9."""
    vp = Viewport(centre_m=(5.0, -2.0), scale_px_per_m=10.0, rotation_rad=0.3, size_px=(900, 700))
    px, py = vp.to_px(x_m, y_m)
    x2, y2 = vp.to_m(px, py)
    assert x2 == pytest.approx(x_m, abs=1e-9)
    assert y2 == pytest.approx(y_m, abs=1e-9)


def test_zoom_about_cursor_keeps_the_cursors_world_point_fixed():
    """UT-B1-9."""
    vp = Viewport(centre_m=(5.0, -2.0), scale_px_per_m=10.0, size_px=(900, 700))
    cursor_px = (400.0, 300.0)
    world_before = vp.to_m(*cursor_px)
    zoomed = vp.zoomed_about_cursor(2.0, cursor_px)
    world_after = zoomed.to_m(*cursor_px)
    assert world_after[0] == pytest.approx(world_before[0])
    assert world_after[1] == pytest.approx(world_before[1])
    assert zoomed.scale_px_per_m == pytest.approx(20.0)


def test_scale_clamps_at_its_declared_bounds():
    """UT-B1-9."""
    too_far_in = Viewport(scale_px_per_m=190.0).zoomed_about_cursor(5.0, (450.0, 350.0))
    assert too_far_in.scale_px_per_m == Viewport.MAX_SCALE_PX_PER_M

    too_far_out = Viewport(scale_px_per_m=2.0).zoomed_about_cursor(0.1, (450.0, 350.0))
    assert too_far_out.scale_px_per_m == Viewport.MIN_SCALE_PX_PER_M


def test_panning_keeps_the_grabbed_world_point_under_the_drag_end():
    """S-B3 slice 7a (viz §4.4): dragging from `start_px` to `end_px` --
    the world point under `start_px` ends up under `end_px`, the same
    invariant `zoomed_about_cursor` proves for zoom."""
    vp = Viewport(centre_m=(5.0, -2.0), scale_px_per_m=10.0, size_px=(900, 700))
    start_px, end_px = (400.0, 300.0), (450.0, 340.0)
    world_grabbed = vp.to_m(*start_px)

    panned = vp.panned(start_px, end_px)
    assert panned.to_m(*end_px) == pytest.approx(world_grabbed)
    assert panned.scale_px_per_m == vp.scale_px_per_m  # pan never touches scale


def test_fitted_to_centres_on_the_bounds_and_shrinks_scale_to_fit():
    vp = Viewport(centre_m=(0.0, 0.0), scale_px_per_m=50.0, size_px=(900, 700))
    bounds = (-10.0, -5.0, 10.0, 5.0)  # x (fwd) span 20m, y (left) span 10m
    fitted = vp.fitted_to(bounds, margin=0.0)
    assert fitted.centre_m == pytest.approx((0.0, 0.0))
    # height/x_span=700/20=35, width/y_span=900/10=90 -- the smaller wins.
    assert fitted.scale_px_per_m == pytest.approx(35.0)


def test_fitted_to_applies_a_margin():
    vp = Viewport(size_px=(900, 700))
    fitted = vp.fitted_to((-10.0, -5.0, 10.0, 5.0), margin=0.1)
    assert fitted.scale_px_per_m == pytest.approx(35.0 * 0.9)


def test_fitted_to_clamps_at_scale_bounds():
    vp = Viewport(size_px=(900, 700))
    huge = vp.fitted_to((-1000.0, -1000.0, 1000.0, 1000.0), margin=0.0)
    assert huge.scale_px_per_m == Viewport.MIN_SCALE_PX_PER_M

    tiny = vp.fitted_to((-0.001, -0.001, 0.001, 0.001), margin=0.0)
    assert tiny.scale_px_per_m == Viewport.MAX_SCALE_PX_PER_M


def test_fitted_to_a_degenerate_single_point_keeps_the_current_scale():
    vp = Viewport(scale_px_per_m=15.0, size_px=(900, 700))
    fitted = vp.fitted_to((3.0, 3.0, 3.0, 3.0))
    assert fitted.scale_px_per_m == pytest.approx(15.0)
    assert fitted.centre_m == pytest.approx((3.0, 3.0))
