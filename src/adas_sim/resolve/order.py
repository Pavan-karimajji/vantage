# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`IMP-0214` (`SW-0214`) -- the one shared "ordered tiers, report the tier
that won" helper every `resolve/` resolver funnels through (`ANL-SW-38`):
`library.py::resolve_library_resolution`, `bundle.py::resolve_bundle`,
`plugins.py::resolve_plugins`. Without this, three near-identical
explicit -> embedded -> library -> checkout walks drift independently --
exactly the shape `resolve/library.py`, `config/project.py::ProjectModel.
resolve` and `resolve/plugins.py::PluginBundle.resolve` already had, by
convention rather than by construction.

`Resolution[T]` carries the outcome PLUS the full trace: which tier won
(or none), every tier tried, and why each rejected candidate lost -- the
same "answerable on success too" need `resolve/library.py::LibraryResolution`
already names for `sim doctor` (`DG-3`).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Resolution(Generic[T]):
    """One resolver's outcome, in one shape (`ANL-SW-38`).

    `chosen` is `None` iff no tier resolved -- `tier` is then also `None`.
    `searched` names every tier attempted, in order; `rejected` pairs a
    tier name with why it did not resolve (a tier that never got tried
    because an earlier one already won is in neither `searched` nor
    `rejected` -- `ordered_tiers` stops at the first success, same
    short-circuit `ProjectModel.resolve`/`PluginBundle.resolve` already
    use).
    """

    chosen: T | None
    tier: str | None
    searched: tuple[str, ...]
    rejected: tuple[tuple[str, str], ...]


def ordered_tiers(tiers: Sequence[tuple[str, Callable[[], T | None]]]) -> Resolution[T]:
    """Tries each `(tier_name, thunk)` in order; the first thunk to return
    a non-`None` value wins. A thunk that raises is treated as a rejection
    naming the exception, not a crash of the whole resolution -- a single
    malformed candidate must not stop the search for a later, valid one.
    """
    searched: list[str] = []
    rejected: list[tuple[str, str]] = []
    for name, thunk in tiers:
        searched.append(name)
        try:
            value = thunk()
        except Exception as exc:  # noqa: BLE001 -- a rejected candidate, not a crash
            rejected.append((name, str(exc)))
            continue
        if value is not None:
            return Resolution(chosen=value, tier=name, searched=tuple(searched), rejected=tuple(rejected))
        rejected.append((name, "no candidate"))
    return Resolution(chosen=None, tier=None, searched=tuple(searched), rejected=tuple(rejected))
