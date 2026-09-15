# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""WP-04: `IMP-0162` -- `IT-13`, against the real `F-LIBDIR` fixture
`test_e3_determinism_measured.py` also uses: a real, already-built
`df_sil.dll`'s own packed config bundle. Copied to an isolated `tmp_path`
first (never mutate the shared build output another test/developer reads)
-- the copy IS the real bundle's own bytes, not a synthetic fixture, so
"change a calibration value; re-run; build nothing; observe the changed
result" is proven against the artifact the claim is actually about.

Skips with a named reason if the real build is absent, same discipline
`test_e3_determinism_measured.py`/`test_c8_relocatability_installed.py`
already use for a real compiled `df_sil`.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from adas_sim.config.project import ProjectModel

SIM_ROOT = Path(__file__).resolve().parent.parent.parent
MODULES_ROOT = SIM_ROOT.parent
DF_ROOT = MODULES_ROOT / "df"
_DF_SIL_CONFIG = DF_ROOT / "conan_workarea" / "build-sil-vs2026" / "src" / "platform" / "df_sil" / "Release" / "config"

pytestmark = pytest.mark.skipif(
    sys.platform != "win32" or not (_DF_SIL_CONFIG / "vehicle" / "ego_params.yaml").is_file(),
    reason="needs a real df_sil.dll build here (scripts/build.py df -t sil -p vs2026 -P base)",
)


def test_editing_the_real_packed_bundle_beside_the_library_changes_the_result_with_no_rebuild(tmp_path):
    """IT-13, `F-LIBDIR`: change a calibration value in the bundle; re-run;
    build nothing; observe the changed result."""
    bundle_copy = tmp_path / "config"
    shutil.copytree(_DF_SIL_CONFIG, bundle_copy)
    ego_path = bundle_copy / "vehicle" / "ego_params.yaml"
    original_text = ego_path.read_text(encoding="utf-8")
    assert "EGO_WHEELBASE_M: 2.7" in original_text, "real bundle's own calibration shape changed -- update this fixture"

    first = ProjectModel.resolve(library_dir=bundle_copy, project="base")
    assert first.ego().wheelbase_m == 2.7
    assert first.bundle_origin == "library"

    # The whole claim: edit the bundle in place, no build/compile step of
    # any kind touches df_sil.dll or bundle_copy's own directory structure.
    ego_path.write_text(original_text.replace("EGO_WHEELBASE_M: 2.7", "EGO_WHEELBASE_M: 3.05"), encoding="utf-8")

    second = ProjectModel.resolve(library_dir=bundle_copy, project="base")
    assert second.ego().wheelbase_m == 3.05
    assert second.bundle_sha256 != first.bundle_sha256  # the hash moved with the edit, R-SIM-3a
