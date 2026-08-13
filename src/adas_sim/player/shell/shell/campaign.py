# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`CampaignWidget` -- the project workspace (`S-D8`, `sim_player.md` §5):
"many runs, reported, reproducible by someone else." A recording-set list
plus a results table, **driven by `sim batch`** (`core.batch.run_batch`,
`S-D7`) -- there is no second execution path: "a Campaign is exactly
`sim batch`... anything Campaign can do, CI can do, because it is the same
command."

**Locked, by omission, not by a disabled control** (`sim_player.md` §5:
"no per-port overrides, no live mode toggles, no Python console"). This
widget never constructs an override affordance, a mode toggle or a console
dock at all -- there is nothing here to grey out, which is a stronger claim
than a permission check on a control that exists. The one way out of a
locked view is `Open on Bench` on any result row (`open_on_bench_
requested`), which `app/shell/window.py` connects to `VantageWindow.
switch_to("bench")` plus loading that exact recording/pipeline/tick --
never a conversion, never a re-authoring step.

**The equivalent `sim batch` invocation is shown, verbatim and copyable**
(`sim_player.md` §5, point 3) -- built by `core.batch_invocation_text`
(shared with nothing else; it exists so the GUI's own command line and a
copy-pasted terminal command can never silently drift apart)."""

from __future__ import annotations

import shlex
from collections.abc import Sequence
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from adas_sim.orchestrate.batch import RecordingOutcome, run_batch


def batch_invocation_text(
    recordings: Sequence[Path], pipeline_path: Path, *,
    search: Sequence[Path] = (), config: Path | None = None, jobs: int = 1,
) -> str:
    """The literal `sim batch` command line this Campaign's `Run` button
    is about to execute -- shown so a developer can copy it into CI or a
    terminal and get the identical run (`sim_player.md` §5's own claim,
    made checkable)."""
    parts = ["sim", "batch", *[str(r) for r in recordings], "--pipeline", str(pipeline_path)]
    for s in search:
        parts += ["--search", str(s)]
    if config is not None:
        parts += ["--config", str(config)]
    if jobs != 1:
        parts += ["--jobs", str(jobs)]
    return shlex.join(parts)


_OUTCOME_COLUMNS = ("recording", "outcome", "duration_s", "ticks", "error")


class _BatchWorker(QtCore.QObject):
    """Off the GUI thread -- `run_batch` launches one real subprocess per
    recording and blocks until all finish (`core.batch`'s own isolation
    discipline, `R-SIM-19`); running it on the GUI thread would freeze the
    whole window for the length of the campaign."""

    finished = QtCore.Signal(list)
    failed = QtCore.Signal(str)

    def __init__(
        self, recordings: Sequence[Path], pipeline_path: Path, *,
        search: Sequence[Path], config: Path | None, jobs: int,
    ) -> None:
        super().__init__()
        self._recordings = tuple(recordings)
        self._pipeline_path = pipeline_path
        self._search = tuple(search)
        self._config = config
        self._jobs = jobs

    def run(self) -> None:
        try:
            results = run_batch(
                self._recordings, self._pipeline_path,
                search=self._search, config=self._config, jobs=self._jobs,
            )
        except Exception as exc:  # noqa: BLE001 -- reported to the GUI, never crashes the window
            self.failed.emit(str(exc))
            return
        self.finished.emit(results)


class CampaignWidget(QtWidgets.QWidget):
    """`sim_player.md` §5's mockup, minus chrome: a recording list, a
    results table, a `Run` button, the copyable invocation line."""

    #: (recording, pipeline_path, at_s) -- `at_s` is `RecordingOutcome.
    #: last_tick_ns / 1e9` for a `crash`/`timeout` result (`ST-D7-6`: that
    #: tick is a fact `run_batch` already captured, no `expect:` evaluation
    #: needed), else `0.0` -- identical to `open_recording`'s own `at_s=None`
    #: default (`Session.seek_ns(0)` == tick 0 either way), so a plain
    #: `float` signal type needs no `None` case.
    open_on_bench_requested = QtCore.Signal(Path, Path, float)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CampaignWidget")
        self._recordings: tuple[Path, ...] = ()
        self._pipeline_path: Path | None = None
        self._search: tuple[Path, ...] = ()
        self._config: Path | None = None
        self._jobs = 1
        self._thread: QtCore.QThread | None = None
        self._worker: _BatchWorker | None = None

        layout = QtWidgets.QVBoxLayout(self)

        header = QtWidgets.QHBoxLayout()
        self._run_button = QtWidgets.QPushButton("Run")
        self._run_button.setEnabled(False)
        self._run_button.clicked.connect(self._on_run_clicked)
        header.addWidget(self._run_button)
        self._status_label = QtWidgets.QLabel("no recording set loaded")
        header.addWidget(self._status_label)
        header.addStretch(1)
        layout.addLayout(header)

        body = QtWidgets.QHBoxLayout()
        self._recordings_list = QtWidgets.QListWidget()
        self._recordings_list.setObjectName("campaignRecordingsList")
        body.addWidget(self._recordings_list, stretch=1)

        self._results_table = QtWidgets.QTableWidget(0, len(_OUTCOME_COLUMNS))
        self._results_table.setObjectName("campaignResultsTable")
        self._results_table.setHorizontalHeaderLabels(_OUTCOME_COLUMNS)
        self._results_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._results_table.itemDoubleClicked.connect(self._on_result_row_activated)
        body.addWidget(self._results_table, stretch=2)
        layout.addLayout(body)

        invocation_row = QtWidgets.QHBoxLayout()
        self._invocation_label = QtWidgets.QLabel("")
        self._invocation_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        invocation_row.addWidget(self._invocation_label, stretch=1)
        self._copy_button = QtWidgets.QPushButton("Copy")
        self._copy_button.setEnabled(False)
        self._copy_button.clicked.connect(self._on_copy_clicked)
        invocation_row.addWidget(self._copy_button)
        layout.addLayout(invocation_row)

    def load_recording_set(
        self, recordings: Sequence[Path], pipeline_path: Path, *,
        search: Sequence[Path] = (), config: Path | None = None, jobs: int = 1,
    ) -> None:
        """The SAME pipeline file the Bench workspace has open
        (`sim_player.md` §5, point 1) -- this widget never reads or writes
        that file itself, only carries the path `run_batch` needs."""
        self._recordings = tuple(recordings)
        self._pipeline_path = pipeline_path
        self._search = tuple(search)
        self._config = config
        self._jobs = jobs

        self._recordings_list.clear()
        for recording in self._recordings:
            self._recordings_list.addItem(str(recording))
        self._results_table.setRowCount(0)

        self._invocation_label.setText(
            batch_invocation_text(self._recordings, pipeline_path, search=search, config=config, jobs=jobs)
        )
        self._run_button.setEnabled(bool(self._recordings))
        self._copy_button.setEnabled(bool(self._recordings))
        self._status_label.setText(f"{len(self._recordings)} recording(s) loaded, not yet run")

    def _on_copy_clicked(self) -> None:
        QtWidgets.QApplication.clipboard().setText(self._invocation_label.text())

    def _on_run_clicked(self) -> None:
        if self._pipeline_path is None or self._thread is not None:
            return
        self._run_button.setEnabled(False)
        self._status_label.setText(f"running {len(self._recordings)} recording(s)…")
        self._thread = QtCore.QThread(self)
        self._worker = _BatchWorker(
            self._recordings, self._pipeline_path, search=self._search, config=self._config, jobs=self._jobs,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_batch_finished)
        self._worker.failed.connect(self._on_batch_failed)
        self._thread.start()

    def _stop_thread(self) -> None:
        if self._thread is None:
            return
        self._thread.quit()
        self._thread.wait()
        self._thread = None
        self._worker = None

    def _on_batch_finished(self, results: list) -> None:
        self._stop_thread()
        self._run_button.setEnabled(True)
        self.show_results(results)

    def _on_batch_failed(self, message: str) -> None:
        self._stop_thread()
        self._run_button.setEnabled(True)
        self._status_label.setText(f"batch failed: {message}")

    def show_results(self, results: Sequence[RecordingOutcome]) -> None:
        """Public so a test (or a future headless-run replay) can populate
        the table with no real subprocess involved."""
        self._results_table.setRowCount(len(results))
        for row, result in enumerate(results):
            values = (
                str(result.recording), result.outcome, f"{result.duration_s:.2f}",
                "" if result.tick_count is None else str(result.tick_count), result.error,
            )
            for col, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                item.setData(QtCore.Qt.ItemDataRole.UserRole, result)
                self._results_table.setItem(row, col, item)
        failed = sum(1 for r in results if r.outcome != "ok")
        self._status_label.setText(f"{len(results)}/{len(results)} run · {failed} failed")

    def _on_result_row_activated(self, item: QtWidgets.QTableWidgetItem) -> None:
        result: RecordingOutcome = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if result is not None and self._pipeline_path is not None:
            at_s = result.last_tick_ns / 1e9 if result.last_tick_ns is not None else 0.0
            self.open_on_bench_requested.emit(result.recording, self._pipeline_path, at_s)
