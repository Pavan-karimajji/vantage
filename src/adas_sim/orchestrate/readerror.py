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
from pathlib import Path
from typing import TypeVar

from adas_sim.plugins.registry import reader_for


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


def _open_and_probe(recording: Path, on_read_error: ReadError | str) -> int:
    """`IMP-0252`/`IMP-0253`: a genuine Python-side read of `recording`,
    proving the file opens and parses -- `.topics()` alone (schema/
    provenance, no full `messages()` decode). Returns the count of damaged
    packages (mcap chunks) found and skipped, always `0` under any policy
    other than `SKIP_PACKAGE` (they never pay for the extra chunk-decode
    pass) and `0` for a codec with no such concept (`check_faults` absent,
    `R-SIM-14`'s "a missing capability degrades explicitly," never a
    guess). A file whose EVERY chunk is corrupted has nothing left to
    skip-and-continue -- that is whole-file damage, raised here so the
    caller's own retry/fail path handles it exactly as it does for every
    other policy. `reader.close()` in `finally` means a retried attempt
    never leaks a handle."""
    reader = reader_for(recording)
    try:
        reader.topics()
        if on_read_error != ReadError.SKIP_PACKAGE.value:
            return 0
        check_faults = getattr(reader, "check_faults", None)
        if check_faults is None:
            return 0
        faults = check_faults()
        if faults.total > 0 and faults.corrupted == faults.total:
            raise OSError(f"every one of {faults.total} package(s) in {recording} is damaged")
        return faults.corrupted
    finally:
        reader.close()


def probe_recording(
    recording: Path, *, on_read_error: ReadError | str, bound_s: float,
) -> tuple[int, RetryOutcome]:
    """`orchestrate/worker.py`'s own pre-flight, extracted so it is directly
    testable against a real damaged-chunk fixture with no `Pipeline.load`/
    engine invocation needed. `(skipped_packages, outcome)` -- `skipped_
    packages` is `0` when `outcome.succeeded` is `False` (nothing was
    read), matching `retry`'s own "no result" convention."""
    result, outcome = retry(lambda: _open_and_probe(recording, on_read_error), bound_s=bound_s)
    return (result if result is not None else 0), outcome
