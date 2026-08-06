# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D6 `UT-D6-2` system test: the real Qt `PipelinePanel` (`render/
viewer.py`) renders the "input overridden" badge for a stage that declares
one, reading `StageView.overridden` (`view/pipeline_panel.py`) -- same
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


def _state(tmp_path, *, overrides: dict | None = None) -> PipelinePanelState:
    stage = {"name": "df", "mode": "simulate", "impl": "stub:df", "inputs": {"egoDyn": "source.veh_dyn"}}
    if overrides:
        stage["overrides"] = overrides
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump({"version": 1, "name": "test", "stages": [stage]}, sort_keys=False), encoding="utf-8")
    manifest = _manifest(component="df", inputs=[PortSpec(name="egoDyn", proto_type="test.VehDyn")])
    pipeline = Pipeline.load(path, components={"df": _stub("df", manifest)})
    return PipelinePanelState(pipeline, known_ports=frozenset())


def test_the_real_panel_shows_no_badge_with_no_override(tmp_path):
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = PipelinePanel()
    panel.sync(_state(tmp_path))
    assert "overridden" not in panel._table.item(0, 2).text()


def test_the_real_panel_badges_a_stage_with_a_declared_override(tmp_path):
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = PipelinePanel()
    panel.sync(_state(tmp_path, overrides={"egoDyn.vx": {"verb": "const", "value": 5.0}}))
    assert "input overridden" in panel._table.item(0, 2).text()
