# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`S-D8` `StartPage` tests (`docs/sim_implementation_plan.md`,
`sim_player.md` §6 Screen 1): recent files persist and round-trip, no
`QLineEdit` exists anywhere in the widget's own tree ("no form, ever"),
and every action -- open a recording, probe a library, open a recent
file, open a sample -- reaches its own signal."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
from PySide6 import QtCore, QtWidgets  # noqa: E402

QtCore.QStandardPaths.setTestModeEnabled(True)  # P-7: never touch the real user profile in tests

from adas_sim.player.shell.shell.startpage import (  # noqa: E402
    MAX_RECENT_FILES,
    SamplePipeline,
    StartPage,
    add_recent_file,
    load_recent_files,
    save_recent_files,
)


def _app() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


# ---------------------------------------------------------------------------
# Recent-files persistence -- pure file logic, no Qt widget needed
# ---------------------------------------------------------------------------


def test_load_recent_files_empty_when_no_file_exists(tmp_path):
    assert load_recent_files(tmp_path / "nope.json") == ()


def test_load_recent_files_empty_on_a_corrupt_file(tmp_path):
    path = tmp_path / "recent.json"
    path.write_text("not json{{{", encoding="utf-8")
    assert load_recent_files(path) == ()


def test_save_and_load_round_trips(tmp_path):
    path = tmp_path / "recent.json"
    files = (Path("/a/one.mcap"), Path("/a/two.mcap"))
    save_recent_files(files, path)
    assert load_recent_files(path) == files


def test_add_recent_file_moves_to_front_and_dedupes(tmp_path):
    path = tmp_path / "recent.json"
    save_recent_files((Path("/a/one.mcap"), Path("/a/two.mcap")), path)
    updated = add_recent_file(Path("/a/two.mcap"), path=path)
    assert updated == (Path("/a/two.mcap"), Path("/a/one.mcap"))


def test_add_recent_file_caps_at_the_maximum(tmp_path):
    path = tmp_path / "recent.json"
    for i in range(MAX_RECENT_FILES + 5):
        add_recent_file(Path(f"/a/{i}.mcap"), path=path)
    assert len(load_recent_files(path)) == MAX_RECENT_FILES
    # most-recently-added is first
    assert load_recent_files(path)[0] == Path(f"/a/{MAX_RECENT_FILES + 4}.mcap")


# ---------------------------------------------------------------------------
# The widget itself
# ---------------------------------------------------------------------------


def test_no_line_edit_anywhere_in_the_start_page():
    """`sim_player.md` §2's own ban: "Vantage never opens onto a form"."""
    _app()
    page = StartPage()
    assert page.findChildren(QtWidgets.QLineEdit) == []


def test_recent_files_populate_the_list():
    _app()
    files = (Path("/a/one.mcap"), Path("/a/two.mcap"))
    page = StartPage(recent_files=files)
    assert page._recent_list.count() == 2
    assert page._recent_list.item(0).text() == str(files[0])


def test_double_clicking_a_recent_file_emits_open_recording_requested():
    _app()
    files = (Path("/a/one.mcap"),)
    page = StartPage(recent_files=files)
    received = []
    page.open_recording_requested.connect(received.append)
    page._on_recent_item_activated(page._recent_list.item(0))
    assert received == [Path("/a/one.mcap")]


def test_sample_pipelines_populate_the_list_and_default_to_empty():
    _app()
    empty_page = StartPage()
    assert empty_page._samples_list.count() == 0

    sample = SamplePipeline(name="one_stage", pipeline_path=Path("/s/p.yaml"), recording_path=Path("/s/r.mcap"))
    page = StartPage(sample_pipelines=[sample])
    assert page._samples_list.count() == 1
    assert page._samples_list.item(0).text() == "one_stage"


def test_double_clicking_a_sample_emits_sample_pipeline_requested():
    _app()
    sample = SamplePipeline(name="one_stage", pipeline_path=Path("/s/p.yaml"), recording_path=Path("/s/r.mcap"))
    page = StartPage(sample_pipelines=[sample])
    received = []
    page.sample_pipeline_requested.connect(received.append)
    page._on_sample_item_activated(page._samples_list.item(0))
    assert received == [sample]


def test_open_recording_button_emits_the_chosen_path(monkeypatch):
    _app()
    monkeypatch.setattr(
        QtWidgets.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("/picked/rec.mcap", ""))
    )
    page = StartPage()
    received = []
    page.open_recording_requested.connect(received.append)
    page._open_button.click()
    assert received == [Path("/picked/rec.mcap")]


def test_open_recording_button_emits_nothing_on_cancel(monkeypatch):
    _app()
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", "")))
    page = StartPage()
    received = []
    page.open_recording_requested.connect(received.append)
    page._open_button.click()
    assert received == []


def test_probe_button_emits_the_chosen_path(monkeypatch):
    _app()
    monkeypatch.setattr(
        QtWidgets.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("/picked/df_sil.dll", ""))
    )
    page = StartPage()
    received = []
    page.probe_requested.connect(received.append)
    page._probe_button.click()
    assert received == [Path("/picked/df_sil.dll")]
