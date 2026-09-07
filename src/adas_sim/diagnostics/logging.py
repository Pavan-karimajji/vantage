# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The fixed-format log line (N-10, sim_api_reference.md §2.5)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone

from adas_sim.diagnostics.events import Event

# Level is derived from `event`, not a caller-supplied parameter (the
# api-reference signature has none): the fixed vocabulary already says how
# serious a line is, so asking the caller to also pick a level would be a
# second place for that judgement to drift from the first.
_WARN_EVENTS = frozenset({"port_missing", "port_overridden", "degrade"})
_ERROR_EVENTS = frozenset({"exec_fail", "expect_fail", "bundle_mismatch"})

#: `WP-05` (`SW-0041`): occurrences of one key before de-duplication engages
#: -- below it, `log()` behaves exactly as it always has, one line per
#: call. No document commits to a specific number (unlike a requirement's
#: own `Accept` threshold, `R-REQ-10`); this is an implementation default.
FLOOD_THRESHOLD = 10


@dataclass
class _DedupEntry:
    """`WP-05` (`SW-0040`): one key's accumulated state -- `occurrences`
    counts every call sharing this key, including the ones printed before
    the threshold engaged; `announced` guards `Event.DEDUP_STARTED` to
    exactly one emission per key (`SW-0041`)."""

    occurrences: int = 0
    announced: bool = False


#: Keyed by `_dedupe_key(...)`. Module-level because `log()` has always
#: been a free function with no caller-held state to attach this to.
_dedup_state: dict[tuple, _DedupEntry] = {}


def _level_for(event: Event) -> str:
    if event in _ERROR_EVENTS:
        return "ERROR"
    if event in _WARN_EVENTS:
        return "WARN"
    return "INFO"


def _dedupe_key(
    event: Event, *, run: str, stage: str | None, port: str | None, msg: str, **fields: object,
) -> tuple:
    """`WP-05` (`SW-0039`): identical messages share this key; any
    difference in `event`/`run`/`stage`/`port`/`msg`/an extra field yields
    a different one. Built generically over `log()`'s own keyword
    vocabulary (`**fields` included) so a field added to `log()` later is
    automatically part of the key, never silently ignored. `tick`/`dur_us`
    are deliberately excluded -- `log()` never forwards them here, because
    those vary on every occurrence of what is still "the same message"
    (`F-FLOOD`'s own point: one component, one warning, every tick).
    Including either would mean nothing ever de-duplicates."""
    return (event, run, stage, port, msg, tuple(sorted(fields.items())))


def _emit_line(
    event: Event, *, run: str, tick: int | None, stage: str | None, port: str | None,
    dur_us: int | None, msg: str, **fields: object,
) -> None:
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
    never replace a field.

    `WP-05`: below `FLOOD_THRESHOLD` occurrences of one key
    (`_dedupe_key`), this is exactly the line-per-call behaviour above has
    always had. At the threshold, one `Event.DEDUP_STARTED` line announces
    it (`SW-0041`) and this call's own line is the last one printed --
    every further occurrence of the same key accumulates silently
    (`_dedup_state`) until `flush_deduped()` reports the total (`SW-0040`).
    """
    if not isinstance(event, Event):
        raise TypeError(f"log() event must be an adas_sim.diagnostics.logging.Event member, got {event!r}")

    key = _dedupe_key(event, run=run, stage=stage, port=port, msg=msg, **fields)
    entry = _dedup_state.setdefault(key, _DedupEntry())
    entry.occurrences += 1

    if entry.occurrences > FLOOD_THRESHOLD:
        return  # suppressed -- counted only, reported at flush

    _emit_line(event, run=run, tick=tick, stage=stage, port=port, dur_us=dur_us, msg=msg, **fields)

    if entry.occurrences == FLOOD_THRESHOLD and not entry.announced:
        entry.announced = True
        _emit_line(
            Event.DEDUP_STARTED, run=run, tick=tick, stage=stage, port=port, dur_us=None,
            msg=f"de-duplicating repeated message (event={event.value}, threshold={FLOOD_THRESHOLD})",
        )


def flush_deduped() -> None:
    """`WP-05` (`SW-0040`): one entry per key that crossed `FLOOD_THRESHOLD`,
    carrying its total occurrence count -- the flush half of `log()`'s own
    gate above. A key that never crossed the threshold needs no flush
    entry: every one of its occurrences was already printed in full.
    Clears each flushed key, so a second flush with no further occurrences
    reports nothing new."""
    for key, entry in list(_dedup_state.items()):
        if entry.occurrences > FLOOD_THRESHOLD:
            event, run, stage, port, msg, extra_items = key
            _emit_line(
                event, run=run, tick=None, stage=stage, port=port, dur_us=None, msg=msg,
                occurrences=entry.occurrences, **dict(extra_items),
            )
        del _dedup_state[key]
