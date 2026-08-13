# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 slice 8 `render/timeline.py` tests: the raster itself, and the
click-to-seek round trip (`px_to_tick` is the exact inverse of the fixed
`[0, head_tick]` zero-margin x-axis `render_timeline` draws with). No Qt --
matplotlib/`Agg`, headless since `S-B1`'s `render/bev.py`."""

from __future__ import annotations

import numpy as np

from adas_sim.render.timeline import px_to_tick, render_timeline
from adas_sim.player.panels.timeline import EventMarker

_SIZE_PX = (400, 200)


def _blank_render(current_tick: int = 0) -> np.ndarray:
    return render_timeline(
        signal_series={}, state_series={}, markers={}, bookmark_ticks=(),
        current_tick=current_tick, head_tick=49, size_px=_SIZE_PX,
    )


def test_render_produces_the_requested_pixel_shape():
    frame = _blank_render()
    assert frame.shape == (_SIZE_PX[1], _SIZE_PX[0], 3)


def test_render_with_no_lanes_still_draws_a_playhead_row():
    """Zero lanes is `max(1, 0)` -- one lane's worth of canvas, not a
    crash and not a zero-height figure."""
    empty = _blank_render(current_tick=0)
    with_playhead = _blank_render(current_tick=25)
    assert not np.array_equal(empty, with_playhead)


def test_a_signal_lane_changes_the_rendered_pixels():
    blank = render_timeline(
        signal_series={}, state_series={}, markers={}, bookmark_ticks=(),
        current_tick=0, head_tick=49, size_px=_SIZE_PX,
    )
    with_signal = render_timeline(
        signal_series={"derived.ttc": tuple((i, float(i)) for i in range(50))},
        state_series={}, markers={}, bookmark_ticks=(),
        current_tick=0, head_tick=49, size_px=_SIZE_PX,
    )
    assert not np.array_equal(blank, with_signal)


def test_a_state_lane_draws_a_band_and_its_marker():
    series = ((0, "OFF"), (20, "NORMAL"))
    with_state = render_timeline(
        signal_series={}, state_series={"test.warning": series},
        markers={"test.warning": (EventMarker(tick_index=20, label="OFF -> NORMAL"),)},
        bookmark_ticks=(), current_tick=0, head_tick=49, size_px=_SIZE_PX,
    )
    without_marker = render_timeline(
        signal_series={}, state_series={"test.warning": series}, markers={},
        bookmark_ticks=(), current_tick=0, head_tick=49, size_px=_SIZE_PX,
    )
    assert not np.array_equal(with_state, without_marker)


def test_an_expectation_window_changes_the_rendered_pixels():
    """§7.3: "expected windows drawn as translucent spans" -- a window on
    a lane's own address changes what that lane draws."""
    series = ((0, "OFF"), (20, "NORMAL"))
    without_window = render_timeline(
        signal_series={}, state_series={"test.warning": series}, markers={},
        bookmark_ticks=(), current_tick=0, head_tick=49, size_px=_SIZE_PX,
    )
    with_window = render_timeline(
        signal_series={}, state_series={"test.warning": series}, markers={},
        bookmark_ticks=(), current_tick=0, head_tick=49, size_px=_SIZE_PX,
        expectation_windows={"test.warning": ((5, 15, True),)},
    )
    assert not np.array_equal(without_window, with_window)


def test_a_passing_and_a_failing_expectation_window_render_differently():
    """Green vs red -- "so a pass/fail is visible rather than computed"
    (§7.3) has to actually mean two different colours, not one badge."""
    series = ((0, "OFF"), (20, "NORMAL"))
    passing = render_timeline(
        signal_series={}, state_series={"test.warning": series}, markers={},
        bookmark_ticks=(), current_tick=0, head_tick=49, size_px=_SIZE_PX,
        expectation_windows={"test.warning": ((5, 15, True),)},
    )
    failing = render_timeline(
        signal_series={}, state_series={"test.warning": series}, markers={},
        bookmark_ticks=(), current_tick=0, head_tick=49, size_px=_SIZE_PX,
        expectation_windows={"test.warning": ((5, 15, False),)},
    )
    assert not np.array_equal(passing, failing)


def test_an_expectation_window_on_an_unlanned_signal_renders_nothing_extra():
    """A window keyed by a signal that is not lane'd has nowhere to draw
    -- absent, not an error and not drawn elsewhere by guesswork."""
    blank = _blank_render()
    still_blank = render_timeline(
        signal_series={}, state_series={}, markers={}, bookmark_ticks=(),
        current_tick=0, head_tick=49, size_px=_SIZE_PX,
        expectation_windows={"nobody.lanes.this": ((5, 15, True),)},
    )
    assert np.array_equal(blank, still_blank)


def test_px_to_tick_round_trips_at_the_ends_and_middle():
    size_px = (600, 200)
    head_tick = 49
    assert px_to_tick(0, size_px, head_tick) == 0
    assert px_to_tick(size_px[0], size_px, head_tick) == head_tick
    assert px_to_tick(size_px[0] / 2, size_px, head_tick) == round(head_tick / 2)


def test_px_to_tick_clamps_outside_the_canvas():
    assert px_to_tick(-50.0, (600, 200), 49) == 0
    assert px_to_tick(9999.0, (600, 200), 49) == 49


def test_px_to_tick_handles_a_single_tick_session_without_dividing_by_zero():
    assert px_to_tick(0.0, (600, 200), 0) == 0
    assert px_to_tick(600.0, (600, 200), 0) == 0
