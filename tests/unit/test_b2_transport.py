# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B2 `view/transport.py` tests: UT-B2-4, UT-B2-7, UT-B2-8, UT-B2-9,
UT-B2-10 (docs/sim_implementation_plan.md)."""

from __future__ import annotations

import pytest

from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.session.session import Session
from adas_sim.session.tick import Pose2D, PortValue, Tick
from adas_sim.player.panels.transport import CancelToken, ResumeOption, Transport

_ORIGIN_POSE = Pose2D(x_m=0.0, y_m=0.0, yaw_rad=0.0)


def _make_session(count: int, *, deterministic: bool = True) -> Session:
    ticks = tuple(
        Tick(index=i, t_ns=i * 50_000_000, dt_ns=50_000_000 if i else 0,
             ports={"p": PortValue(name="p", message=b"", origin="measured")}, pose=_ORIGIN_POSE)
        for i in range(count)
    )
    return Session(run_id="r", name="s", ticks=ticks, deterministic=deterministic)


class _StatefulExecCounter:
    """Stands in for a real SUT's `exec()` loop: maintains its own position
    and an `exec_calls` counter that only advances on genuine forward
    progress -- exactly what UT-B2-7 needs to assert against."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.position = 0
        self.exec_calls = 0

    def __call__(self, n, on_progress, cancel) -> int:
        target = min(self.position + n, len(self.session) - 1)
        while self.position < target:
            if cancel.cancelled:
                break
            self.position += 1
            self.exec_calls += 1
            on_progress(self.position, target)
        return self.position


def test_speed_loop_and_step_arithmetic_at_the_ends():
    """UT-B2-4."""
    session = _make_session(5)
    exec_counter = _StatefulExecCounter(session)
    transport = Transport(session, exec_counter)
    transport.advance(4)  # head_tick = 4 (the last tick)

    transport.speed = 2.0
    assert transport.speed == 2.0
    transport.loop_marks = (1, 3)
    assert transport.loop_marks == (1, 3)

    transport.goto(0)
    transport.step_back(1)  # clamps at 0, does not go negative
    assert transport.cursor == 0
    transport.goto(4)
    transport.step_forward(10)  # clamps at the last tick, does not overrun
    assert transport.cursor == 4


def test_stepping_backward_leaves_execution_mode():
    """UT-B2-7: is_at_head goes false, review_mode true, and the SUT's
    exec() counter does not advance on any further backward step or seek."""
    session = _make_session(10)
    exec_counter = _StatefulExecCounter(session)
    transport = Transport(session, exec_counter)
    transport.advance(5)
    calls_at_head = exec_counter.exec_calls

    transport.step_back(2)
    assert transport.is_at_head is False
    assert transport.review_mode is True
    assert exec_counter.exec_calls == calls_at_head

    transport.step_back(1)
    transport.goto(1)
    assert exec_counter.exec_calls == calls_at_head


def test_resume_offers_exactly_two_choices_recompute_unavailable_when_nondeterministic():
    """UT-B2-8."""
    deterministic_session = _make_session(5, deterministic=True)
    transport = Transport(deterministic_session, _StatefulExecCounter(deterministic_session))
    options = transport.resume_options()
    assert len(options) == 2
    assert {o.option for o in options} == {ResumeOption.SKIP_TO_HEAD, ResumeOption.RECOMPUTE_FROM_ZERO}
    assert all(o.available for o in options)

    live_session = _make_session(5, deterministic=False)
    transport = Transport(live_session, _StatefulExecCounter(live_session))
    options = transport.resume_options()
    assert len(options) == 2
    recompute = next(o for o in options if o.option is ResumeOption.RECOMPUTE_FROM_ZERO)
    assert recompute.available is False
    assert recompute.reason


def test_no_silent_continue_advancing_from_a_rewound_tick_raises():
    """UT-B2-9."""
    session = _make_session(10)
    exec_counter = _StatefulExecCounter(session)
    transport = Transport(session, exec_counter)
    transport.advance(5)
    transport.step_back(2)

    with pytest.raises(AuthoringError):
        transport.step_forward(5)  # would go past head while rewound
    with pytest.raises(AuthoringError):
        transport.advance(1)


def test_advance_n_arithmetic_clamps_at_the_end():
    """UT-B2-10: 50 requested on a 30-tick session clamps at the last tick."""
    session = _make_session(30)
    transport = Transport(session, _StatefulExecCounter(session))
    reached = transport.advance(50)
    assert reached == 29
    assert transport.head_tick == 29


@pytest.mark.parametrize("n", [50, 100, 200])
def test_advance_n_arithmetic_at_custom_sizes(n):
    """UT-B2-10: 50/100/200/custom, on a session with headroom for all of them."""
    session = _make_session(300)
    transport = Transport(session, _StatefulExecCounter(session))
    reached = transport.advance(n)
    assert reached == n
    assert transport.head_tick == n


def test_advance_cancel_at_tick_k_leaves_head_tick_at_k():
    """UT-B2-10: cancel at tick k leaves head_tick == k."""
    session = _make_session(300)

    def cancel_at_17(n, on_progress, token):
        reached = 0
        target = min(n, len(session) - 1)
        while reached < target:
            reached += 1
            on_progress(reached, target)
            if reached == 17:
                token.cancel()
            if token.cancelled:
                break
        return reached

    transport = Transport(session, cancel_at_17)
    reached = transport.advance(100, cancel=CancelToken())
    assert reached == 17
    assert transport.head_tick == 17
