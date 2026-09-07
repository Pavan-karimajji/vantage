# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""PARITY `WP-05` tests: `UT-diaglog-01`..`UT-diaglog-03`
(`docs/v2/parity/PARITY_Test_Spec.md` §5.9).
"""

from __future__ import annotations

import adas_sim.diagnostics.logging as logging_mod
from adas_sim.diagnostics.events import Event
from adas_sim.diagnostics.logging import FLOOD_THRESHOLD, _dedupe_key, flush_deduped, log


def setup_function() -> None:
    """Each test gets a clean dedup state -- `_dedup_state` is module-level
    because `log()` has always been a free function, so cross-test
    contamination is a hygiene concern the tests themselves must guard."""
    logging_mod._dedup_state.clear()


def test_the_key_distinguishes_what_differs_ut_diaglog_01():
    """UT-diaglog-01."""
    key_a = _dedupe_key(Event.PORT_MISSING, run="r1", stage="df", port="p", msg="m")
    key_a_again = _dedupe_key(Event.PORT_MISSING, run="r1", stage="df", port="p", msg="m")
    assert key_a == key_a_again  # .c1: identical messages share a key

    variants = [
        _dedupe_key(Event.DEGRADE, run="r1", stage="df", port="p", msg="m"),  # event differs
        _dedupe_key(Event.PORT_MISSING, run="r2", stage="df", port="p", msg="m"),  # run differs
        _dedupe_key(Event.PORT_MISSING, run="r1", stage="other", port="p", msg="m"),  # stage differs
        _dedupe_key(Event.PORT_MISSING, run="r1", stage="df", port="q", msg="m"),  # port differs
        _dedupe_key(Event.PORT_MISSING, run="r1", stage="df", port="p", msg="other"),  # msg differs
        _dedupe_key(Event.PORT_MISSING, run="r1", stage="df", port="p", msg="m", extra="x"),  # extra field
    ]
    assert len(set(variants)) == len(variants)  # .c2: every variant is a distinct key
    assert key_a not in variants


def test_the_count_equals_the_occurrences_ut_diaglog_02(capsys):
    """UT-diaglog-02."""
    n = FLOOD_THRESHOLD + 5
    for _ in range(n):
        log(Event.DEGRADE, run="ut-diaglog-02", stage="df")
    flush_deduped()

    out = capsys.readouterr().err
    aggregate_lines = [line for line in out.splitlines() if "occurrences=" in line]
    assert len(aggregate_lines) == 1  # .c1: one entry, not N
    assert f"occurrences={n}" in aggregate_lines[0]  # .c1: its count reads N


def test_the_crossing_is_announced_once_ut_diaglog_03(capsys):
    """UT-diaglog-03."""
    for _ in range(FLOOD_THRESHOLD):
        log(Event.DEGRADE, run="ut-diaglog-03-above", stage="df")
    out = capsys.readouterr().err
    announcements = [line for line in out.splitlines() if "event=dedup_started" in line]
    assert len(announcements) == 1  # .c1: exactly one
    assert "df" in announcements[0]
    assert str(FLOOD_THRESHOLD) in announcements[0]

    for _ in range(FLOOD_THRESHOLD - 1):
        log(Event.DEGRADE, run="ut-diaglog-03-below", stage="df")
    out = capsys.readouterr().err
    assert "event=dedup_started" not in out  # .c2: none below the threshold
