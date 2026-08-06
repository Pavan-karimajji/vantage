# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-C3's own "badged in the HUD" claim: the real Qt `PipelinePanel`
(`render/viewer.py`) shows a run-level summary of every declared
`run.faults:` entry -- a summary, not a per-stage badge, since a fault
targets the STIMULUS generically, never one particular stage's own row
(unlike the override badge, `test_d6_override_badge_widget.py`). Same
offscreen-platform discipline `test_d3_severed_chain_widget.py` sets.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
import yaml

pytest.importorskip("PySide6")
from PySide6 import QtWidgets  # noqa: E402

from adas_sim.contracts.component import ComponentManifest, InProcessSilComponent, PortSpec  # noqa: E402
from adas_sim.contracts.fault import Fault, FaultVerb  # noqa: E402
from adas_sim.contracts.pipeline import Pipeline  # noqa: E402
from adas_sim.render.viewer import PipelinePanel  # noqa: E402
from adas_sim.view.pipeline_panel import PipelinePanelState  # noqa: E402


def _manifest(*, component: str, inputs=()) -> ComponentManifest:
    return ComponentManifest(
        component=component, version="1", abi_version=1, build_id="test",
        inputs=tuple(inputs), outputs=(), project="base",
        config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )


def _stub(name: str, manifest: ComponentManifest) -> InProcessSilComponent:
    component = InProcessSilComponent(name, manifest, lambda dt_ns, inputs: {})
    component.init()
    return component


def _state(tmp_path, *, faults: list[Fault] = ()) -> PipelinePanelState:
    stage = {"name": "df", "mode": "simulate", "impl": "stub:df", "inputs": {"egoDyn": "source.veh_dyn"}}
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump({"version": 1, "name": "test", "stages": [stage]}, sort_keys=False), encoding="utf-8")
    manifest = _manifest(component="df", inputs=[PortSpec(name="egoDyn", proto_type="test.VehDyn")])
    pipeline = Pipeline.load(path, components={"df": _stub("df", manifest)}, faults=faults)
    return PipelinePanelState(pipeline, known_ports=frozenset())


def test_the_real_panel_hides_the_faults_label_with_none_declared(tmp_path):
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = PipelinePanel()
    panel.sync(_state(tmp_path))
    assert panel._faults_label.isHidden()


def test_the_real_panel_names_a_declared_fault(tmp_path):
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = PipelinePanel()
    fault = Fault(verb=FaultVerb.STALE, address="veh_dyn", from_s=0.0, to_s=10.0)
    panel.sync(_state(tmp_path, faults=[fault]))

    assert not panel._faults_label.isHidden()
    text = panel._faults_label.text()
    assert "stale:veh_dyn" in text
    assert "1" in text
