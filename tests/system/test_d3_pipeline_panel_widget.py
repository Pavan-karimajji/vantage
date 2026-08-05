# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

"""S-D3 slice 1 system test: `PipelinePanel` (`render/viewer.py`) renders a
real Qt table under an offscreen platform (`P-7`) and dispatches a real
click into `mode_changed` -- the "not just what the state object reports"
bar `test_b3_offscreen_smoke.py`'s own layers-panel test sets. Standalone:
no `MainWindow`, no recording -- this dock is not wired into the window
this pass (see `view/pipeline_panel.py`'s own scope note).
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


def _manifest(*, component: str, outputs=()) -> ComponentManifest:
    return ComponentManifest(
        component=component, version="1", abi_version=1, build_id="test",
        inputs=(), outputs=tuple(outputs), project="base",
        config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )


def _noop(dt_ns, inputs):
    del dt_ns, inputs
    return {}


def _load_pipeline(tmp_path) -> Pipeline:
    path = tmp_path / "d3_widget_fixture.yaml"
    path.write_text(yaml.safe_dump({
        "name": "d3_widget_fixture",
        "stages": [{"name": "upstream", "mode": "simulate", "impl": "stub:upstream", "inputs": {}}],
    }, sort_keys=False), encoding="utf-8")
    manifest = _manifest(component="upstream", outputs=[PortSpec(name="objects", proto_type="test.Objects")])
    upstream = InProcessSilComponent("upstream", manifest, _noop)
    upstream.init()
    return Pipeline.load(path, components={"upstream": upstream})


def test_panel_renders_one_row_per_stage_offscreen(tmp_path):
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    pipeline = _load_pipeline(tmp_path)
    state = PipelinePanelState(pipeline, known_ports=frozenset({"upstream.objects"}))

    panel = PipelinePanel()
    panel.sync(state)

    assert panel._table.rowCount() == 1
    assert panel._table.item(0, 0).text() == "upstream"
    assert "stub:upstream" in panel._table.item(0, 2).text()


def test_run_button_disabled_until_sync_then_clicking_it_emits_run_requested(tmp_path):
    """S-D3 slice 4 (`ST-D3-1`): the Run button follows `sync()`'s own
    "no state yet" gating `_save_run_manifest_action` already uses, and a
    real click dispatches `run_requested` -- `MainWindow` owns what "run"
    means, this class only emits."""
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = PipelinePanel()
    assert not panel._run_button.isEnabled()

    pipeline = _load_pipeline(tmp_path)
    state = PipelinePanelState(pipeline, known_ports=frozenset({"upstream.objects"}))
    panel.sync(state)
    assert panel._run_button.isEnabled()

    received = []
    panel.run_requested.connect(lambda: received.append(True))
    panel._run_button.click()
    assert received == [True]

    panel.set_run_enabled(False)
    assert not panel._run_button.isEnabled()
    panel.set_run_enabled(True)
    assert panel._run_button.isEnabled()  # state is still set -- re-enabled for real


def test_clicking_a_mode_radio_dispatches_mode_changed_and_rebuilds_the_row(tmp_path):
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    pipeline = _load_pipeline(tmp_path)
    state = PipelinePanelState(pipeline, known_ports=frozenset({"upstream.objects"}))

    panel = PipelinePanel()
    panel.sync(state)

    received: list[tuple[str, str]] = []
    panel.mode_changed.connect(lambda name, mode: received.append((name, mode)))

    mode_cell = panel._table.cellWidget(0, 1)
    measured_button = mode_cell.findChildren(QtWidgets.QRadioButton)[1]  # (simulate, measured, off)
    assert measured_button.text() == "measured"
    measured_button.click()

    assert received == [("upstream", "measured")]
    assert state.stages()[0].mode == "measured"
