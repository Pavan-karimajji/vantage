# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D6 unit test: `UT-D6-3` (`sim_implementation_plan.md`) -- one source,
no second description. `sim probe`'s own CLI verb only ever takes a
library path, never an in-process object (`tests/system/test_d6_probe.py`
proves that half); this is the claim underneath it, at the level that DOES
apply to an `InProcessSilComponent`: `Pipeline.manifest_for` returns a
resolved stage's own component manifest **unchanged** -- no second,
independently-maintained port-set description for `Pipeline` to drift
from what the component itself declares.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent, PortSpec
from adas_sim.graph.pipeline import Pipeline


def test_manifest_for_returns_the_components_own_manifest_unchanged(tmp_path: Path):
    manifest = ComponentManifest(
        component="under_test", version="1", abi_version=1, build_id="test",
        inputs=(PortSpec(name="egoDyn", proto_type="test.VehDyn"),),
        outputs=(PortSpec(name="verdict", proto_type="test.Verdict"),),
        project="base", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )
    component = InProcessSilComponent("under_test", manifest, lambda dt_ns, inputs: {})
    component.init()

    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump({
        "name": "d6_manifest_for", "stages": [
            {"name": "under_test", "mode": "simulate", "impl": "stub:under_test", "inputs": {"egoDyn": "source.veh_dyn"}},
        ],
    }, sort_keys=False), encoding="utf-8")
    pipeline = Pipeline.load(path, components={"under_test": component})

    assert pipeline.manifest_for("under_test") is manifest
