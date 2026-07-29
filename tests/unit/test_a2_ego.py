# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-A2 `EgoModel` tests: UT-A2-1, UT-A2-2, UT-A2-3, UT-A2-8
(docs/sim_implementation_plan.md)."""

from __future__ import annotations

import pytest

from adas_sim.core.errors import AuthoringError
from adas_sim.model.ego import EgoModel


def test_ego_model_load_base_matches_the_published_landmark_numbers():
    """UT-A2-1: same formulas as modules/df/docs/bsd/py/bsdviz/egogeom.py,
    against shared_config/projects/base/vehicle/ego_params.yaml."""
    ego = EgoModel.load("base")
    assert ego.x_front_m == pytest.approx(3.60)
    assert ego.x_rear_m == pytest.approx(-0.90)
    assert ego.half_width_m == pytest.approx(0.90)


def test_ego_model_differs_across_every_project():
    """UT-A2-2: switching project changes the picture (R-SIM-3) -- no two of
    base/2w_base/cus1 share a single one of the three derived numbers."""
    models = {name: EgoModel.load(name) for name in ("base", "2w_base", "cus1")}
    for attr in ("x_front_m", "x_rear_m", "half_width_m"):
        values = [getattr(m, attr) for m in models.values()]
        assert len(set(values)) == len(values), f"{attr} collided across projects: {values}"


def test_missing_ego_key_raises_authoring_error_naming_key_and_file(tmp_path):
    """UT-A2-3: naming the key and the file, not "KeyError"."""
    project_dir = tmp_path / "vehicle"
    project_dir.mkdir()
    ego_file = project_dir / "ego_params.yaml"
    ego_file.write_text(
        "EGO_LENGTH_M: 4.5\nEGO_WHEELBASE_M: 2.7\nEGO_OVERHANG_FRONT_M: 0.9\n",
        encoding="utf-8",
    )  # EGO_WIDTH_M deliberately missing

    with pytest.raises(AuthoringError) as excinfo:
        EgoModel.from_yaml_file(ego_file, project="fixture")

    err = excinfo.value
    assert "EGO_WIDTH_M" in err.expected
    assert str(ego_file) == err.where


def test_unknown_project_raises_naming_the_searched_path():
    """UT-A2-8."""
    with pytest.raises(AuthoringError) as excinfo:
        EgoModel.load("does-not-exist-as-a-project")
    err = excinfo.value
    assert "does-not-exist-as-a-project" in err.where
