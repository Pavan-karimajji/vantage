# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`VantageWindow` -- the outer shell (`S-D8`, `sim_player.md` §3): one
window, a workspace toggle in the title area, everything else is `S-B3`'s/
`S-D3`'s own docks, reused, never rebuilt.

**How the two workspaces share one engine (`R-SIM-16`, `UT-D8-1`).**
`render.viewer.MainWindow` (Bench's own content) is constructed once a
recording is chosen, and lives inside a `QStackedWidget` for the rest of
this shell's life -- Qt supports a `QMainWindow` as a plain, non-top-level
child widget (its dock system and menu bar keep working; it simply is not
the OS-level window anymore), which is what lets this module be *only* a
front door: it never re-implements a pipeline panel, an inspector or a
plot. **Switching pages in the stack is the entire workspace switch** --
nothing about `MainWindow` itself is touched, so its `Session`, its
`Pipeline` (`pipeline_panel_state.pipeline`) and the pipeline file's own
bytes on disk are identical before and after, by construction rather than
by care (`UT-D8-1`). Campaign (`app/shell/campaign.py`) is a SEPARATE
widget in the same stack, reading the same `Session`/pipeline path Bench
has open, never a converted copy.

**Screen 1 -> Screen 2** (`sim_player.md` §6, `ST-D8-2`'s own `L-2` claim):
`recording=None` opens onto the start page (recent files, `Open
Recording…`, `Probe a Library…`, sample pipelines) -- `MainWindow` is not
constructed at all until `open_recording()` actually runs, so "no
configuration before something is visible" holds structurally: there is
no half-built Bench sitting behind the start page. `open_recording()` is
the ONE path both the constructor (`recording` given up front, `sim view
<path>`'s own case) and every start-page signal route through.

**The engine never learns which workspace is open** (`UT-D8-9`): this
module is the one place that decides, and `MainWindow`/`Pipeline`/`Session`
carry no workspace concept of their own -- `switch_to` only ever changes
which page is visible and which `Workspace` permission set is current.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from adas_sim.app.panels.console import ConsolePanel
from adas_sim.app.panels.probe import ProbePanel
from adas_sim.app.shell.campaign import CampaignWidget
from adas_sim.app.shell.palette import install_shortcut
from adas_sim.app.shell.startpage import SamplePipeline, StartPage, add_recent_file, load_recent_files
from adas_sim.app.shell.workspace import BENCH, CAMPAIGN, WorkspaceName
from adas_sim.render.viewer import MainWindow


class VantageWindow(QtWidgets.QMainWindow):
    """The product's own top-level window. `Ctrl+Shift+M` toggles
    workspace (`sim_player.md` §1's own binding)."""

    def __init__(
        self, recording: Path | None = None, *, project: str = "base",
        workspace_path: Path | None = None,
        preset: str | None = None,
        at_s: float | None = None,
        scenario_path: Path | None = None,
        pipeline_path: Path | None = None,
        pipeline_search: Sequence[Path] = (),
        pipeline_config: Path | None = None,
        sample_pipelines: Sequence[SamplePipeline] = (),
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Vantage")
        self.bench: MainWindow | None = None
        self._default_project = project
        self._pipeline_search = tuple(pipeline_search)
        self._pipeline_config = pipeline_config

        self.campaign = CampaignWidget()
        self.campaign.open_on_bench_requested.connect(self._on_open_on_bench_requested)
        self._probe_panel = ProbePanel()
        #: `AR-45`: `sim_player.md` §4 -- "the pressure valve that stops
        #: someone forking the tool for one experiment." ONE instance,
        #: constructed here and never rebuilt, so its transcript/history
        #: survives every reopened recording (`_attach_console_dock`
        #: rebuilds only the `QDockWidget` wrapping it, since that dies
        #: with the old `self.bench`); `update_namespace` rebinds
        #: `session`/`pipeline` in place instead.
        self._console_panel = ConsolePanel()
        self._start_page = StartPage(recent_files=load_recent_files(), sample_pipelines=sample_pipelines)
        self._start_page.open_recording_requested.connect(self.open_recording)
        self._start_page.probe_requested.connect(self._on_probe_requested)
        self._start_page.sample_pipeline_requested.connect(self._on_sample_pipeline_requested)

        self._stack = QtWidgets.QStackedWidget()
        self._stack.addWidget(self._start_page)
        self._stack.addWidget(self.campaign)
        self._stack.addWidget(self._probe_panel)
        self.setCentralWidget(self._stack)

        self._workspace_name: WorkspaceName = "bench"
        self._build_workspace_toggle()
        install_shortcut(self)

        toggle_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+M"), self)
        toggle_shortcut.activated.connect(self._toggle_workspace)

        if recording is not None:
            self.open_recording(
                recording, project=project, workspace_path=workspace_path, preset=preset, at_s=at_s,
                scenario_path=scenario_path, pipeline_path=pipeline_path,
            )
        else:
            self._stack.setCurrentWidget(self._start_page)

    def _build_workspace_toggle(self) -> None:
        toolbar = QtWidgets.QToolBar("Workspace")
        toolbar.setObjectName("workspaceToolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        group = QtGui.QActionGroup(self)
        group.setExclusive(True)
        self._bench_action = QtGui.QAction("Bench", self, checkable=True, checked=True)
        self._campaign_action = QtGui.QAction("Campaign", self, checkable=True)
        for action in (self._bench_action, self._campaign_action):
            group.addAction(action)
            toolbar.addAction(action)
        self._bench_action.triggered.connect(lambda: self.switch_to("bench"))
        self._campaign_action.triggered.connect(lambda: self.switch_to("campaign"))

    @property
    def workspace_name(self) -> WorkspaceName:
        return self._workspace_name

    def open_recording(
        self, recording: Path, *, project: str | None = None,
        workspace_path: Path | None = None, preset: str | None = None, at_s: float | None = None,
        scenario_path: Path | None = None, pipeline_path: Path | None = None,
    ) -> None:
        """Screen 1 -> Screen 2 (`sim_player.md` §6): constructs `MainWindow`
        for real (the one real engine load in this shell's life for this
        recording), records it in the recent-files list, and switches to
        Bench. The SAME path a freshly-opened window's constructor uses,
        a recent-file double-click uses, and a sample-pipeline pick uses --
        one recording, one way in."""
        if self.bench is not None:
            self._stack.removeWidget(self.bench)
            self._detach_console_dock()
            self.bench.close()
        self.bench = MainWindow(
            recording, project=project if project is not None else self._default_project,
            workspace_path=workspace_path, preset=preset, initial_at_s=at_s, scenario_path=scenario_path,
            pipeline_path=pipeline_path, pipeline_search=self._pipeline_search, pipeline_config=self._pipeline_config,
        )
        self._stack.insertWidget(0, self.bench)
        self._attach_console_dock()
        add_recent_file(recording)
        self._start_page.set_recent_files(load_recent_files())
        self.switch_to("bench")

    def _detach_console_dock(self) -> None:
        """The old `self.bench` is about to be closed and discarded, and a
        `QDockWidget` deletes its own widget along with itself -- without
        this, the persistent `self._console_panel` `_attach_console_dock`
        promises would die with the dock wrapping it. `takeCentralWidget`'s
        own idiom, applied to a dock: reparent the survivor out first."""
        dock = self._console_panel.parentWidget()
        if dock is not None:
            dock.setWidget(None)  # type: ignore[arg-type]

    def _attach_console_dock(self) -> None:
        """`AR-45`: Bench-only by construction -- Campaign is a separate
        stack page (`app/shell/campaign.py`) that never gets a dock at all,
        the same "locked by omission" discipline it already uses for
        overrides and mode toggles. The `QDockWidget` wrapper is rebuilt
        per `self.bench` (it dies with the old one, closed above,
        `_detach_console_dock`); the `ConsolePanel` it wraps is not.
        `session`/`pipeline` are rebound once immediately (both `None`
        until the load finishes) and again on `MainWindow.session_ready`,
        so the console is never left pointing at a stale or absent
        session."""
        dock = QtWidgets.QDockWidget("Console", self.bench)
        dock.setObjectName("consoleDock")
        dock.setWidget(self._console_panel)
        self.bench.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        self.bench.session_ready.connect(self._on_bench_session_ready)
        self._rebind_console_namespace()

    def _on_bench_session_ready(self) -> None:
        self._rebind_console_namespace()

    def _rebind_console_namespace(self) -> None:
        if self.bench is not None:
            self._console_panel.update_namespace(
                session=self.bench.session, pipeline=self.bench.pipeline_panel_state,
            )

    def _on_probe_requested(self, path: Path) -> None:
        """`AR-45`: `sim_player.md` §4 -- "the day-one screen for a new
        component." Probing and showing are two calls, not one, so a
        caller (a test) can still probe without the stack switch."""
        self._probe_panel.probe(path)
        self._stack.setCurrentWidget(self._probe_panel)

    def _on_sample_pipeline_requested(self, sample: SamplePipeline) -> None:
        self.open_recording(sample.recording_path, pipeline_path=sample.pipeline_path)

    def _on_open_on_bench_requested(self, recording: Path, pipeline_path: Path, at_s: float) -> None:
        """`UT-D8-3`/`ST-D7-6`: Campaign's own escape hatch -- the SAME
        recording and pipeline file a result row named, reopened on Bench,
        seeked to `at_s` (`CampaignWidget`'s own `RecordingOutcome.
        last_tick_ns / 1e9` for a `crash`/`timeout` row -- a fact `run_batch`
        already captured, needing no `expect:` evaluation -- or `0.0`,
        identical to today's tick-0 default, for every other outcome).
        **Still open, honestly**: attributing a tick to an `ok`/`fail` result
        against its `expect:` criteria is `sim check`'s own job and is not
        this signal's scope -- those rows still open at tick 0."""
        self.open_recording(recording, pipeline_path=pipeline_path, at_s=at_s if at_s > 0.0 else None)

    def _toggle_workspace(self) -> None:
        self.switch_to("campaign" if self._workspace_name == "bench" else "bench")

    def switch_to(self, name: WorkspaceName) -> None:
        """The entire workspace switch (`UT-D8-1`): pick the stack page,
        record which `Workspace` permission set is current, and touch
        NOTHING else -- no reload, no re-parse of the pipeline file, no
        change to `self.bench`'s own state. `name == "bench"` with no
        recording open yet falls back to the start page -- there is
        nothing to switch to."""
        self._workspace_name = name
        if name == "bench":
            self._stack.setCurrentWidget(self.bench if self.bench is not None else self._start_page)
        else:
            self._stack.setCurrentWidget(self.campaign)
        self._bench_action.setChecked(name == "bench")
        self._campaign_action.setChecked(name == "campaign")

    @property
    def current_workspace(self):
        return BENCH if self._workspace_name == "bench" else CAMPAIGN

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802 -- Qt override
        # MainWindow is no longer top-level once embedded in the stack, so
        # Qt never delivers it its own close event automatically -- calling
        # close() explicitly still runs its real cleanup (save_layout,
        # thread teardown), since QWidget.close() sends a QCloseEvent
        # regardless of top-level status.
        if self.bench is not None:
            self.bench.close()
        super().closeEvent(event)
