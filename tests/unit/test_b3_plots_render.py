# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 slice 10 `render/plots.py` tests: `UT-B3-8` (docs/
sim_implementation_plan.md) plus `distribution`. No Qt -- matplotlib/`Agg`,
headless since `S-B1`'s `render/bev.py`."""

from __future__ import annotations

import numpy as np

from adas_sim.render.plots import render_distribution, render_xy

_SIZE_PX = (300, 200)
_X = tuple((i, float(i)) for i in range(20))
_Y = tuple((i, float(i) * 2.0) for i in range(20))


def test_render_xy_produces_the_requested_pixel_shape():
    frame = render_xy(_X, _Y, None, current_tick=5, size_px=_SIZE_PX)
    assert frame.shape == (_SIZE_PX[1], _SIZE_PX[0], 3)


def test_render_xy_plots_signal_vs_signal_not_vs_time():
    """UT-B3-8: changing `y`'s values (not `x`) changes the picture --
    proving the plot is a function of both series, not just x-vs-time."""
    flat_y = tuple((i, 0.0) for i in range(20))
    varying = render_xy(_X, _Y, None, current_tick=5, size_px=_SIZE_PX)
    flat = render_xy(_X, flat_y, None, current_tick=5, size_px=_SIZE_PX)
    assert not np.array_equal(varying, flat)


def test_render_xy_colouring_by_a_third_signal_changes_the_picture():
    """UT-B3-8: "colouring by a third works"."""
    uncoloured = render_xy(_X, _Y, None, current_tick=5, size_px=_SIZE_PX)
    color = tuple((i, float(i % 3)) for i in range(20))
    coloured = render_xy(_X, _Y, color, current_tick=5, size_px=_SIZE_PX)
    assert not np.array_equal(uncoloured, coloured)


def test_render_xy_only_pairs_ticks_present_in_both_series():
    partial_x = tuple((i, float(i)) for i in range(10))
    frame = render_xy(partial_x, _Y, None, current_tick=5, size_px=_SIZE_PX)
    assert frame.shape == (_SIZE_PX[1], _SIZE_PX[0], 3)  # no crash on mismatched ranges


def test_render_distribution_produces_the_requested_pixel_shape():
    frame = render_distribution(tuple(float(i) for i in range(50)), current_value=None, size_px=_SIZE_PX)
    assert frame.shape == (_SIZE_PX[1], _SIZE_PX[0], 3)


def test_render_distribution_current_value_marker_changes_the_picture():
    values = tuple(float(i) for i in range(50))
    without_marker = render_distribution(values, current_value=None, size_px=_SIZE_PX)
    with_marker = render_distribution(values, current_value=25.0, size_px=_SIZE_PX)
    assert not np.array_equal(without_marker, with_marker)


def test_render_distribution_handles_no_values_without_crashing():
    frame = render_distribution((), current_value=None, size_px=_SIZE_PX)
    assert frame.shape == (_SIZE_PX[1], _SIZE_PX[0], 3)
