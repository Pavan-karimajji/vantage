# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`IMP-0206`/`IMP-0207`/`IMP-0208` (`SW-0206`..`SW-0208`) -- `resolve/bundle.
py::resolve_bundle` is a thin `Resolution[T]`-shaped wrapper (`ANL-SW-38`)
over the one real bundle resolver, `config.project.ProjectModel.resolve`
(the design's own package-rename table already lands `model/project.py` at
`config/project.py` -- there is no separate relocation for this row to make).

**Why `Resolution[ProjectModel]`, not `Resolution[Path]`** (the `SI-13`
skeleton's own pseudocode signature): `ProjectModel` already carries the
winning `bundle_dir` *and* the resolved `EgoModel`/`bundle_sha256`/
`bundle_origin` a caller actually needs -- wrapping only the directory would
throw that away and force a second call into `ProjectModel.resolve` to get
it back, which would call the real resolver twice per use and risk the two
calls disagreeing (`R-SIM-3a`'s whole point). `ProjectModel.bundle_dir` is
still reachable off `.chosen.bundle_dir` for a caller that only wants the
path.

This module calls `ProjectModel.resolve` exactly once and never
re-implements its explicit -> embedded -> library -> checkout walk: the
tiers passed to `order.ordered_tiers` below are trivial "is this the tier
that already won" checks, not a second resolution pass -- `ordered_tiers`
is only used to produce the shared `searched`/`rejected` shape (`ANL-SW-38`)
around a result already computed by the one real implementation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from adas_sim.config.project import BundleOrigin, ProjectModel
from adas_sim.resolve.order import Resolution, ordered_tiers

_TIER_ORDER: tuple[BundleOrigin, ...] = ("explicit", "embedded", "library", "checkout")


def resolve_bundle(
    *,
    recording: Path | None = None,
    library_dir: Path | None = None,
    explicit: Path | None = None,
    project: str = "base",
    force: Literal["embedded", "library", "checkout"] | None = None,
    known_project: str | None = None,
) -> Resolution[ProjectModel]:
    """One bundle per component per build (`R-SIM-3a`, `IMP-0206`),
    resolved module-relative by default with an explicit path always
    winning and a project mismatch only ever a warning (`IMP-0207`) --
    `ProjectModel.resolve`'s own already-correct behaviour, reported here
    in the shared `Resolution[T]` shape so `resolve_library`/`resolve_bundle`/
    `resolve_plugins` are mechanically the same kind of answer.
    """
    resolved = ProjectModel.resolve(
        recording=recording, library_dir=library_dir, explicit=explicit,
        project=project, force=force, known_project=known_project,
    )

    candidates = {"explicit": explicit, "embedded": recording, "library": library_dir}
    offered = tuple(_TIER_ORDER) if force is None else (force,)
    offered = tuple(tier for tier in offered if tier == "checkout" or candidates[tier] is not None)

    def thunk_for(tier: BundleOrigin):
        def thunk() -> ProjectModel | None:
            return resolved if resolved.bundle_origin == tier else None

        return thunk

    return ordered_tiers([(tier, thunk_for(tier)) for tier in offered])
