# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B2 `core/session.py` tests: UT-B2-1, UT-B2-2, UT-B2-6, UT-B2-11
(docs/sim_implementation_plan.md). `Session.signal()` (`S-B3` slice 6) is
tested here too, as a thin delegation to `core/signals.py` -- the resolver
mechanics themselves are `tests/unit/test_b3_signals.py`'s job."""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest

from adas_sim.core.session import Session
from adas_sim.core.tick import Pose2D, PortValue, Tick

_ORIGIN_POSE = Pose2D(x_m=0.0, y_m=0.0, yaw_rad=0.0)


def _make_ticks(count: int, *, dt_ns: int = 50_000_000) -> tuple[Tick, ...]:
    ticks = []
    t_ns = 0
    for index in range(count):
        ticks.append(
            Tick(
                index=index, t_ns=t_ns, dt_ns=dt_ns if index else 0,
                ports={"p": PortValue(name="p", message=b"", origin="measured")},
                pose=_ORIGIN_POSE,
            )
        )
        t_ns += dt_ns
    return tuple(ticks)


def test_seek_time_maps_to_the_correct_tick_at_boundaries():
    """UT-B2-1."""
    session = Session(run_id="r", name="s", ticks=_make_ticks(5, dt_ns=50_000_000))
    assert session.seek_ns(-10) == 0
    assert session.seek_ns(0) == 0
    assert session.seek_ns(49_999_999) == 0
    assert session.seek_ns(50_000_000) == 1
    assert session.seek_ns(50_000_001) == 1
    assert session.seek_ns(10_000_000_000) == 4  # far beyond the last tick


def test_backwards_seek_returns_the_exact_earlier_tick():
    """UT-B2-2: from tick N to tick 0 returns tick 0's exact data."""
    session = Session(run_id="r", name="s", ticks=_make_ticks(50))
    tick_49 = session.at(49)
    assert tick_49.index == 49
    tick_0 = session.at(0)
    assert tick_0.index == 0
    assert tick_0.t_ns == 0
    # And forward again -- the data at 49 is unchanged by having visited 0.
    assert session.at(49) == tick_49


def test_time_is_exact_over_ten_thousand_ticks_zero_drift():
    """UT-B2-6: t_ns accumulated equals the sum of dt_ns with zero drift;
    t_s is derived and never fed back."""
    dt_ns = 16_666_667  # ~60 Hz, deliberately not a round number in seconds
    ticks = _make_ticks(10_000, dt_ns=dt_ns)
    session = Session(run_id="r", name="s", ticks=ticks)
    last = session.at(len(session) - 1)
    assert last.t_ns == dt_ns * (len(session) - 1)
    assert last.t_s == pytest.approx(last.t_ns / 1e9)


def test_signal_delegates_to_the_core_signals_resolver():
    """`NR-SIM-8`: `Session.signal()` is the api-reference contract's own
    entry point, not a second implementation."""
    ticks = tuple(
        Tick(index=i, t_ns=i * 50_000_000, dt_ns=50_000_000,
             ports={"p": PortValue(name="p", message=SimpleNamespace(v=i * 3), origin="measured")},
             pose=_ORIGIN_POSE)
        for i in range(3)
    )
    session = Session(run_id="r", name="s", ticks=ticks)
    assert session.signal("p.v") == ((0, 0), (1, 3), (2, 6))


def test_session_is_immutable_mutating_a_returned_tick_or_its_ports_raises():
    """UT-B2-11: pass 2 must not be able to corrupt what pass 1 produced."""
    session = Session(run_id="r", name="s", ticks=_make_ticks(3))
    tick = session.at(0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        tick.index = 99
    with pytest.raises(TypeError):
        tick.ports["p"] = PortValue(name="p", message=b"x", origin="measured")
    with pytest.raises(dataclasses.FrozenInstanceError):
        session.ticks = ()


def test_has_simulated_output_is_false_for_a_stimulus_only_recording():
    """`AR-57`: `_make_ticks`' own default is `origin="measured"` on every
    tick -- exactly the "stimulus-only" shape (source/truth/mocked data,
    no stage ever executed against it)."""
    session = Session(run_id="r", name="s", ticks=_make_ticks(3))
    assert session.has_simulated_output() is False


def test_has_simulated_output_is_true_when_any_port_ever_says_simulated():
    """A single `origin="simulated"` value, on a single port at a single
    tick, is enough -- this asks "did any stage ever genuinely compute
    something here", not "does every port carry computed data"."""
    ticks = (
        Tick(index=0, t_ns=0, dt_ns=0,
             ports={"p": PortValue(name="p", message=b"", origin="measured")}, pose=_ORIGIN_POSE),
        Tick(index=1, t_ns=50_000_000, dt_ns=50_000_000,
             ports={"p": PortValue(name="p", message=b"", origin="measured"),
                    "q": PortValue(name="q", message=b"", origin="simulated")}, pose=_ORIGIN_POSE),
    )
    session = Session(run_id="r", name="s", ticks=ticks)
    assert session.has_simulated_output() is True


def test_has_simulated_output_is_false_for_an_empty_session():
    session = Session(run_id="r", name="s", ticks=())
    assert session.has_simulated_output() is False
