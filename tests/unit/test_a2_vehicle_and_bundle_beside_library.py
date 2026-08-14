# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-04: IMP-0161/IMP-0162 -- `config/vehicle.py` (ego/objects/sensors/
cameras) and "the bundle is copied beside the library, never compiled into
it" are both tagged `KEEP` (already true); this file is the UT-CFG-13/IT-13
coverage that names them, not a code change (`R-STYLE-2`).
"""

from __future__ import annotations

from pathlib import Path

from adas_sim.config.ego import EgoModel
from adas_sim.config.objects import DEFAULT_FALLBACK_FOOTPRINT, ObjectModel
from adas_sim.config.project import ProjectModel

_EGO_TEMPLATE = (
    "EGO_LENGTH_M: {length}\n"
    "EGO_WIDTH_M: {width}\n"
    "EGO_WHEELBASE_M: {wheelbase}\n"
    "EGO_OVERHANG_FRONT_M: {overhang}\n"
)


def _make_bundle(root: Path, name: str, *, wheelbase: float) -> Path:
    bundle_dir = root / name
    (bundle_dir / "vehicle").mkdir(parents=True)
    (bundle_dir / "vehicle" / "ego_params.yaml").write_text(
        _EGO_TEMPLATE.format(length=4.5, width=1.8, wheelbase=wheelbase, overhang=0.9), encoding="utf-8",
    )
    return bundle_dir


def test_resolve_geometry_for_two_projects_then_a_class_with_no_footprint(tmp_path):
    """UT-CFG-13: resolve geometry for two projects; then for a class with
    no measured footprint."""
    project_a = _make_bundle(tmp_path, "project_a", wheelbase=2.7)
    project_b = _make_bundle(tmp_path, "project_b", wheelbase=3.1)

    ego_a = ProjectModel.resolve(library_dir=project_a, project="project_a").ego()
    ego_b = ProjectModel.resolve(library_dir=project_b, project="project_b").ego()
    assert ego_a.wheelbase_m == 2.7
    assert ego_b.wheelbase_m == 3.1
    assert ego_a.wheelbase_m != ego_b.wheelbase_m  # switching project changes the picture (R-SIM-3)

    objects = ObjectModel(class_table={"car": DEFAULT_FALLBACK_FOOTPRINT})
    unmeasured = objects.footprint("spaceship")  # a class with no measured footprint
    assert unmeasured.assumed_geometry is True


def test_editing_the_bundle_beside_the_library_changes_the_result_with_no_rebuild(tmp_path):
    """IT-13: change a calibration value in the bundle; re-run; build
    nothing; observe the changed result. `library_dir` here stands in for
    `<library_dir>/config` (R-SIM-3a) -- no DLL is compiled or touched by
    either resolve() call, matching "the bundle is copied beside the
    library, never compiled into it"."""
    library_dir = _make_bundle(tmp_path, "lib_config", wheelbase=2.7)

    first = ProjectModel.resolve(library_dir=library_dir, project="base").ego()
    assert first.wheelbase_m == 2.7

    # Edit the calibration value on disk -- no build step of any kind.
    (library_dir / "vehicle" / "ego_params.yaml").write_text(
        _EGO_TEMPLATE.format(length=4.5, width=1.8, wheelbase=2.9, overhang=0.9), encoding="utf-8",
    )

    second = ProjectModel.resolve(library_dir=library_dir, project="base").ego()
    assert second.wheelbase_m == 2.9
    assert isinstance(second, EgoModel)
