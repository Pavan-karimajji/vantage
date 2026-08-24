# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`SW-0252`/`SW-0253`: a read error's behaviour is selected from a closed
set, and a retried read is bounded and recorded.

`ReadError` is `switch`-equivalent -- no default arm, so a new failure mode
forces a real decision at every call site rather than silently falling into
whichever behaviour happened to be last in an `if` chain. `retry` bounds a
retried read by wall-clock duration (never an unbounded loop, `SW-0253`'s own
"an unbounded retry converts a damaged file into a hung campaign") and
returns a `RetryOutcome` recording every attempt made, so a caller can write
it into the run's own artifact directory."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TypeVar


class ReadError(StrEnum):
    STOP = "stop"                          # refuse the whole operation
    SKIP_ENTRY = "skip_entry"               # drop this one recording, continue
    ABORT_BATCH = "abort_batch"             # end the batch, keep results so far
    SKIP_PACKAGE = "skip_package"           # drop this one damaged package within a recording


@dataclass(frozen=True, slots=True)
class RetryOutcome:
    attempts: int
    succeeded: bool
    elapsed_s: float
    #: `()` when `succeeded`; one entry per failed attempt otherwise.
    errors: tuple[str, ...] = field(default_factory=tuple)


_T = TypeVar("_T")


def retry(
    fn: Callable[[], _T], *, bound_s: float, retry_interval_s: float = 0.1, clock: Callable[[], float] = time.monotonic,
) -> tuple[_T | None, RetryOutcome]:
    """Calls `fn()` until it succeeds (returns without raising) or `bound_s`
    of wall clock has elapsed -- **no backoff, no unbounded loop**: the
    interval between attempts is fixed (`retry_interval_s`), and the bound is
    on total elapsed time, not attempt count, so a caller states a real time
    budget rather than guessing a count for an unknown-cost operation.
    Returns `(result, outcome)`; `result` is `None` when every attempt
    failed, matching this module's own honesty discipline (`R-SIM-25`) --
    a caller distinguishes "no result" from "not tried" via `outcome.
    attempts == 0`, which never happens here (at least one attempt is
    always made)."""
    start = clock()
    errors: list[str] = []
    attempts = 0
    while True:
        attempts += 1
        try:
            result = fn()
        except Exception as exc:  # noqa: BLE001 -- a read error is exactly what this bounds
            errors.append(f"{type(exc).__name__}: {exc}")
            elapsed = clock() - start
            if elapsed >= bound_s:
                return None, RetryOutcome(attempts=attempts, succeeded=False, elapsed_s=elapsed, errors=tuple(errors))
            time.sleep(min(retry_interval_s, max(0.0, bound_s - elapsed)))
            continue
        return result, RetryOutcome(attempts=attempts, succeeded=True, elapsed_s=clock() - start, errors=tuple(errors))
