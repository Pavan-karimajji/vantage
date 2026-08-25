# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`SW-0128`: a headless run may exit early at a declared severity threshold
-- `--exit-on {exception,error,alert,warning}`. The threshold in force is
returned alongside the verdict so a caller (`orchestrate/batch.py`'s per-run
worker, or a future `sim run`/`sim resim` wiring) can write it into the
run's own artifact directory (`orchestrate/artifacts.py`) and the exit code
reflects the triggering severity -- never a bare non-zero."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class Severity(IntEnum):
    """Ordered low -> high so `>=` compares thresholds directly. `SW-0128`'s
    own closed vocabulary -- adding a fifth value is a requirement change,
    not a code change."""

    WARNING = 0
    ALERT = 1
    ERROR = 2
    EXCEPTION = 3


#: The four values `--exit-on` recognizes, spelled exactly as the CLI flag
#: does (SW-0128's own Shall clause) -- a typo fails loudly via `Severity[...]`
#: rather than silently picking a neighbour.
EXIT_ON_CHOICES = tuple(s.name.lower() for s in Severity)


@dataclass(frozen=True, slots=True)
class SeverityVerdict:
    """Whether a run should stop, and why -- `exit_code` is `0` when nothing
    breached the threshold, else `1` (never merged with a `batch.py`
    outcome's own crash/timeout exit codes, which are a different question:
    this is about a run's *own* logged events, not its process's survival)."""

    threshold: Severity
    triggered: Severity | None
    should_exit: bool
    exit_code: int


#: `IMP-0128`: the real event source, decided 2026-08-25 -- every
#: `diagnostics.errors.SimError.kind` maps to a `Severity`, so a caught
#: exception's own already-closed taxonomy is what `--exit-on` gates
#: against, rather than inventing a second, parallel event vocabulary.
#: `"authoring"` (a config mistake, usually isolated to one recording) is
#: the mildest; `"internal"` (a framework bug, `InternalError`'s own
#: "anything uncaught is this by definition") is the worst. Nothing maps to
#: `WARNING` -- no `SimError` kind is ever merely a warning (a raised
#: exception already ended that run); `--exit-on warning` still works
#: correctly (`evaluate`/`observe`'s own `>=` comparison), it simply never
#: sees an event AT that level from this source.
_SEVERITY_OF_KIND = {
    "authoring": Severity.ALERT,
    "environment": Severity.ERROR,
    "contract": Severity.ERROR,
    "internal": Severity.EXCEPTION,
}


def severity_for_kind(kind: str) -> Severity | None:
    """`None` for an empty or unrecognized `kind` (no error occurred, or a
    kind outside the closed `SimError` taxonomy) -- never a guessed
    severity (`R-SIM-25`)."""
    return _SEVERITY_OF_KIND.get(kind)


def parse_exit_on(value: str) -> Severity:
    """Raises `KeyError`-shaped `ValueError` naming the bad value and the
    closed set, rather than defaulting -- `SW-0128`'s "threshold... with no
    default" discipline, matching `readerror.py::ReadError`'s own."""
    try:
        return Severity[value.upper()]
    except KeyError as exc:
        raise ValueError(f"--exit-on {value!r} not in {EXIT_ON_CHOICES}") from exc


def evaluate(events: list[Severity], threshold: Severity) -> SeverityVerdict:
    """`events` is every severity a run logged, in the order they occurred.
    The first event at or above `threshold` is the trigger -- `SW-0128`'s
    own Accept clause ("the run's exit code reflects the triggering
    severity")."""
    for event in events:
        if event >= threshold:
            return SeverityVerdict(threshold=threshold, triggered=event, should_exit=True, exit_code=1)
    return SeverityVerdict(threshold=threshold, triggered=None, should_exit=False, exit_code=0)


class SeverityGate:
    """The incremental form `evaluate` above generalizes over: a caller
    logging events one at a time (a real run in progress) calls `observe`
    per event and gets told, immediately, whether this is the one that ends
    the run -- rather than collecting every event first and asking after
    the fact, which is what "terminates early" (`SW-0128`'s own wording)
    requires."""

    def __init__(self, threshold: Severity) -> None:
        self.threshold = threshold
        self.triggered: Severity | None = None

    def observe(self, event: Severity) -> bool:
        """Returns `True` the first time `event` reaches `threshold`; a gate
        already triggered stays triggered (`self.triggered` unchanged) and
        keeps returning `True` -- a caller stops on the first `True`, so a
        repeat report is informational only."""
        if self.triggered is None and event >= self.threshold:
            self.triggered = event
        return self.triggered is not None

    def verdict(self) -> SeverityVerdict:
        return SeverityVerdict(
            threshold=self.threshold, triggered=self.triggered,
            should_exit=self.triggered is not None, exit_code=1 if self.triggered is not None else 0,
        )
