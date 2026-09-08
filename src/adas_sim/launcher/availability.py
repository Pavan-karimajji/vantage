# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`SI-22 launcher` -- `check_availability` (`WP-28`, `IMP-0344`): shown
BEFORE launch, never discovered as a load failure after (`SW-0344`'s own
`Accept`). Wraps `resolve.library.resolve_library_report`, a plain
file-existence probe against the candidate `dll:`/`stubdll:` file names for
this platform -- **no `dlopen`, ever** (`UT-LNC-03`'s "count load attempts"
must read zero).

**`version` is honestly `"unknown"`.** Reading a real version means loading
the manifest (`adasManifest()`), which this module refuses to do; a
non-loading version source is `IMP-0205`/`WP-21`'s own `library.py::
is_available` plus `resolve/bundle.py`, neither built yet. Writing a
plausible-looking version here would be exactly the guess `R-SIM-25`/
`NR-SIM-4` forbid -- so it stays `"unknown"` until `WP-21` lands a real one,
recorded here rather than invented."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from adas_sim.resolve.library import resolve_library_report

if TYPE_CHECKING:
    from adas_sim.launcher.model import Selection

#: `_resolve_components`'s own closed set (`graph/pipeline.py`) -- only these
#: two kinds resolve to a real file this probe can check; `stub:`/`legacy:`
#: stages are excluded below because `Pipeline.load` (no `components=`, the
#: shape a written run config loads through) cannot resolve either kind at
#: all, so reporting either "available" would be exactly the false-before
#: signal `SW-0344` exists to prevent.
_RESOLVABLE_KINDS = ("dll", "stubdll")


@dataclass(frozen=True, slots=True)
class ModuleAvailability:
    """One stage's answer, per `SW-0344`'s own field list. `reason` is `""`
    exactly when `available` -- `feasible.CutFeasibility`'s own convention,
    reused here so a caller checks one field the same way in both places."""

    stage: str
    impl: str | None
    available: bool
    reason: str
    version: str = "unknown"


def _unavailable(stage: str, impl: str | None, reason: str) -> ModuleAvailability:
    return ModuleAvailability(stage=stage, impl=impl, available=False, reason=reason)


def check_availability(stage: str, impl: str | None, *, search: Sequence[Path] = ()) -> ModuleAvailability:
    """`IMP-0344`: `stage`'s declared `impl:` resolved against `search`
    (the same `search:` `resolve_library` itself takes) with no load
    performed."""
    if not impl:
        return _unavailable(stage, impl, "stage declares no impl: -- nothing to resolve")
    kind, _, ref = impl.partition(":")
    if kind not in _RESOLVABLE_KINDS:
        return _unavailable(
            stage, impl,
            f"impl kind {kind!r} has no resolvable binary "
            f"(only {'/'.join(k + ':' for k in _RESOLVABLE_KINDS)} do)",
        )
    report = resolve_library_report(ref, search=search)
    if report.resolved is None:
        where = ", ".join(str(d) for d in report.directories_searched) or "(no directories given)"
        return _unavailable(
            stage, impl,
            f"no binary for this platform: tried {', '.join(report.candidate_patterns)} in {where}",
        )
    return ModuleAvailability(stage=stage, impl=impl, available=True, reason="")


def check_all(selection: "Selection") -> tuple[ModuleAvailability, ...]:
    """`IMP-0344`: every declared stage's availability, `selection.search`
    forwarded to each -- the launcher's own "show before launch" table."""
    pipeline = selection.working_pipeline
    return tuple(check_availability(s.name, s.impl, search=selection.search) for s in pipeline.stages)
