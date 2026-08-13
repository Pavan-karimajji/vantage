# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`StartPage` -- Screen 1 of `sim_player.md` §6: "Recent files, `Open
recording…`, `Probe a library…`, and three sample pipelines that ship
with the tool. No configuration. No settings prompt. No project selection."

**No form, ever** (`sim_player.md` §2's own ban: "Vantage never opens onto
a form. It opens onto either a recording or a start page with recent
files."). This widget contains no `QLineEdit`/settings field of its own --
every action is a button or a list double-click, and the ONE place text
entry happens at all is the native OS file-open dialog `Open Recording…`/
`Probe a Library…` triggers, never this page's own layout.

**Sample pipelines are real infrastructure, empty content.** `sample_
pipelines` defaults to `()` -- the three that should ship need a real,
compiled, cross-platform demo component library (so a sample loads with
no project's own DLL present), which this pass could not build (no C++
toolchain in this environment, the same class of gap `S-C7`'s own honesty
note already states). The widget, the signal, the list rendering and the
tests are all real; the three actual samples are left open rather than
shipped broken (`R-SIM-25`'s discipline extended to "a feature that only
looks present").

**Recent files persist to the OS config location** (`P-2`/`P-7`,
`render/viewer.py`'s own `_config_root()` -- reused here, not
re-implemented, so there is exactly one answer to "where does Vantage
keep its own state")."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from adas_sim.player.shell.qt_window import _config_root

#: `sim_player.md` doesn't fix a number -- capped so the list stays a
#: glance, not a second file browser.
MAX_RECENT_FILES = 10


def recent_files_path() -> Path:
    return _config_root() / "recent_files.json"


def load_recent_files(path: Path | None = None) -> tuple[Path, ...]:
    """`()` for "no file yet" AND for "the file is unreadable/corrupt" --
    a start page with no recent files is the same honest empty state
    either way, never a crash on first launch or a stale profile."""
    target = path if path is not None else recent_files_path()
    if not target.is_file():
        return ()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    if not isinstance(raw, list):
        return ()
    return tuple(Path(entry) for entry in raw if isinstance(entry, str))


def save_recent_files(files: Sequence[Path], path: Path | None = None) -> None:
    target = path if path is not None else recent_files_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps([str(f) for f in files]), encoding="utf-8")


def add_recent_file(new_file: Path, *, path: Path | None = None) -> tuple[Path, ...]:
    """Moves `new_file` to the front, de-duplicated, capped at
    `MAX_RECENT_FILES` -- the one mutating entry point; `StartPage` never
    writes the file directly."""
    existing = [f for f in load_recent_files(path) if f != new_file]
    updated = (new_file, *existing)[:MAX_RECENT_FILES]
    save_recent_files(updated, path)
    return updated


@dataclass(frozen=True, slots=True)
class SamplePipeline:
    """One shipped sample: a name, a pipeline file, a recording to open it
    against -- `mode: measured` end to end, by construction, so opening a
    sample needs no project's own component library resolved (see this
    module's own docstring on why none ship yet)."""

    name: str
    pipeline_path: Path
    recording_path: Path


class StartPage(QtWidgets.QWidget):
    """`sim_player.md` §6 Screen 1. Three signals, no state of its own
    beyond what it was constructed with -- `app/shell/window.py` owns
    opening the chosen file, this widget only ever asks."""

    open_recording_requested = QtCore.Signal(Path)
    probe_requested = QtCore.Signal(Path)
    sample_pipeline_requested = QtCore.Signal(object)  # SamplePipeline

    def __init__(
        self, *, recent_files: Sequence[Path] = (), sample_pipelines: Sequence[SamplePipeline] = (),
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("StartPage")
        self._sample_pipelines = tuple(sample_pipelines)

        layout = QtWidgets.QVBoxLayout(self)

        actions = QtWidgets.QHBoxLayout()
        self._open_button = QtWidgets.QPushButton("Open Recording…")
        self._open_button.clicked.connect(self._on_open_clicked)
        actions.addWidget(self._open_button)
        self._probe_button = QtWidgets.QPushButton("Probe a Library…")
        self._probe_button.clicked.connect(self._on_probe_clicked)
        actions.addWidget(self._probe_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        layout.addWidget(QtWidgets.QLabel("Recent"))
        self._recent_list = QtWidgets.QListWidget()
        self._recent_list.setObjectName("recentFilesList")
        self._recent_list.itemDoubleClicked.connect(self._on_recent_item_activated)
        layout.addWidget(self._recent_list)
        self.set_recent_files(recent_files)

        layout.addWidget(QtWidgets.QLabel("Sample pipelines"))
        self._samples_list = QtWidgets.QListWidget()
        self._samples_list.setObjectName("samplePipelinesList")
        self._samples_list.itemDoubleClicked.connect(self._on_sample_item_activated)
        layout.addWidget(self._samples_list)
        self._rebuild_samples_list()

        layout.addStretch(1)

    def set_recent_files(self, files: Sequence[Path]) -> None:
        self._recent_list.clear()
        for f in files:
            item = QtWidgets.QListWidgetItem(str(f))
            item.setData(QtCore.Qt.ItemDataRole.UserRole, f)
            self._recent_list.addItem(item)

    def _rebuild_samples_list(self) -> None:
        self._samples_list.clear()
        for sample in self._sample_pipelines:
            item = QtWidgets.QListWidgetItem(sample.name)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, sample)
            self._samples_list.addItem(item)

    def _on_open_clicked(self) -> None:
        path_str, _filter = QtWidgets.QFileDialog.getOpenFileName(self, "Open Recording")
        if path_str:
            self.open_recording_requested.emit(Path(path_str))

    def _on_probe_clicked(self) -> None:
        path_str, _filter = QtWidgets.QFileDialog.getOpenFileName(self, "Probe a Library")
        if path_str:
            self.probe_requested.emit(Path(path_str))

    def _on_recent_item_activated(self, item: QtWidgets.QListWidgetItem) -> None:
        path = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if path is not None:
            self.open_recording_requested.emit(path)

    def _on_sample_item_activated(self, item: QtWidgets.QListWidgetItem) -> None:
        sample = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if sample is not None:
            self.sample_pipeline_requested.emit(sample)
