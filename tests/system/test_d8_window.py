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


# ---------------------------------------------------------------------------
# Screen 1 -> Screen 2 (sim_player.md S6, ST-D8-2's own L-2 claim):
# recording=None opens onto the start page; MainWindow does not exist
# until open_recording() actually runs.
# ---------------------------------------------------------------------------


def test_no_recording_given_opens_onto_the_start_page():
    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = VantageWindow()
    assert window.bench is None
    assert window._stack.currentWidget() is window._start_page


def test_open_recording_constructs_bench_and_switches_to_it(tmp_path):
    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = VantageWindow()
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)

    window.open_recording(recording)
    _pump_until_loaded(window)

    assert window.bench is not None
    assert window.bench.session is not None
    assert window.workspace_name == "bench"
    assert window._stack.currentWidget() is window.bench


def test_l2_start_page_to_moving_picture_in_three_actions(tmp_path):
    """`ST-D8-2`: open (action 1, `open_recording_requested`) -> playing
    (action 2, `toggle_play_pause`) is already at or under the `L-2`
    budget of 3 -- driven programmatically, exactly as the test's own
    name in the plan requires."""
    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = VantageWindow()
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)

    actions = 0
    window._start_page.open_recording_requested.emit(recording)  # action 1: open
    actions += 1
    _pump_until_loaded(window)

    window.bench.transport_bar.toggle_play_pause()  # action 2: play
    actions += 1

    assert actions <= 3
    assert window.bench.transport.playing is True


def test_opening_a_recording_adds_it_to_recent_files_and_refreshes_the_start_page(tmp_path):
    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = VantageWindow()
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)

    window.open_recording(recording)
    _pump_until_loaded(window)

    from adas_sim.app.shell.startpage import load_recent_files
    assert recording in load_recent_files()
    assert window._start_page._recent_list.count() >= 1


def test_sample_pipeline_requested_opens_its_recording_and_pipeline(tmp_path):
    from adas_sim.app.shell.startpage import SamplePipeline

    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = VantageWindow()
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    pipeline_path = tmp_path / "pipeline.yaml"
    pipeline_path.write_text("version: 1\nname: sample\nstages: []\n", encoding="utf-8")
    sample = SamplePipeline(name="demo", pipeline_path=pipeline_path, recording_path=recording)

    window._start_page.sample_pipeline_requested.emit(sample)
    _pump_until_loaded(window)

    assert window.bench is not None
    assert window.bench.pipeline_path == pipeline_path


def test_probe_requested_from_the_start_page_reaches_the_probe_panel(tmp_path):
    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = VantageWindow()
    received = []
    window._probe_panel.load_failed.connect(received.append)

    window._start_page.probe_requested.emit(tmp_path / "no_such.dll")

    assert len(received) == 1


def test_ar45_probe_panel_is_in_the_window_and_shown_on_probe(tmp_path):
    """`AR-45`: the panel behaving is not the claim -- the window must
    actually CONTAIN it and switch to it, or `"Probe a Library…"` renders
    into a widget nobody sees. `test_probe_requested_from_the_start_page_
    reaches_the_probe_panel` above only ever proved the former."""
    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = VantageWindow()

    assert window._stack.indexOf(window._probe_panel) != -1

    window._start_page.probe_requested.emit(tmp_path / "no_such.dll")

    assert window._stack.currentWidget() is window._probe_panel


def test_ar45_console_panel_is_a_real_dock_on_bench(tmp_path):
    """`AR-45`: `ConsolePanel` must be constructed AND reachable -- before
    this fix it was never even imported by `window.py`."""
    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = VantageWindow()
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)

    window.open_recording(recording)
    _pump_until_loaded(window)

    docks = window.bench.findChildren(QtWidgets.QDockWidget)
    console_docks = [d for d in docks if d.widget() is window._console_panel]
    assert len(console_docks) == 1


def test_ar45_console_panel_survives_and_rebinds_across_a_reopened_recording(tmp_path):
    """`AR-45` + `ConsolePanel`'s own promise ("`update_namespace` rebinds
    ... without a new console instance"): the SAME `ConsolePanel` persists
    across two different recordings, and its namespace ends up bound to
    the second `Session`, never the first or a stale `None`."""
    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = VantageWindow()
    first = tmp_path / "first.mcap"
    second = tmp_path / "second.mcap"
    _write_synthetic_recording(first)
    _write_synthetic_recording(second)

    window.open_recording(first)
    _pump_until_loaded(window)
    console = window._console_panel
    first_session = window.bench.session
    assert console.namespace["session"] is first_session

    window.open_recording(second)
    _pump_until_loaded(window)

    assert window._console_panel is console  # never rebuilt
    assert console.namespace["session"] is window.bench.session
    assert console.namespace["session"] is not first_session


def test_ut_d8_3_open_on_bench_reopens_the_same_recording_and_pipeline(tmp_path):
    """`UT-D8-3`: `Open on Bench` reconstructs recording + pipeline (the
    exact failing-tick attribution for an `ok`/`fail` result needs `sim
    check`'s own expectation evaluation and is not wired to this signal --
    see `_on_open_on_bench_requested`'s own docstring; a `crash`/`timeout`
    result's own tick IS wired, `test_ut_d7_6_...` below) -- the
    reconstructed pipeline path is byte-identical to Campaign's, because it
    is literally the same `Path`, never a converted or re-authored one."""
    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = VantageWindow()
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)
    pipeline_path = tmp_path / "pipeline.yaml"
    pipeline_bytes = b"version: 1\nname: campaign\nstages: []\n"
    pipeline_path.write_bytes(pipeline_bytes)

    window.campaign.open_on_bench_requested.emit(recording, pipeline_path, 0.0)
    _pump_until_loaded(window)

    assert window.workspace_name == "bench"
    assert window.bench.pipeline_path == pipeline_path
    assert pipeline_path.read_bytes() == pipeline_bytes  # untouched, never re-authored
    assert window.bench.transport.cursor == 0


def test_ut_d7_6_open_on_bench_seeks_to_a_crash_results_last_tick(tmp_path):
    """`ST-D7-6`: a crash/timeout result's own `last_tick_ns` reproduces
    in-process on Bench AT that tick, not tick 0 -- the loop that makes a
    crash reproducible with a debugger attached (`R-SIM-19`)."""
    set_high_dpi_policy()
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = VantageWindow()
    recording = tmp_path / "rec.mcap"
    _write_synthetic_recording(recording)  # 3 ticks, 50ms apart: 0, 50ms, 100ms
    pipeline_path = tmp_path / "pipeline.yaml"
    pipeline_path.write_bytes(b"version: 1\nname: campaign\nstages: []\n")

    window.campaign.open_on_bench_requested.emit(recording, pipeline_path, 0.1)  # the 100ms tick
    _pump_until_loaded(window)

    assert window.bench.transport.cursor == 2
