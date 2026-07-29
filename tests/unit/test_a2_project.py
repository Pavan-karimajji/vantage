# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-A2 `ProjectModel.resolve` tests: UT-A2-7, UT-A2-10
(docs/sim_implementation_plan.md)."""

from __future__ import annotations

from pathlib import Path

import pytest

from adas_sim.core.errors import ProvenanceWarning
from adas_sim.model.project import ProjectModel

_EGO_TEMPLATE = (
    "EGO_LENGTH_M: {length}\n"
    "EGO_WIDTH_M: {width}\n"
    "EGO_WHEELBASE_M: {wheelbase}\n"
    "EGO_OVERHANG_FRONT_M: {overhang}\n"
)


def _make_bundle(root: Path, name: str, *, project: str, length: float, width: float,
                  wheelbase: float, overhang: float) -> Path:
    bundle_dir = root / name
    (bundle_dir / "vehicle").mkdir(parents=True)
    (bundle_dir / "vehicle" / "ego_params.yaml").write_text(
        _EGO_TEMPLATE.format(length=length, width=width, wheelbase=wheelbase, overhang=overhang),
        encoding="utf-8",
    )
    (bundle_dir / "manifest.yaml").write_text(f"project: {project}\n", encoding="utf-8")
    return bundle_dir


def test_resolution_order_explicit_beats_embedded_beats_library_beats_checkout(tmp_path):
    """UT-A2-7: with all four sources present, explicit wins; with three, the
    embedded bundle wins; bundle_origin reports which."""
    explicit_dir = _make_bundle(tmp_path, "explicit", project="fx", length=1.0, width=1.0, wheelbase=1.0, overhang=0.1)
    embedded_dir = _make_bundle(tmp_path, "embedded", project="fx", length=2.0, width=2.0, wheelbase=2.0, overhang=0.2)
    library_dir = _make_bundle(tmp_path, "library", project="fx", length=3.0, width=3.0, wheelbase=3.0, overhang=0.3)

    all_four = ProjectModel.resolve(explicit=explicit_dir, recording=embedded_dir, library_dir=library_dir, project="fx")
    assert all_four.bundle_origin == "explicit"
    assert all_four.ego().length_m == 1.0

    three = ProjectModel.resolve(recording=embedded_dir, library_dir=library_dir, project="fx")
    assert three.bundle_origin == "embedded"
    assert three.ego().length_m == 2.0

    two = ProjectModel.resolve(library_dir=library_dir, project="fx")
    assert two.bundle_origin == "library"
    assert two.ego().length_m == 3.0

    none_given = ProjectModel.resolve(project="base")
    assert none_given.bundle_origin == "checkout"
    assert none_given.project == "base"


def test_project_mismatch_emits_provenance_warning_and_still_resolves(tmp_path):
    """UT-A2-10: a project mismatch degrades visibly (a warning) and the run
    continues -- it never raises and never silently substitutes (R-SIM-3a)."""
    other_project_dir = _make_bundle(
        tmp_path, "other", project="cus1", length=5.0, width=5.0, wheelbase=5.0, overhang=0.5
    )

    with pytest.warns(ProvenanceWarning):
        resolved = ProjectModel.resolve(explicit=other_project_dir, project="base")

    assert resolved.project == "cus1"
    assert resolved.ego().length_m == 5.0
