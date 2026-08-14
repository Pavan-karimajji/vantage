# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-04: IMP-0159/IMP-0160 -- UT-CFG-11, UT-CFG-12."""

from __future__ import annotations

import warnings

import pytest

from adas_sim.config.bundle import BundleCategory, check_cross_component_agreement, may_enter_bundle
from adas_sim.diagnostics.errors import AuthoringError, ProvenanceWarning


def test_runtime_calibration_may_enter():
    may_enter_bundle(BundleCategory.RUNTIME_CALIBRATION, key="AEB_TTC_BRAKE_THRESHOLD_S")  # no raise


@pytest.mark.parametrize("category", [
    BundleCategory.WORLD_MODEL_BINDING, BundleCategory.SENSOR_ERROR_MODEL, BundleCategory.FAULT_INJECTION,
])
def test_offer_a_runtime_file_then_a_simulation_file_reads_the_refusal_and_the_rule(category):
    """UT-CFG-11: offer a runtime file and a simulation file to the bundle;
    read the refusal and the rule it quotes."""
    may_enter_bundle(BundleCategory.RUNTIME_CALIBRATION, key="ok")  # runtime: accepted
    with pytest.raises(AuthoringError) as excinfo:
        may_enter_bundle(category, key="object_range_m")  # simulation data: refused
    assert "R-SIM-9" in str(excinfo.value)


def test_project_disagreement_is_a_warning_with_an_escape(tmp_path):
    """UT-CFG-12: present two components disagreeing on project, then on
    an ego parameter."""
    a_dir = tmp_path / "a" / "vehicle"
    a_dir.mkdir(parents=True)
    (a_dir / "ego_params.yaml").write_text("EGO_WHEELBASE_M: 2.7\n", encoding="utf-8")
    b_dir = tmp_path / "b" / "vehicle"
    b_dir.mkdir(parents=True)
    (b_dir / "ego_params.yaml").write_text("EGO_WHEELBASE_M: 2.7\n", encoding="utf-8")

    projects = {"a": "base", "b": "other_project"}
    bundle_dirs = {"a": tmp_path / "a", "b": tmp_path / "b"}

    with pytest.warns(ProvenanceWarning):
        mixed = check_cross_component_agreement(projects, bundle_dirs, allow_mixed_projects=False)
    assert mixed is True

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        mixed = check_cross_component_agreement(projects, bundle_dirs, allow_mixed_projects=True)
    assert mixed is True


def test_ego_parameter_disagreement_is_a_hard_error_with_no_escape(tmp_path):
    a_dir = tmp_path / "a" / "vehicle"
    a_dir.mkdir(parents=True)
    (a_dir / "ego_params.yaml").write_text("EGO_WHEELBASE_M: 2.7\n", encoding="utf-8")
    b_dir = tmp_path / "b" / "vehicle"
    b_dir.mkdir(parents=True)
    (b_dir / "ego_params.yaml").write_text("EGO_WHEELBASE_M: 3.1\n", encoding="utf-8")

    projects = {"a": "base", "b": "base"}
    bundle_dirs = {"a": tmp_path / "a", "b": tmp_path / "b"}

    # allow_mixed_projects does NOT suppress the ego-parameter hard error.
    with pytest.raises(AuthoringError):
        check_cross_component_agreement(projects, bundle_dirs, allow_mixed_projects=True)
