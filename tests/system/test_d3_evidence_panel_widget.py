# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D3 slice 5 system test (`UT-D3-8`, `R-SIM-25`, `OD-6`): the real Qt
`EvidencePanel` (`render/viewer.py`) renders the SAME record `sim explain
<name> --at <tick>` prints, for both a resolvable address and one the
session cannot satisfy -- asserted field by field, never merely "both
non-empty" (`sim_implementation_plan.md`'s own `UT-D3-8` wording). Records
a real on-disk recording (`sources.recorder.Recorder`, same fixture shape
`test_c2_record_resim.py` already uses) rather than hand-building a
`Session`, so this exercises the CLI's own `build_session_from_recording`
path too. Same offscreen-platform discipline as the other S-D3 widget
tests (`P-7`).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest
import yaml

pytest.importorskip("PySide6")
from PySide6 import QtWidgets  # noqa: E402

from adas_sim.cli import explain as explain_cli  # noqa: E402
from adas_sim.resolve.component import ComponentManifest, InProcessSilComponent, PortSpec  # noqa: E402
from adas_sim.graph.build import Pipeline  # noqa: E402
from adas_sim.config.scenario import (  # noqa: E402
    EgoScenario, RoadHint, RunControl, Scenario, ScenarioContent, SensorModelRef, SutRef,
)
from adas_sim.diagnostics.evidence import evidence, format_evidence  # noqa: E402
from adas_sim.runspec.manifest import build_manifest  # noqa: E402
from adas_sim.core.runner import build_session_from_recording  # noqa: E402
from adas_sim.player.shell.qt_window import EvidencePanel  # noqa: E402
from adas_sim.sources.recorder import Recorder  # noqa: E402
from adas_sim.sources.synthetic import SyntheticSource  # noqa: E402
from adas_sim.player.panels.evidence_panel import EvidencePanelState  # noqa: E402

_UNDER_TEST_MANIFEST = ComponentManifest(
    component="under_test", version="1", abi_version=1, build_id="test",
    inputs=(PortSpec(name="egoDyn", proto_type="test.VehDyn"),),
    outputs=(PortSpec(name="verdict", proto_type="test.Verdict"),),
    project="base", config_bundle_sha256="", descriptor_set=b"", period_ns=0,
)


def _scenario() -> Scenario:
    return Scenario(
        schema=2, id="d3_evidence", doc="",
        scenario=ScenarioContent(road=RoadHint(), ego=EgoScenario(speed_mps=0.0), actors=()),
        sensor_model=SensorModelRef(), run=RunControl(), sut=SutRef(),
    )


def _record(tmp_path: Path) -> Path:
    pipeline_path = tmp_path / "pipeline.yaml"
    pipeline_path.write_text(yaml.safe_dump({
        "name": "d3_evidence", "stages": [
            {"name": "under_test", "mode": "simulate", "impl": "stub:under_test", "inputs": {"egoDyn": "source.veh_dyn"}},
        ],
    }, sort_keys=False), encoding="utf-8")
    component = InProcessSilComponent("under_test", _UNDER_TEST_MANIFEST, lambda dt_ns, inputs: {"verdict": b"ok"})
    component.init()
    pipeline = Pipeline.load(pipeline_path, components={"under_test": component})

    source = SyntheticSource([{"veh_dyn": f"vd{i}".encode()} for i in range(3)])
    recording_path = tmp_path / "recording.mcap"
    meta = build_manifest(pipeline=pipeline, pipeline_path=pipeline_path, run_kind="sim", source_kind="synthetic")
    recorder = Recorder(pipeline, source, recording_path, meta=meta)
    recorder.open(_scenario())
    for _ in range(3):
        recorder.tick(50_000_000)
    recorder.close()
    return recording_path


def _cli_rows(recording_path: Path, address: str, tick: int, capsys) -> list[tuple[str, str]]:
    exit_code = explain_cli.run([address, "--session", str(recording_path), "--at", str(tick)])
    lines = capsys.readouterr().out.splitlines()
    return exit_code, [(line[:20].strip(), line[20:].strip()) for line in lines]


def _panel_rows(session, address: str, tick: int) -> list[tuple[str, str]]:
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = EvidencePanel()
    panel.sync(EvidencePanelState(session), address, tick)
    return [
        (panel._table.item(row, 0).text(), panel._table.item(row, 1).text())
        for row in range(panel._table.rowCount())
    ]


def test_evidence_panel_matches_sim_explain_field_by_field_for_a_resolved_port(tmp_path, capsys):
    recording_path = _record(tmp_path)
    session = build_session_from_recording(recording_path)
    address, tick = "under_test.verdict", 0

    exit_code, cli_rows = _cli_rows(recording_path, address, tick, capsys)
    panel_rows = _panel_rows(session, address, tick)

    assert exit_code == 0
    assert panel_rows == cli_rows
    assert panel_rows == list(format_evidence(evidence(address, session, tick)))
    assert dict(panel_rows)["kind"] == "port"


def test_evidence_panel_matches_sim_explain_field_by_field_for_an_unresolved_address(tmp_path, capsys):
    """R-SIM-25/`NR-SIM-4`: a field the record cannot fill reads "unknown"
    on both surfaces -- never blank on one side and filled on the other."""
    recording_path = _record(tmp_path)
    session = build_session_from_recording(recording_path)
    address, tick = "no.such.port", 0

    exit_code, cli_rows = _cli_rows(recording_path, address, tick, capsys)
    panel_rows = _panel_rows(session, address, tick)

    assert exit_code == 1  # "unknown" is a non-zero exit, same as core/explain's own degrade
    assert panel_rows == cli_rows
    assert dict(panel_rows)["kind"] == "unknown"
    assert dict(panel_rows)["topic"] == "unknown"
    assert dict(panel_rows)["origin"] == "unknown"
