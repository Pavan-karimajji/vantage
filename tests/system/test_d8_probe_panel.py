# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`S-D8` `ProbePanel` tests (`docs/sim_implementation_plan.md`,
`sim_player.md` §4): probing a real, unloadable path fails visibly (no
DLL needed for this half); probing a real manifest (mocked
`probe_manifest`, the same "no DLL in this shell" boundary the rest
of this session's own tests draw) renders every input/output port."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
from PySide6 import QtWidgets  # noqa: E402

from adas_sim.player.shell.panels.probe import ProbePanel  # noqa: E402
from adas_sim.resolve.component import ComponentManifest, PortSpec  # noqa: E402


def _app() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _manifest() -> ComponentManifest:
    return ComponentManifest(
        component="demo", version="1.2.3", abi_version=1, build_id="abc123",
        inputs=(PortSpec(name="in_a", proto_type="test.A", optional=True),),
        outputs=(PortSpec(name="out_b", proto_type="test.B", owner_function="fn", period_us=50_000),),
        project="base", config_bundle_sha256="deadbeef", descriptor_set=b"", period_ns=20_000_000,
    )


def test_probing_a_nonexistent_path_fails_visibly_no_dll_needed(tmp_path):
    _app()
    panel = ProbePanel()
    panel.probe(tmp_path / "no_such_library.dll")
    assert "could not load" in panel._summary_label.text()
    assert panel._ports_tree.topLevelItemCount() == 0


def test_probing_a_nonexistent_path_emits_load_failed(tmp_path):
    _app()
    panel = ProbePanel()
    received = []
    panel.load_failed.connect(received.append)
    panel.probe(tmp_path / "no_such_library.dll")
    assert len(received) == 1
    assert "no_such_library.dll" in received[0]


def test_probing_a_real_manifest_renders_inputs_and_outputs(monkeypatch, tmp_path):
    _app()
    monkeypatch.setattr("adas_sim.player.shell.panels.probe.probe_manifest", lambda path: _manifest())
    panel = ProbePanel()
    panel.probe(tmp_path / "demo.dll")

    assert "demo" in panel._summary_label.text()
    assert "1.2.3" in panel._summary_label.text()
    assert panel._ports_tree.topLevelItemCount() == 2
    inputs_root = panel._ports_tree.topLevelItem(0)
    outputs_root = panel._ports_tree.topLevelItem(1)
    assert inputs_root.text(0) == "inputs"
    assert inputs_root.childCount() == 1
    assert inputs_root.child(0).text(0) == "in_a"
    assert outputs_root.child(0).text(0) == "out_b"
    assert outputs_root.child(0).text(4) == "50000"  # period_us


def test_probing_a_real_manifest_emits_manifest_loaded(monkeypatch, tmp_path):
    _app()
    monkeypatch.setattr("adas_sim.player.shell.panels.probe.probe_manifest", lambda path: _manifest())
    panel = ProbePanel()
    received = []
    panel.manifest_loaded.connect(received.append)
    panel.probe(tmp_path / "demo.dll")
    assert len(received) == 1
    assert received[0].component == "demo"


def test_panel_accepts_drops():
    _app()
    panel = ProbePanel()
    assert panel.acceptDrops() is True
