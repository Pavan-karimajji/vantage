# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-A2 system test: ST-A2-1 (docs/sim_implementation_plan.md) -- equivalence
with the code being replaced. Skips with a named reason if `modules/df`'s
`bsdviz` tree is absent (a partial clone, docs/partial_clone_workflow.md).

**Finding:** ST-A2-1 also names `SensorModel` in its equivalence claim, but
`bsdviz.sensors` has no YAML-driven counterpart to compare against -- its
`P1`..`P5` poses are hardcoded Stage-2 design constants for coverage
validation, never read from a project's `BSD_SENSOR_*` calibration. Only
`EgoModel` has a real baseline to equivalence-test here; recorded in the plan
rather than fabricating a comparison against unrelated hardcoded poses.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from adas_sim.config.ego import EgoModel

SIM_ROOT = Path(__file__).resolve().parent.parent.parent
MODULES_ROOT = SIM_ROOT.parent
BSDVIZ_DIR = MODULES_ROOT / "df" / "docs" / "bsd" / "py" / "bsdviz"


def _load_bsdviz():
    if not (BSDVIZ_DIR / "calib.py").is_file():
        return None
    py_dir = BSDVIZ_DIR.parent
    if str(py_dir) not in sys.path:
        sys.path.insert(0, str(py_dir))
    from bsdviz import calib, egogeom

    return calib, egogeom


def test_ego_model_matches_bsdviz_for_every_project():
    """ST-A2-1."""
    loaded = _load_bsdviz()
    if loaded is None:
        pytest.skip("modules/df/docs/bsd/py/bsdviz is absent (partial clone)")
    calib, egogeom = loaded

    for project in ("base", "cus1", "2w_base"):
        reference = calib.Calibration(project)
        mine = EgoModel.load(project)
        assert mine.x_front_m == pytest.approx(egogeom.x_front(reference))
        assert mine.x_rear_m == pytest.approx(egogeom.x_rear(reference))
        assert mine.half_width_m == pytest.approx(egogeom.body_half_width_m(reference))
