# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""PARITY `WP-03` tests: `UT-selmodel-01`, `UT-selmodel-02`, `UT-selview-01`
(`docs/v2/parity/PARITY_Test_Spec.md` §5.5). `F-MODEL`: three stages
(`stage_a`, `stage_b`, `stage_c`) in two groups -- `{stage_a, stage_b}` and
`{stage_c}`. Same fixture shape as `test_lnc_model.py::_chain_pipeline`.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from adas_sim.graph.build import Pipeline
from adas_sim.launcher.model import Selection, group_control_view
from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent, PortSpec

_STAGE_NAMES = ("stage_a", "stage_b", "stage_c")
GROUP_AB = ("stage_a", "stage_b")


def _manifest(*, component: str) -> ComponentManifest:
    return ComponentManifest(
        component=component, version="1", abi_version=1, build_id="test",
        inputs=(), outputs=(PortSpec(name="out", proto_type="test.A"),),
        project="base", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )


def _model_pipeline(tmp_path: Path) -> Pipeline:
    stages = []
    components = {}
    for name in _STAGE_NAMES:
        manifest = _manifest(component=name)
        stages.append({"name": name, "mode": "simulate", "impl": f"stub:{name}", "inputs": {}})
        component = InProcessSilComponent(name, manifest, lambda dt_ns, inputs: {})
        component.init()
        components[name] = component
    data = {"version": 1, "name": "model3", "stages": stages}
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return Pipeline.load(path, components=components)


def test_isolate_touches_only_the_modes_ut_selmodel_01(tmp_path):
    """UT-selmodel-01."""
    before = Selection(base_pipeline=_model_pipeline(tmp_path))

    after = before.isolate("stage_b")

    modes = {s.name: s.mode for s in after.working_pipeline.stages}
    assert modes == {"stage_a": "measured", "stage_b": "simulate", "stage_c": "measured"}  # .c1

    # .c2: nothing but mode_overrides moved
    assert after.impl_overrides == before.impl_overrides
    assert after.recordings == before.recordings
    assert after.selected_recording == before.selected_recording
    assert after.layout == before.layout
    assert after.project == before.project
    assert after.config == before.config
    assert after.search == before.search


def test_a_group_state_cannot_be_assigned_ut_selmodel_02(tmp_path):
    """UT-selmodel-02."""
    selection = Selection(base_pipeline=_model_pipeline(tmp_path))
    assert selection.group_state(GROUP_AB) == "simulate"  # both start simulate

    selection = selection.set_mode("stage_a", "measured")
    assert selection.group_state(GROUP_AB) == "mixed"  # .c1: follows its members

    selection = selection.set_mode("stage_b", "measured")
    assert selection.group_state(GROUP_AB) == "measured"  # agreeing again

    # .c2: no assignment path exists -- Selection has no set_group_state,
    # and group_state itself takes no value to assign, only member names to read.
    assert not hasattr(selection, "set_group_state")


def test_the_computed_state_is_visibly_not_choosable_ut_selview_01(tmp_path):
    """UT-selview-01."""
    selection = Selection(base_pipeline=_model_pipeline(tmp_path)).set_mode("stage_a", "measured")

    view = group_control_view(selection, GROUP_AB)

    assert view.state == "mixed"  # shown
    assert view.selectable is False  # and rejects input -- no enabled variant for "mixed"
