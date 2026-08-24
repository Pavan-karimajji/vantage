# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`SW-0251`: reset mode and reset timing are two independent settings.
`ResetMode` (none / reset / reset-and-init) and `ResetWhen` (before the whole
batch / before each entry / before each section) are orthogonal -- a batch
face wires both, defaulting to `RESET_INIT` x `ENTRY`, the only combination
`SW-0251`'s own Accept clause names as making runs order-independent
(shuffling the recording list must not change any single run's own output).

`should_reset_before(...)` is the pure decision function `orchestrate/batch.py`
calls per entry -- it takes no I/O and performs no reset itself (a real
reset/init is `lifecycle.cpp::Transition`, `IMP-0085`, reached through the
per-worker subprocess boundary, not from here)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ResetMode(StrEnum):
    NONE = "none"
    RESET = "reset"
    RESET_INIT = "reset_init"


class ResetWhen(StrEnum):
    BATCH = "batch"       # once, before the whole batch
    ENTRY = "entry"        # before every recording
    SECTION = "section"    # before every named section (a sweep group, a list-file block)


@dataclass(frozen=True, slots=True)
class ResetPolicy:
    """Both settings, recorded together so a run directory's own spec
    (`orchestrate/artifacts.py`) states exactly what a reader needs to
    reproduce the order-(in)dependence a given run exhibited."""

    mode: ResetMode = ResetMode.RESET_INIT
    when: ResetWhen = ResetWhen.ENTRY


DEFAULT_RESET_POLICY = ResetPolicy()


def should_reset_before(policy: ResetPolicy, *, index: int, is_first_in_section: bool) -> bool:
    """`index` is the entry's position in the whole batch (0-based);
    `is_first_in_section` is whether this entry starts a new section
    (always `True` for `index == 0`, and for `ResetWhen.ENTRY`/`BATCH`
    every entry counts as its own section boundary trivially). `ResetMode.
    NONE` never resets regardless of timing -- the deliberate order-
    dependence escape hatch `SW-0251`'s own Accept clause names as the
    control case proving the test has power."""
    if policy.mode == ResetMode.NONE:
        return False
    if policy.when == ResetWhen.BATCH:
        return index == 0
    if policy.when == ResetWhen.ENTRY:
        return True
    # ResetWhen.SECTION
    return is_first_in_section
