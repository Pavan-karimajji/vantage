# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-A1 log-line test: UT-A1-8 (docs/sim_implementation_plan.md)."""

from __future__ import annotations

import pytest

from adas_sim.core.logging import Event, log


def test_log_emits_one_line_with_fields_in_the_fixed_order(capsys):
    """UT-A1-8: N-10's fixed field order, never multi-line."""
    log(Event.EXEC_OK, run="20260728T143012Z-9f3a1c04", tick=412, stage="df",
        port="df.aeb.outputs", dur_us=118)
    out = capsys.readouterr().err.strip()
    assert "\n" not in out
    assert (
        out.index("run=") < out.index("tick=") < out.index("stage=")
        < out.index("port=") < out.index("event=") < out.index("dur_us=")
    )


def test_log_rejects_an_event_outside_the_closed_enum():
    """UT-A1-8: an `event` outside the closed enum is a TypeError."""
    with pytest.raises(TypeError):
        log("exec_ok", run="20260728T143012Z-9f3a1c04")  # type: ignore[arg-type]


def test_log_flattens_a_multiline_message(capsys):
    """UT-A1-8: a multi-line `msg` is flattened, never wrapped."""
    log(Event.RUN_START, run="20260728T143012Z-9f3a1c04", msg="line one\nline two")
    out = capsys.readouterr().err.strip()
    assert "\n" not in out
    assert "msg=line one line two" in out
