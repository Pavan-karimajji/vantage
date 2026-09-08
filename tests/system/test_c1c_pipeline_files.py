# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C1c's "component pipeline files under `modules/<name>/sim/pipelines/`"
box (`docs/sim_implementation_plan.md`): `df`'s own `df_only.yaml` already
proved the convention for a real, multi-function component; this proves it
for `perception-core`'s newly-shimmed one --
`modules/perception-core/sim/pipelines/perception_core_only.yaml`, checked
in unmodified here, is discoverable by `check.runner.discover_pipelines`
and genuinely `Pipeline.load`s against the real compiled library, wiring
both of `perception_core`'s real declared input ports
(`frame`/`egoDyn`) -- not a hand-authored stand-in, the actual file a
`sim check`/`sim resim --pipeline perception_core_only` run would use.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from adas_sim.check.runner import discover_pipelines
from adas_sim.graph.pipeline import Pipeline

SIM_ROOT = Path(__file__).resolve().parent.parent.parent
MODULES_ROOT = SIM_ROOT.parent
SUPERPROJECT_ROOT = MODULES_ROOT.parent
PERCEPTION_CORE_ROOT = MODULES_ROOT / "perception-core"

_PIPELINE_PATH = PERCEPTION_CORE_ROOT / "sim" / "pipelines" / "perception_core_only.yaml"
_DLL_DIR = SUPERPROJECT_ROOT / "ws" / "perception-core-base-sil-vs2026" / "src" / "platform" / "perception_core_sil" / "Release"

_SKIP_REASON = "needs a real perception_core_sil.dll build here (scripts/build.py perception-core -t sil -p vs2026 -P base)"


@pytest.fixture(autouse=True)
def _require_real_environment():
    if sys.platform != "win32":
        pytest.skip("Windows-only build path (perception_core_sil.dll)")
    if not (_DLL_DIR / "perception_core_sil.dll").is_file():
        pytest.skip(f"{_SKIP_REASON}: perception_core_sil.dll not found at {_DLL_DIR}")


def test_perception_core_only_is_discovered_under_modules_star_sim_pipelines():
    pipelines = discover_pipelines(superproject_root=SUPERPROJECT_ROOT)
    assert pipelines.get("perception_core_only") == _PIPELINE_PATH


def test_perception_core_only_loads_and_wires_both_real_input_ports():
    pipeline = Pipeline.load(_PIPELINE_PATH, search=[_DLL_DIR])
    stage = next(s for s in pipeline.stages if s.name == "perception_core")
    assert stage.inputs == {"frame": "source.frame", "egoDyn": "source.egoDyn"}
    manifest = pipeline.manifest_for("perception_core")
    declared_inputs = {spec.name for spec in manifest.inputs}
    assert declared_inputs == {"frame", "egoDyn"}
