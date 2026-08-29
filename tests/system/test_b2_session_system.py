# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B2 system tests: ST-B2-1, ST-B2-2 (docs/sim_implementation_plan.md).

**`ST-B2-3` (rewind/recompute-from-zero, exercised through
`player.panels.transport.Transport`) retired with it** (`SM-12`,
`docs/VIZ_Sync_Plan_v0.1.md`): that panel-state module was part of the
Python scene/render/player tree. `R-SIM-17`'s own rewind/recompute rule is
`viz`'s own C++ player's concern now, not this module's."""

from __future__ import annotations

import random
import time
from pathlib import Path

import pytest

from adas_sim.core.runner import build_session_from_recording
from adas_sim.session.session import Session
from adas_sim.session.tick import Pose2D, PortValue, Tick

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
