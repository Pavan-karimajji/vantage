# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 pass-1 hook tests: the `on_progress`/`is_cancelled` plumbing
`render/viewer.py`'s `_SessionLoadWorker` drives, exercised here without Qt
since `core/` must stay Qt-free (`UT-B3-17`)."""

from __future__ import annotations

from pathlib import Path

import pytest

from adas_sim.core.runner import LoadCancelled, build_session_from_recording

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
TINY_MCAP = FIXTURES_DIR / "tiny.mcap"


def test_on_progress_reports_every_tick_in_order():
    seen = []
    session = build_session_from_recording(TINY_MCAP, on_progress=lambda done, total: seen.append((done, total)))
    assert len(session) == 20
    assert seen == [(i, 20) for i in range(1, 21)]


def test_cancelling_mid_load_raises_and_builds_no_session():
    """UT-B3-16's own reasoning at the core level: a half-built session must
    never be returned, so cancellation is an exception, not a partial value."""
    calls = {"n": 0}

    def is_cancelled():
        calls["n"] += 1
        return calls["n"] > 5  # cancel partway through the 20 ticks

    with pytest.raises(LoadCancelled):
        build_session_from_recording(TINY_MCAP, is_cancelled=is_cancelled)
