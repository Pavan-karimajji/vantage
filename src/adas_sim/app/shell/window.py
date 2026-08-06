# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`VantageWindow` -- the outer shell (`S-D8`, `sim_player.md` §3): one
window, a workspace toggle in the title area, everything else is `S-B3`'s/
`S-D3`'s own docks, reused, never rebuilt.

**How the two workspaces share one engine (`R-SIM-16`, `UT-D8-1`).**
`render.viewer.MainWindow` (Bench's own content) is constructed ONCE, here,
and lives inside a `QStackedWidget` for this shell's whole life -- Qt
supports a `QMainWindow` as a plain, non-top-level child widget (its dock
system and menu bar keep working; it simply is not the OS-level window
anymore), which is what lets this module be *only* a front door: it never
re-implements a pipeline panel, an inspector or a plot. **Switching pages
in the stack is the entire workspace switch** -- nothing about `MainWindow`
itself is touched, so its `Session`, its `Pipeline` (`pipeline_panel_state.
pipeline`) and the pipeline file's own bytes on disk are identical before
and after, by construction rather than by care (`UT-D8-1`). Campaign
(`app/shell/campaign.py`) is a SEPARATE widget in the same stack, reading
the same `Session`/pipeline path Bench has open, never a converted copy.

**The engine never learns which workspace is open** (`UT-D8-9`): this
module is the one place that decides, and `MainWindow`/`Pipeline`/`Session`
carry no workspace concept of their own -- `switch_to` only ever changes
which page is visible and which `Workspace` permission set is current.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PySide6 import QtGui, QtWidgets

from adas_sim.app.shell.campaign import CampaignWidget
from adas_sim.app.shell.palette import install_shortcut
from adas_sim.app.shell.startpage import SamplePipeline
from adas_sim.app.shell.workspace import BENCH, CAMPAIGN, WorkspaceName
from adas_sim.render.viewer import MainWindow


class VantageWindow(QtWidgets.QMainWindow):
    """The product's own top-level window. `Ctrl+Shift+M` toggles
    workspace (`sim_player.md` §1's own binding)."""

    def __init__(
        self, recording: Path, *, project: str = "base",
        workspace_path: Path | None = None,
        pipeline_path: Path | None = None,
        pipeline_search: Sequence[Path] = (),
        pipeline_config: Path | None = None,
        sample_pipelines: Sequence[SamplePipeline] = (),
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Vantage")
        del sample_pipelines  # forwarded to the start page once app/shell/window.py grows one (deferred, see StartPage's own docstring)

        self.bench = MainWindow(
            recording, project=project, workspace_path=workspace_path,
            pipeline_path=pipeline_path, pipeline_search=pipeline_search, pipeline_config=pipeline_config,
        )
        self.campaign = CampaignWidget()

        self._stack = QtWidgets.QStackedWidget()
        self._stack.addWidget(self.bench)
        self._stack.addWidget(self.campaign)
        self.setCentralWidget(self._stack)

        self._workspace_name: WorkspaceName = "bench"
        self._build_workspace_toggle()
        install_shortcut(self)

        toggle_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+M"), self)
        toggle_shortcut.activated.connect(self._toggle_workspace)

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

    def _toggle_workspace(self) -> None:
        self.switch_to("campaign" if self._workspace_name == "bench" else "bench")

    def switch_to(self, name: WorkspaceName) -> None:
        """The entire workspace switch (`UT-D8-1`): pick the stack page,
        record which `Workspace` permission set is current, and touch
        NOTHING else -- no reload, no re-parse of the pipeline file, no
        change to `self.bench`'s own state."""
        self._workspace_name = name
        self._stack.setCurrentWidget(self.bench if name == "bench" else self.campaign)
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
        self.bench.close()
        super().closeEvent(event)
