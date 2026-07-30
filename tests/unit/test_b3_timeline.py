# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 slice 8 `view/timeline.py` tests: `UT-B3-3`
(docs/sim_implementation_plan.md) plus `TimelineState`'s lane/bookmark
bookkeeping. No Qt (`view/` stays headless-testable)."""

from __future__ import annotations

from adas_sim.view.timeline import EventMarker, TimelineState, event_markers


def test_event_markers_fires_only_on_a_real_transition():
    """UT-B3-3: a marker at every transition, and only there."""
    series = ((0, "OFF"), (1, "OFF"), (2, "NORMAL"), (3, "NORMAL"), (4, "BLINKING"), (5, "BLINKING"))
    markers = event_markers(series)
    assert markers == (
        EventMarker(tick_index=2, label="OFF -> NORMAL"),
        EventMarker(tick_index=4, label="NORMAL -> BLINKING"),
    )


def test_event_markers_on_an_empty_or_single_tick_series_is_empty():
    assert event_markers(()) == ()
    assert event_markers(((0, "OFF"),)) == ()


def test_event_markers_a_value_returning_to_its_predecessor_still_marks_both_edges():
    series = ((0, "OFF"), (1, "NORMAL"), (2, "OFF"))
    markers = event_markers(series)
    assert markers == (
        EventMarker(tick_index=1, label="OFF -> NORMAL"),
        EventMarker(tick_index=2, label="NORMAL -> OFF"),
    )


def test_signal_lanes_never_merge_and_stay_ordered():
    state = TimelineState()
    state.add_signal_lane("derived.ttc")
    state.add_signal_lane("source.veh_dyn.longitudinal.velocity")
    state.add_signal_lane("derived.ttc")  # duplicate -- no second lane, no reordering
    assert state.signal_lanes() == ("derived.ttc", "source.veh_dyn.longitudinal.velocity")


def test_remove_signal_lane_is_a_no_op_if_not_present():
    state = TimelineState()
    state.remove_signal_lane("nothing.here")
    assert state.signal_lanes() == ()


def test_state_lanes_are_tracked_independently_of_signal_lanes():
    state = TimelineState()
    state.add_state_lane("test.warning")
    state.add_signal_lane("test.warning")  # same address, different lane kind -- both are legitimate
    assert state.state_lanes() == ("test.warning",)
    assert state.signal_lanes() == ("test.warning",)
    state.remove_state_lane("test.warning")
    assert state.state_lanes() == ()
    assert state.signal_lanes() == ("test.warning",)


def test_bookmarks_are_returned_sorted_by_tick_and_deduplicated():
    state = TimelineState()
    state.add_bookmark(50, "onset")
    state.add_bookmark(10, "start")
    state.add_bookmark(50, "duplicate tick, ignored")
    ticks = [b.tick_index for b in state.bookmarks()]
    assert ticks == [10, 50]
    assert state.bookmarks()[0].label == "start"
    assert state.bookmarks()[1].label == "onset"


def test_remove_bookmark():
    state = TimelineState()
    state.add_bookmark(10)
    state.add_bookmark(20)
    state.remove_bookmark(10)
    assert [b.tick_index for b in state.bookmarks()] == [20]


def test_jump_to_event_finds_the_nearest_marker_in_each_direction():
    state = TimelineState()
    markers = (EventMarker(tick_index=10, label="a"), EventMarker(tick_index=50, label="b"))
    assert state.jump_to_event(30, 1, markers) == 50
    assert state.jump_to_event(30, -1, markers) == 10
    assert state.jump_to_event(5, -1, markers) is None
    assert state.jump_to_event(60, 1, markers) is None


def test_jump_to_event_also_considers_bookmarks():
    state = TimelineState()
    state.add_bookmark(25)
    markers = (EventMarker(tick_index=10, label="a"),)
    assert state.jump_to_event(15, 1, markers) == 25
