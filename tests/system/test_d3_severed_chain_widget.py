# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D3 slice 5 system test (`UT-D3-3`, `UT-D6-4`): the real Qt
`PipelinePanel` (`render/viewer.py`) reflects `PipelinePanelState`'s
severed-chain auto-close -- a one-line undo bar appears naming what moved,
and clicking it renders the *"computed, not consumed"* badge on the
orphaned stage's row. Same offscreen-platform discipline as
`test_d3_pipeline_panel_widget.py` (`P-7`); same fixture topology as
`test_d3_severed_chain_panel.py`
(`upstream(simulate) -> measured(measured) -> downstream(measured)`).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
import yaml

pytest.importorskip("PySide6")
from PySide6 import QtWidgets  # noqa: E402

from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent, PortSpec  # noqa: E402
from adas_sim.graph.build import Pipeline  # noqa: E402
from adas_sim.player.shell.qt_window import PipelinePanel  # noqa: E402
from adas_sim.player.panels.pipeline_panel import PipelinePanelState  # noqa: E402


def _manifest(*, component: str, inputs=(), outputs=()) -> ComponentManifest:
    return ComponentManifest(
        component=component, version="1", abi_version=1, build_id="test",
        inputs=tuple(inputs), outputs=tuple(outputs),
        project="base", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
    )


def _stub(name: str, manifest: ComponentManifest) -> InProcessSilComponent:
    component = InProcessSilComponent(name, manifest, lambda dt_ns, inputs: {})
    component.init()
    return component


def _pre_severed_chain_state(tmp_path) -> PipelinePanelState:
    upstream = _manifest(component="upstream", outputs=[PortSpec(name="out", proto_type="test.A")])
    measured = _manifest(
        component="measured", inputs=[PortSpec(name="in", proto_type="test.A")],
        outputs=[PortSpec(name="out", proto_type="test.B")],
    )
    downstream = _manifest(component="downstream", inputs=[PortSpec(name="in", proto_type="test.B")])
    stages = [
        {"name": "upstream", "mode": "simulate", "impl": "stub:upstream", "inputs": {}},
        {"name": "measured", "mode": "measured", "impl": "stub:measured", "inputs": {"in": "upstream.out"}},
        {"name": "downstream", "mode": "measured", "impl": "stub:downstream", "inputs": {"in": "measured.out"}},
    ]
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump({"version": 1, "name": "test", "stages": stages}, sort_keys=False), encoding="utf-8")
    pipeline = Pipeline.load(path, components={
        "upstream": _stub("upstream", upstream), "measured": _stub("measured", measured),
        "downstream": _stub("downstream", downstream),
    })
    return PipelinePanelState(pipeline, known_ports=frozenset())


def _mode_button(panel: PipelinePanel, row: int, mode: str) -> QtWidgets.QRadioButton:
    cell = panel._table.cellWidget(row, 1)
    for button, (button_mode, _label) in zip(cell.findChildren(QtWidgets.QRadioButton), panel._MODE_LABELS):
        if button_mode == mode:
            return button
    raise AssertionError(f"no {mode!r} radio in row {row}")


def _row_of(panel: PipelinePanel, name: str) -> int:
    for row in range(panel._table.rowCount()):
        if panel._table.item(row, 0).text().split()[0] == name:
            return row
    raise AssertionError(f"no row named {name!r}")


def test_undo_bar_appears_on_auto_close_and_undo_badges_the_orphan_row(tmp_path):
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    state = _pre_severed_chain_state(tmp_path)
    panel = PipelinePanel()
    panel.sync(state)
    assert panel._undo_bar.isHidden()  # nothing auto-closed yet

    _mode_button(panel, _row_of(panel, "downstream"), "simulate").click()

    assert not panel._undo_bar.isHidden()
    assert "measured" in panel._undo_label.text()
    measured_row = _row_of(panel, "measured")
    assert "computed, not consumed" not in panel._table.item(measured_row, 0).text()  # gap is closed, no badge yet

    received: list[tuple[str, str]] = []
    panel.mode_changed.connect(lambda name, mode: received.append((name, mode)))
    panel._undo_button.click()

    assert panel._undo_bar.isHidden()  # nothing left to undo
    measured_row = _row_of(panel, "measured")
    assert "computed, not consumed" in panel._table.item(measured_row, 0).text()
    assert received == [("measured", "measured")]
