# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`SW-0246`/`SW-0247`: two watchdogs, never one -- a run whose modules are
all within their processing threshold but whose process has stopped
responding is a different finding from a run that is genuinely still
computing, and `SYS-0186` calls the "still running" symptom *harder* to
diagnose than a crash precisely because one timer cannot tell the two apart.

`ProcessingWatchdog` fires when the time since the last observed *unit of
work* (a tick, a stage) exceeds its threshold. `ResponsivenessWatchdog`
fires when the time since the last observed *sign of life at all* (any
heartbeat, including one that is not a completed unit of work) exceeds its
own, independent threshold. Both are pollable, clock-injectable primitives
with no thread and no subprocess of their own -- a caller (`orchestrate/
batch.py`'s worker supervision, or a future interactive in-process run) drives `poll(now)` on
its own schedule and calls `heartbeat(now)` whenever it observes activity.

**Known integration gap, named rather than hidden:** wiring either watchdog
to a REAL `sim batch` subprocess needs a heartbeat channel across the
`simengine` process boundary that does not exist yet -- the same gap
`orchestrate/worker.py`'s own docstring names for `--checkpoint-json`
(no per-tick callback survives the `WP-15b` move to a `simengine`
subprocess). Both classes are complete and unit-tested against a simulated
clock; the missing piece is a producer of real heartbeats, not the consumer
logic here."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class WatchdogUnit(StrEnum):
    """`SW-0246`'s own "a threshold expressed with an explicit unit and one
    without it are both accepted, and the assumed unit is reported" --
    `parse_threshold` below is what accepts either form."""

    SECONDS = "s"
    MILLISECONDS = "ms"


#: `SW-0246`'s own default when a bare number carries no unit -- reported
#: alongside the parsed value so a caller can log which one was assumed.
DEFAULT_UNIT = WatchdogUnit.SECONDS


def parse_threshold(value: str | float) -> tuple[float, WatchdogUnit, bool]:
    """Returns `(seconds, unit, was_explicit)`. `"30"` / `30` parses as
    30 seconds, `unit assumed`; `"30s"`/`"1500ms"` parse with the unit
    stated explicitly."""
    if isinstance(value, (int, float)):
        return float(value), DEFAULT_UNIT, False
    text = value.strip()
    if text.endswith("ms"):
        return float(text[:-2]) / 1000.0, WatchdogUnit.MILLISECONDS, True
    if text.endswith("s"):
        return float(text[:-1]), WatchdogUnit.SECONDS, True
    return float(text), DEFAULT_UNIT, False


@dataclass(slots=True)
class _PollingWatchdog:
    """Shared shape: an interval to poll at, a threshold to compare the
    time-since-last-heartbeat against, and a fired flag latched once."""

    threshold_s: float
    poll_interval_s: float
    _last_heartbeat: float = field(default=0.0)
    _fired: bool = field(default=False)
    _fired_at: float | None = field(default=None)

    def heartbeat(self, now: float) -> None:
        """Records a sign of life at time `now`. Does not un-latch `fired`
        -- once a watchdog has fired the run is being aborted; a heartbeat
        arriving after that is a race with the abort, not a reprieve."""
        self._last_heartbeat = now

    def poll(self, now: float) -> bool:
        """Returns whether this watchdog is firing (latched: once `True`,
        every subsequent call also returns `True`)."""
        if not self._fired and (now - self._last_heartbeat) >= self.threshold_s:
            self._fired = True
            self._fired_at = now
        return self._fired

    @property
    def fired(self) -> bool:
        return self._fired

    @property
    def fired_at(self) -> float | None:
        return self._fired_at


class ProcessingWatchdog(_PollingWatchdog):
    """Per-module processing time (`SW-0246`) -- a caller calls `heartbeat`
    on every unit of work completed (a tick, a stage's own `exec()`); this
    fires when no unit of work has completed within `threshold_s`."""


class ResponsivenessWatchdog(_PollingWatchdog):
    """Whether the process remains responsive at all (`SW-0247`), independent
    of `ProcessingWatchdog` -- a caller calls `heartbeat` on ANY observed
    sign of life (a log line, a process-level ping), not only completed
    units of work. A run wedged inside one stage's `exec()` -- still
    responding to the OS, still writing nothing new -- fires
    `ProcessingWatchdog` but not this one; a run stuck in a kernel-level wait
    with no observable output at all fires this one too."""
