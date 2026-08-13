# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`resolve_library` — the ONE place a component library is resolved (P-5).

A pipeline's `impl: "dll:<stem>"` names a stem, not a file name. Expanding it
to a real file is a platform fact, and this module is the only place that
fact is consulted (sim_api_reference.md SS3.2, sim_portability.md P-5).
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from adas_sim.diagnostics.errors import EnvironmentError_


@dataclass(frozen=True, slots=True)
class LibraryResolution:
    """The full trace of one `resolve_library`-shaped search -- `sim
    doctor`'s own need (`DG-3`, `UT-D6-8`): "which library resolves, and by
    which pattern, listing every directory searched" must be answerable on
    SUCCESS too, which `resolve_library`'s raise-only-on-failure contract
    cannot do."""

    stem: str
    resolved: Path | None
    matched_directory: Path | None
    matched_pattern: str | None
    directories_searched: tuple[Path, ...]
    candidate_patterns: tuple[str, ...]


def resolve_library_report(stem: str, *, search: Sequence[Path], platform: str = sys.platform) -> LibraryResolution:
    """Same search `resolve_library` performs, but always returns -- never
    raises -- carrying which directory and pattern matched, or that none
    did, plus the full search trace either way."""
    candidates = _candidate_names(stem, platform=platform)
    for directory in search:
        for name in candidates:
            path = directory / name
            if path.is_file():
                return LibraryResolution(
                    stem=stem, resolved=path, matched_directory=directory, matched_pattern=name,
                    directories_searched=tuple(search), candidate_patterns=candidates,
                )
    return LibraryResolution(
        stem=stem, resolved=None, matched_directory=None, matched_pattern=None,
        directories_searched=tuple(search), candidate_patterns=candidates,
    )


def _candidate_names(stem: str, *, platform: str) -> tuple[str, ...]:
    if platform.startswith("win"):
        return (f"{stem}.dll",)
    return (f"lib{stem}.so", f"{stem}.so")


def resolve_library(
    stem: str, *, search: Sequence[Path], platform: str = sys.platform
) -> Path:
    """'df_sil' -> df_sil.dll | libdf_sil.so | df_sil.so, by platform.

    Searches `search` in order; within a directory, candidate names are tried
    in the order returned by `_candidate_names` (lib-prefixed before bare on
    Linux). Raises `EnvironmentError_` naming every pattern tried and every
    directory searched (N-8) so a pipeline file stays portable as written.
    """
    report = resolve_library_report(stem, search=search, platform=platform)
    if report.resolved is not None:
        return report.resolved
    where = ", ".join(str(directory) for directory in search) if search else "(no directories given)"
    raise EnvironmentError_(
        expected=f"stem '{stem}' as one of: {', '.join(report.candidate_patterns)}",
        found="none of those files exist",
        where=f"search directories: {where}",
        hint="build the component, or add its output directory to the search path",
    )
