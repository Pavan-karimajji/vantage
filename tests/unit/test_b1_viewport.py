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
