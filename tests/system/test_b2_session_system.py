# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B2 system tests: ST-B2-1, ST-B2-2, ST-B2-3 (docs/sim_implementation_plan.md)."""

from __future__ import annotations

import random
import time
from pathlib import Path

import pytest

from adas_sim.core.runner import build_session_from_recording
from adas_sim.session.session import Session
from adas_sim.session.tick import Pose2D, PortValue, Tick
from adas_sim.player.panels.transport import ResumeOption, Transport

SIM_ROOT = Path(__file__).resolve().parent.parent.parent
MODULES_ROOT = SIM_ROOT.parent
DF_TESTRUNS = MODULES_ROOT / "df" / "tests" / "carla_testruns"

_ORIGIN_POSE = Pose2D(x_m=0.0, y_m=0.0, yaw_rad=0.0)


def _make_session(count: int) -> Session:
    ticks = tuple(
        Tick(index=i, t_ns=i * 50_000_000, dt_ns=50_000_000 if i else 0,
             ports={"p": PortValue(name="p", message=bytes([i % 256]), origin="measured")}, pose=_ORIGIN_POSE)
        for i in range(count)
    )
    return Session(run_id="r", name="s", ticks=ticks)


def test_one_hundred_random_seeks_on_a_thousand_plus_tick_session_are_correct():
    """ST-B2-1."""
    session = _make_session(1500)
    rng = random.Random(0)
    for _ in range(100):
        t_ns = rng.randint(0, session.at(len(session) - 1).t_ns + 10_000_000)
        index = session.seek_ns(t_ns)
        tick = session.at(index)
        assert tick.t_ns <= t_ns
        if index + 1 < len(session):
            assert session.at(index + 1).t_ns > t_ns


def test_pass_1_over_the_largest_existing_recording_is_timed_not_asserted():
    """ST-B2-2: recorded as a number, not asserted as a limit until a
    baseline exists."""
    if not DF_TESTRUNS.is_dir():
        pytest.skip("modules/df/tests/carla_testruns is absent (partial clone)")
    recordings = sorted(DF_TESTRUNS.rglob("*.mcap"), key=lambda p: p.stat().st_size, reverse=True)
    if not recordings:
        pytest.skip("no recordings found under modules/df/tests/carla_testruns")
    largest = recordings[0]

    start = time.perf_counter()
    session = build_session_from_recording(largest)
    elapsed_s = time.perf_counter() - start

    print(f"\nST-B2-2: pass 1 over {largest.name} ({len(session)} ticks) took {elapsed_s:.3f}s")
    assert len(session) > 0


def test_rewind_then_recompute_from_zero_is_exact():
    """ST-B2-3: recomputing to tick N reproduces the original tick N
    byte-for-byte on a deterministic resim.

    **Scoping note.** In Phase B there is no real SUT execution yet (no C++,
    no DLL) -- `Session.ticks` is pre-built once from the recording and never
    mutated, so `session.at(150) == session.at(150)` would hold trivially
    even with a broken `Transport`. What is genuinely testable now is that
    `resume(RECOMPUTE_FROM_ZERO)` drives a **deterministic re-execution
    sequence**: the exact same positions, in the exact same order, on the
    second pass as the first. The stronger claim -- that re-*computed* tick
    data is byte-identical -- needs a real pipeline that can produce new
    data on each run, which does not exist until `S-C1+`.
    """
    session = _make_session(200)
    visited: list[int] = []

    class RecordingExec:
        def __init__(self) -> None:
            self.position = 0

        def __call__(self, n, on_progress, cancel) -> int:
            target = min(self.position + n, len(session) - 1)
            while self.position < target and not cancel.cancelled:
                self.position += 1
                visited.append(self.position)
                on_progress(self.position, target)
            return self.position

    exec_fn = RecordingExec()
    transport = Transport(session, exec_fn)
    transport.advance(150)
    first_pass_sequence = list(visited)

    transport.step_back(50)
    transport.resume(ResumeOption.RECOMPUTE_FROM_ZERO)
    assert transport.head_tick == 0 and transport.cursor == 0
    exec_fn.position = 0  # a real SUT resets its own state on recompute
    visited.clear()
    transport.advance(150)
    second_pass_sequence = list(visited)

    assert second_pass_sequence == first_pass_sequence
    assert transport.head_tick == 150
