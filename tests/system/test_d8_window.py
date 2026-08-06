# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`S-D8` `VantageWindow` tests (`docs/sim_implementation_plan.md`,
`sim_player.md` §1/§3): `UT-D8-1` -- switching workspace preserves the
loaded `Session` object and the pipeline file's own bytes on disk,
because switching never reloads anything, it only changes which stack
page is visible."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
from PySide6 import QtCore, QtWidgets  # noqa: E402

QtCore.QStandardPaths.setTestModeEnabled(True)  # P-7: never touch the real user profile in tests

from adas_sim.app.shell.window import VantageWindow  # noqa: E402
from adas_sim.io.base import ComponentBuildInfo, Provenance, RunManifest, TopicInfo  # noqa: E402
from adas_sim.io.registry import writer_for  # noqa: E402
from adas_sim.render.viewer import set_high_dpi_policy  # noqa: E402

import adas_sim.io.mcap  # noqa: E402,F401 -- registers the ".mcap" codec

_PROJECT = "base"


def _write_synthetic_recording(out_path: Path) -> None:
    manifest = RunManifest(
        manifest_version=2, run_id="test-d8-window", run_kind="resim",
        created_utc="2026-08-06T00:00:00Z", source_kind="synthetic",
        scenario="fixtures/test_d8_window.yaml", project=_PROJECT, pipeline="p1", seed=0,
        components=(ComponentBuildInfo(name="test", library_sha256="0" * 64, build_id="build-xyz"),),
    )
    topics = {"/test/marker": TopicInfo(schema_name="", provenance=Provenance.UNKNOWN)}
    writer = writer_for(out_path)
    writer.open(out_path, manifest, topics, config_bundle_bytes=b"")
    for tick in range(3):
        writer.write("/test/marker", tick * 50_000_000, bytes([tick % 256]))
    writer.close()


def _pump_until_loaded(window: VantageWindow, timeout_ms: int = 5000) -> None:
    loop = QtCore.QEventLoop()
    ceiling = QtCore.QTimer()
    ceiling.setSingleShot(True)
    ceiling.timeout.connect(loop.quit)
    ceiling.start(timeout_ms)
    poll = QtCore.QTimer()
    poll.timeout.connect(lambda: loop.quit() if window.bench.session is not None else None)
    poll.start(10)
    loop.exec()
    poll.stop()
    ceiling.stop()


def _open_window(recording: Path, **kwargs) -> VantageWindow:
    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = VantageWindow(recording, project=_PROJECT, **kwargs)
    window.show()
    _pump_until_loaded(window)
    assert window.bench.session is not None
    return window


def test_opens_on_bench_by_default(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)
    assert window.workspace_name == "bench"
    assert window._stack.currentWidget() is window.bench


def test_switch_to_campaign_changes_the_visible_page_only(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)
    session_before = window.bench.session

    window.switch_to("campaign")
    assert window.workspace_name == "campaign"
    assert window._stack.currentWidget() is window.campaign
    assert window.bench.session is session_before  # UT-D8-1: no reload

    window.switch_to("bench")
    assert window._stack.currentWidget() is window.bench
    assert window.bench.session is session_before


def test_ut_d8_1_session_object_identity_survives_a_round_trip(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)

    session_before = window.bench.session
    window.switch_to("campaign")
    window.switch_to("bench")
    assert window.bench.session is session_before


def test_ut_d8_1_pipeline_file_bytes_survive_a_workspace_switch(tmp_path):
    """Asserted on the FILE, not the model (`UT-D8-1`'s own wording) --
    switching workspace must never touch the pipeline file on disk."""
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    pipeline_path = tmp_path / "pipeline.yaml"
    pipeline_path.write_text("version: 1\nname: test\nstages: []\n", encoding="utf-8")
    bytes_before = pipeline_path.read_bytes()

    window = _open_window(recording, pipeline_path=pipeline_path)
    assert window.bench.pipeline_path == pipeline_path

    window.switch_to("campaign")
    window.switch_to("bench")

    assert pipeline_path.read_bytes() == bytes_before
    assert window.bench.pipeline_path == pipeline_path


def test_toggle_workspace_shortcut_flips_between_bench_and_campaign(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)
    assert window.workspace_name == "bench"
    window._toggle_workspace()
    assert window.workspace_name == "campaign"
    window._toggle_workspace()
    assert window.workspace_name == "bench"


def test_workspace_toolbar_actions_reflect_the_current_workspace(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)
    assert window._bench_action.isChecked()
    assert not window._campaign_action.isChecked()
    window.switch_to("campaign")
    assert window._campaign_action.isChecked()
    assert not window._bench_action.isChecked()


def test_current_workspace_property_matches_the_permission_set(tmp_path):
    from adas_sim.app.shell.workspace import BENCH, CAMPAIGN

    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)
    assert window.current_workspace is BENCH
    window.switch_to("campaign")
    assert window.current_workspace is CAMPAIGN


def test_close_event_cleans_up_the_embedded_bench_window(tmp_path):
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    window = _open_window(recording)
    window.close()  # must not raise, must run MainWindow's own cleanup
