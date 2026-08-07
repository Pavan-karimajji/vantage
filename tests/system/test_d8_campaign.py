# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`S-D8` `CampaignWidget` tests (`docs/sim_implementation_plan.md`,
`sim_player.md` §5): loading a recording set populates the list and the
copyable `sim batch` invocation; results populate the table; `Open on
Bench` fires from a result row; `Run` drives the real `core.batch.
run_batch` off the GUI thread (mocked here -- a real batch needs a real
`dll:`/`stubdll:` build, `core/batch.py`'s own test boundary)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
from PySide6 import QtCore, QtWidgets  # noqa: E402

from adas_sim.app.shell.campaign import CampaignWidget, batch_invocation_text  # noqa: E402
from adas_sim.core.batch import RecordingOutcome  # noqa: E402


def _app() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _pump(predicate, timeout_ms: int = 5000) -> None:
    loop = QtCore.QEventLoop()
    ceiling = QtCore.QTimer()
    ceiling.setSingleShot(True)
    ceiling.timeout.connect(loop.quit)
    ceiling.start(timeout_ms)
    poll = QtCore.QTimer()
    poll.timeout.connect(lambda: loop.quit() if predicate() else None)
    poll.start(10)
    loop.exec()
    poll.stop()
    ceiling.stop()


# ---------------------------------------------------------------------------
# batch_invocation_text -- pure formatting
# ---------------------------------------------------------------------------


def test_batch_invocation_text_names_every_recording_and_the_pipeline():
    text = batch_invocation_text([Path("a.mcap"), Path("b.mcap")], Path("p.yaml"))
    assert text == "sim batch a.mcap b.mcap --pipeline p.yaml"


def test_batch_invocation_text_includes_search_config_and_jobs():
    text = batch_invocation_text(
        [Path("a.mcap")], Path("p.yaml"), search=[Path("lib")], config=Path("cfg"), jobs=4,
    )
    assert "--search lib" in text
    assert "--config cfg" in text
    assert "--jobs 4" in text


# ---------------------------------------------------------------------------
# CampaignWidget
# ---------------------------------------------------------------------------


def test_load_recording_set_populates_the_list_and_invocation():
    _app()
    widget = CampaignWidget()
    widget.load_recording_set([Path("a.mcap"), Path("b.mcap")], Path("p.yaml"))
    assert widget._recordings_list.count() == 2
    assert "a.mcap" in widget._invocation_label.text()
    assert widget._run_button.isEnabled()
    assert widget._copy_button.isEnabled()


def test_load_recording_set_with_nothing_disables_run_and_copy():
    _app()
    widget = CampaignWidget()
    widget.load_recording_set([], Path("p.yaml"))
    assert not widget._run_button.isEnabled()
    assert not widget._copy_button.isEnabled()


def test_show_results_populates_the_table():
    _app()
    widget = CampaignWidget()
    widget.load_recording_set([Path("a.mcap")], Path("p.yaml"))
    results = [RecordingOutcome(recording=Path("a.mcap"), outcome="ok", duration_s=1.5, tick_count=42)]
    widget.show_results(results)
    assert widget._results_table.rowCount() == 1
    assert widget._results_table.item(0, 1).text() == "ok"
    assert widget._results_table.item(0, 3).text() == "42"


def test_double_clicking_a_result_row_emits_open_on_bench_requested():
    _app()
    widget = CampaignWidget()
    widget.load_recording_set([Path("a.mcap")], Path("p.yaml"))
    widget.show_results([RecordingOutcome(recording=Path("a.mcap"), outcome="fail", duration_s=0.5)])
    received = []
    widget.open_on_bench_requested.connect(lambda rec, pipe, at_s: received.append((rec, pipe, at_s)))
    widget._on_result_row_activated(widget._results_table.item(0, 0))
    assert received == [(Path("a.mcap"), Path("p.yaml"), 0.0)]


def test_double_clicking_a_crash_row_emits_its_last_tick_as_at_s():
    """`ST-D7-6`: a `crash`/`timeout` row's `last_tick_ns` is a fact
    `run_batch` already captured -- `Open on Bench` seeks there directly,
    no `expect:` evaluation needed."""
    _app()
    widget = CampaignWidget()
    widget.load_recording_set([Path("a.mcap")], Path("p.yaml"))
    widget.show_results([
        RecordingOutcome(recording=Path("a.mcap"), outcome="crash", duration_s=0.5, last_tick_ns=7_500_000_000),
    ])
    received = []
    widget.open_on_bench_requested.connect(lambda rec, pipe, at_s: received.append((rec, pipe, at_s)))
    widget._on_result_row_activated(widget._results_table.item(0, 0))
    assert received == [(Path("a.mcap"), Path("p.yaml"), 7.5)]


def test_run_button_drives_run_batch_off_the_gui_thread_and_populates_results(monkeypatch):
    """`Run` never blocks the GUI thread and the real result set lands in
    the table once the (mocked) subprocess batch completes."""
    _app()
    canned = [RecordingOutcome(recording=Path("a.mcap"), outcome="ok", duration_s=0.1, tick_count=3)]
    monkeypatch.setattr("adas_sim.app.shell.campaign.run_batch", lambda *a, **k: canned)

    widget = CampaignWidget()
    widget.load_recording_set([Path("a.mcap")], Path("p.yaml"))
    widget._on_run_clicked()
    assert not widget._run_button.isEnabled()  # disabled while running

    _pump(lambda: widget._results_table.rowCount() > 0)

    assert widget._run_button.isEnabled()
    assert widget._results_table.rowCount() == 1
    assert widget._results_table.item(0, 1).text() == "ok"


def test_ut_d8_2_locked_by_omission_no_mode_toggle_and_no_console():
    """`UT-D8-2` (`AR-48`, repointed 2026-08-06): the claim that matters is
    not that `Workspace.require()` raises correctly in isolation
    (`test_d8_workspace.py` already proves that) -- it is that `Campaign
    Widget` never constructs a control there is anything to grey out. Mode
    toggles are `QRadioButton`s (`render/viewer.py::PipelinePanel`'s own
    `_mode_button` pattern); the console is a `ConsolePanel`, identifiable
    by its own `objectName()` regardless of which dock wraps it."""
    _app()
    widget = CampaignWidget()
    widget.load_recording_set([Path("a.mcap")], Path("p.yaml"))
    widget.show_results([RecordingOutcome(recording=Path("a.mcap"), outcome="ok", duration_s=0.1)])

    assert widget.findChildren(QtWidgets.QRadioButton) == []
    assert not any(w.objectName() == "ConsolePanel" for w in widget.findChildren(QtWidgets.QWidget))


def test_run_failure_is_reported_and_never_crashes(monkeypatch):
    _app()

    def _raise(*a, **k):
        raise RuntimeError("subprocess launch failed")

    monkeypatch.setattr("adas_sim.app.shell.campaign.run_batch", _raise)
    widget = CampaignWidget()
    widget.load_recording_set([Path("a.mcap")], Path("p.yaml"))
    widget._on_run_clicked()

    _pump(lambda: widget._run_button.isEnabled())

    assert "subprocess launch failed" in widget._status_label.text()
