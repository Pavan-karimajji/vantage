# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`SI-11 graph` -- waiving a `BROKEN` `coherence.Finding` (`WP-20`
phase 3, `SW-0180`/`SW-0181`). A waiver requires a flag (`policy.
waivers_allowed`) AND a written reason -- an empty reason is refused the
same way an empty override reason would be elsewhere in this codebase
(`R-SIM-24`'s "every row carries a mandatory `why:`" discipline, applied
here to a run-time decision rather than a calibration file). A policy that
forbids waivers refuses one outright, raising `WaiverForbidden` -- carrying
`errors.py::EXIT_CODES["coherence"]`, the situational exit code
`diagnostics/errors.py`'s own docstring already reserves for "`WP-20`
coherence" (never modelled as a `SimError` subclass, per that module's own
design note: a situational code is a specific call site's own decision, not
a derived `Kind` default).

**Scoped to this file's own data and logic only** -- `SW-0180`'s "marks
permanently in the manifest, in every export and visibly in the player"
names three integration points (the run manifest, `WP-22`; an export,
`WP-18`/`WP-30`; the player, superseded to `viz`) that do not exist as
callers of `coherence.classify()`/this module yet, because nothing calls
`classify()` in a real run today -- `graph/modes.py` (phase 4) still
blocks/warns off the old one-hop `severed_chains()`. Wiring a waiver mark
into those three surfaces is real, separate work belonging to whichever
`WP` first makes coherence classification part of an actual run; this
module gives that future caller a `Waiver` value to carry, tested standalone
against `coherence.Finding`/`Verdict` directly.
"""

from __future__ import annotations

from dataclasses import dataclass

from adas_sim.diagnostics.errors import EXIT_CODES
from adas_sim.graph.coherence import Finding, Verdict


@dataclass(frozen=True, slots=True)
class Policy:
    """`SW-0181`: whether a waiver may be granted at all. `waivers_allowed`
    defaults `True` -- a policy that never mentions waivers behaves as
    today's ungoverned codebase does; forbidding them is an explicit,
    stated choice, not a silent default flip (`NR-SIM-4`)."""

    waivers_allowed: bool = True


@dataclass(frozen=True, slots=True)
class Waiver:
    """A granted waiver, permanent once created -- there is no un-waive
    (`SW-0180`'s own "marks permanently"): a caller wanting a different
    outcome re-classifies and grants a new decision, it does not mutate
    this one."""

    finding: Finding
    reason: str


class WaiverForbidden(Exception):
    """`SW-0181`: raised when `policy.waivers_allowed` is `False`. Carries
    the situational `coherence` exit code (`EXIT_CODES["coherence"]`, `3`)
    -- the process-level "does not execute" half of `SW-0181`'s Accept
    clause is a future CLI call site's own responsibility (nothing calls
    `coherence.classify()` in a real run yet, see this module's own top
    note); this class exists so that caller has an exit code to read the
    day it exists, rather than inventing one at the point of use."""

    exit_code = EXIT_CODES["coherence"]

    def __init__(self, reason_attempted: str) -> None:
        self.reason_attempted = reason_attempted
        super().__init__(f"waivers are forbidden by policy (attempted reason: {reason_attempted!r})")


def waive(finding: Finding, reason: str, *, policy: Policy = Policy()) -> Waiver:
    """`SW-0180`: a `BROKEN` finding is waived only with both a flag
    (`policy.waivers_allowed`) and a non-empty written reason -- checked in
    that order, since a forbidding policy makes the reason moot. An
    `ORPHAN`/`NORMAL` "finding" (nothing to waive -- `ORPHAN` already never
    blocks, `SW-0182`) is refused with the same `ValueError` an empty reason
    gets: there is no code path that waives without both a real broken
    finding and a real written reason."""
    if not policy.waivers_allowed:
        raise WaiverForbidden(reason)
    if finding.verdict is not Verdict.BROKEN:
        raise ValueError(f"nothing to waive: verdict is {finding.verdict.value}, not broken")
    if not reason.strip():
        raise ValueError("a waiver requires a non-empty written reason")
    return Waiver(finding=finding, reason=reason)


def still_blocking(findings: tuple[Finding, ...], waivers: tuple[Waiver, ...]) -> tuple[Finding, ...]:
    """`SW-0182`'s companion half for `BROKEN`: every finding a waiver does
    NOT cover, in the same order `coherence.classify()` returned them --
    what a future run-blocking caller (`graph/modes.py`, phase 4) actually
    checks is empty before proceeding. `ORPHAN` findings are never
    blocking regardless of waivers (`SW-0182`) and are excluded here too."""
    waived = {waiver.finding for waiver in waivers}
    return tuple(f for f in findings if f.verdict is Verdict.BROKEN and f not in waived)
