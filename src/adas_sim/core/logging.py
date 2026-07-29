# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The fixed-format log line (N-10, sim_api_reference.md §2.5)."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from enum import StrEnum

# Level is derived from `event`, not a caller-supplied parameter (the
# api-reference signature has none): the fixed vocabulary already says how
# serious a line is, so asking the caller to also pick a level would be a
# second place for that judgement to drift from the first.
_WARN_EVENTS = frozenset({"port_missing", "port_overridden", "degrade"})
_ERROR_EVENTS = frozenset({"exec_fail", "expect_fail", "bundle_mismatch"})


class Event(StrEnum):
    """The closed `event=` vocabulary (N-10). Adding a value is a review."""

    RUN_START = "run_start"
    RUN_END = "run_end"
    STAGE_INIT = "stage_init"
    STAGE_SHUTDOWN = "stage_shutdown"
    EXEC_OK = "exec_ok"
    EXEC_FAIL = "exec_fail"
    PORT_MISSING = "port_missing"
    PORT_OVERRIDDEN = "port_overridden"
    DEGRADE = "degrade"
    EXPECT_PASS = "expect_pass"
    EXPECT_FAIL = "expect_fail"
    BUNDLE_MISMATCH = "bundle_mismatch"


def _level_for(event: Event) -> str:
    if event in _ERROR_EVENTS:
        return "ERROR"
    if event in _WARN_EVENTS:
        return "WARN"
    return "INFO"


def log(
    event: Event,
    *,
    run: str,
    tick: int | None = None,
    stage: str | None = None,
    port: str | None = None,
    dur_us: int | None = None,
    msg: str = "",
    **fields: object,
) -> None:
    """Emit ONE line, fields in fixed order (N-10). `msg` comes last and may
    never replace a field."""
    if not isinstance(event, Event):
        raise TypeError(f"log() event must be an adas_sim.core.logging.Event member, got {event!r}")

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    parts = [timestamp, f"{_level_for(event):<5}", f"run={run}"]
    if tick is not None:
        parts.append(f"tick={tick}")
    if stage is not None:
        parts.append(f"stage={stage}")
    if port is not None:
        parts.append(f"port={port}")
    parts.append(f"event={event.value}")
    if dur_us is not None:
        parts.append(f"dur_us={dur_us}")
    for key in sorted(fields):
        parts.append(f"{key}={fields[key]}")
    if msg:
        flattened = " ".join(msg.split())
        parts.append(f"msg={flattened}")

    print(" ".join(parts), file=sys.stderr)
