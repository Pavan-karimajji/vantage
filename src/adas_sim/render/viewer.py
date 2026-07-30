# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Vantage's Qt shell -- foundation slice (`sim_implementation_plan.md` S-B3).
Qt starts here and never below this line (`UT-B3-17`): pass 1 lives in
`core/runner.py`, Scene assembly in `core/runner.build_scene`, rasterising in
`render/bev.py` -- none of them import Qt, so this module is the only place
that does.

**Threading ownership (one documented rule, `sim_visualization_spec.md`
§11.1).** Pass 1 (`build_session_from_recording`) runs on a `QThread` via
`_SessionLoadWorker`, which is the only thing that touches a `Session`
before it exists. Once `loaded` fires (delivered on the GUI thread by Qt's
queued connection across threads), the `SceneCache` and every panel are
built and read from the GUI thread only -- pass 2 (Scene assembly +
rasterising) is cheap and pure, so it can afford to.

**Scope so far.** Slice 1 built the window, the threading model and the BEV
panel. Slice 2 added the layers dock, a thin Qt view over
`view.layers.LayerTreeState` (every decision -- tri-state, solo/mute, search,
verbosity -- lives there, never here, `GT-9`). **Slice 3 closes two pieces of
persistence debt (`P-7`):** the dockable panel grid itself -- open/close (each
dock's own `toggleViewAction()` in the View menu), split/tab/float (native
`QMainWindow`/`QDockWidget` mechanics, nothing to wrap) and a **saved layout,
per project** (`sim_visualization_spec.md` §11.1) via `saveState()`/
`restoreState()` -- plus wiring `LayerTreeState`'s already-built `save()`/
`load()` (Slice 2) to a real location, **per (project, pipeline)** (§6: a
function's layer overrides persist per project + pipeline, so re-opening a
recording of that function restores its layer choices). Both locations
resolve through `QStandardPaths.AppConfigLocation`, never a hand-written
`%LOCALAPPDATA%`/`~/.config` path. Inspector, timeline, signals, plots,
measure and component-shipped `workspace.yaml` loading remain later slices;
none of them change this module's shape (`sim_visualization_spec.md` §11.1's own "a new
panel type registers itself... the shell does not change").
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from adas_sim.core.history import Interaction
from adas_sim.core.runner import (
    LoadCancelled, SceneCache, build_reactive_layers, build_session_from_recording, build_static_scene,
)
from adas_sim.core.session import Session
from adas_sim.render.bev import render_scene
from adas_sim.render.theme import Theme
from adas_sim.scene.types import Layer
from adas_sim.view.layers import LayerTreeState
from adas_sim.view.viewport import Viewport

_CHECK_STATES = {
    "on": QtCore.Qt.CheckState.Checked,
    "off": QtCore.Qt.CheckState.Unchecked,
    "mixed": QtCore.Qt.CheckState.PartiallyChecked,
}


def set_high_dpi_policy() -> None:
    """P-7: set before the `QApplication` object exists, on both platforms."""
    QtGui.QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )


def _config_root() -> Path:
    """P-7: `QStandardPaths.AppConfigLocation` -- never `%LOCALAPPDATA%` or
    `~/.config` written by hand. Tests redirect this with
    `QStandardPaths.setTestModeEnabled(True)` rather than monkeypatching."""
    base = QtCore.QStandardPaths.writableLocation(
        QtCore.QStandardPaths.StandardLocation.AppConfigLocation
    )
    return Path(base) / "adas-sim"


def layers_state_path(project: str, pipeline: str) -> Path:
    """Per (project, pipeline) -- `sim_visualization_spec.md` §6."""
    return _config_root() / "layers" / f"{project}.{pipeline}.json"


def layout_path(project: str) -> Path:
    """Per project only -- §11.1: "a layout is saveable per project"."""
    return _config_root() / "layout" / f"{project}.bin"


class _SessionLoadWorker(QtCore.QObject):
    """Pass 1, off the GUI thread. Constructed on the GUI thread, then
    `moveToThread`'d before `run()` is invoked (`MainWindow` owns the
    `QThread`)."""

    progress = QtCore.Signal(int, int)
    loaded = QtCore.Signal(object)  # Session
    cancelled = QtCore.Signal()
    failed = QtCore.Signal(str)

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path
        self._cancel_requested = False

    def request_cancel(self) -> None:
        """Thread-safe: a single bool flip, read cooperatively by `run()`
        (`UT-B3-16`) -- never a hard thread kill."""
        self._cancel_requested = True

    def run(self) -> None:
        try:
            session = build_session_from_recording(
                self._path,
                on_progress=lambda done, total: self.progress.emit(done, total),
                is_cancelled=lambda: self._cancel_requested,
            )
        except LoadCancelled:
            self.cancelled.emit()
            return
        except Exception as exc:  # noqa: BLE001 -- surfaced to the GUI, never crashes the worker thread
            self.failed.emit(str(exc))
            return
        self.loaded.emit(session)


class BevPanel(QtWidgets.QDockWidget):
    """The first peer panel (`sim_visualization_spec.md` §11.1): a raster
    from `render/bev.py` shown in a plain label. Pan/zoom/follow-mode
    controls and the scrub bar are a later slice -- this panel exists to
    prove the shell and the threading model, not the full viewport feature
    set."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("BEV", parent)
        self.setObjectName("dock.bev")  # stable id `saveState()`/`restoreState()` match on
        self._label = QtWidgets.QLabel()
        self._label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setWidget(self._label)
        self.viewport = Viewport()
        self.theme: Theme = "dark"

    def show_frame(self, frame: np.ndarray) -> None:
        frame = np.ascontiguousarray(frame)
        height, width, _channels = frame.shape
        image = QtGui.QImage(frame.data, width, height, width * 3, QtGui.QImage.Format.Format_RGB888)
        self._label.setPixmap(QtGui.QPixmap.fromImage(image))

    def pixmap(self) -> QtGui.QPixmap:
        return self._label.pixmap()


class LayersPanel(QtWidgets.QDockWidget):
    """The layer tree (`sim_visualization_spec.md` §6): groups with a
    tri-state checkbox, layers with a plain one, a search box, and
    `Alt`+click on a group to solo it. Every decision is a call into
    `state` (`view/layers.py`); this class only arranges the tree and
    dispatches clicks (`GT-9`)."""

    changed = QtCore.Signal()

    def __init__(self, state: LayerTreeState, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("Layers", parent)
        self.setObjectName("dock.layers")  # stable id `saveState()`/`restoreState()` match on
        self.state = state
        self._updating = False

        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)

        self._search_box = QtWidgets.QLineEdit()
        self._search_box.setPlaceholderText("search layers...")
        self._search_box.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search_box)

        self._tree = QtWidgets.QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.itemChanged.connect(self._on_item_changed)
        self._tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._tree)

        self.setWidget(container)

    def sync_from_scene(self, layers: tuple[Layer, ...]) -> None:
        self.state.sync(layers)
        self._rebuild()

    def _rebuild(self) -> None:
        self._updating = True
        self._tree.clear()
        for group in self.state.groups():
            title = f"{group} (solo)" if self.state.solo_group == group else group
            group_item = QtWidgets.QTreeWidgetItem([title])
            group_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, ("group", group))
            group_item.setFlags(group_item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            group_item.setCheckState(0, _CHECK_STATES[self.state.group_state(group)])
            self._tree.addTopLevelItem(group_item)
            for info in self.state.layers_in_group(group):
                if not self.state.matches_search(info.id):
                    continue
                layer_item = QtWidgets.QTreeWidgetItem([info.label])
                layer_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, ("layer", info.id))
                layer_item.setFlags(layer_item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
                checked = QtCore.Qt.CheckState.Checked if self.state.is_visible(info.id) \
                    else QtCore.Qt.CheckState.Unchecked
                layer_item.setCheckState(0, checked)
                group_item.addChild(layer_item)
        self._tree.expandAll()
        self._updating = False

    def _on_item_changed(self, item: QtWidgets.QTreeWidgetItem, _column: int) -> None:
        if self._updating:
            return
        kind, key = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        checked = item.checkState(0) == QtCore.Qt.CheckState.Checked
        if kind == "layer":
            self.state.set_visible(key, checked)
        else:
            self.state.set_group_visible(key, checked)
        self._rebuild()
        self.changed.emit()

    def _on_item_clicked(self, item: QtWidgets.QTreeWidgetItem, _column: int) -> None:
        kind, key = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if kind != "group":
            return
        if QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.KeyboardModifier.AltModifier:
            self.state.toggle_solo(key)
            self._rebuild()
            self.changed.emit()

    def _on_search_changed(self, text: str) -> None:
        self.state.set_search(text)
        self._rebuild()


class MainWindow(QtWidgets.QMainWindow):
    """Vantage's window (`sim_player.md` names the application). A
    **dockable peer-panel grid** (`sim_visualization_spec.md` §11.1) -- today
    just the BEV panel; layers/inspector/timeline/plots/pipeline dock in
    alongside it as later slices land."""

    def __init__(self, recording: Path, *, project: str = "base",
                 parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Vantage")
        self._project = project
        self._session: Session | None = None
        self._scene_cache: SceneCache | None = None
        self._current_tick = 0

        self.bev = BevPanel(self)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.bev)

        self.layers_state = LayerTreeState()
        self.layers_panel = LayersPanel(self.layers_state, self)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.layers_panel)
        self.layers_panel.changed.connect(self._on_layers_changed)

        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self.bev.toggleViewAction())
        view_menu.addAction(self.layers_panel.toggleViewAction())

        self.restore_layout()

        self._thread = QtCore.QThread(self)
        self._worker = _SessionLoadWorker(recording)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.loaded.connect(self._on_loaded)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

    @property
    def session(self) -> Session | None:
        return self._session

    def request_cancel_load(self) -> None:
        self._worker.request_cancel()

    def save_layout(self) -> None:
        """The dock grid's arrangement -- open/close, split, tab, float --
        per project (§11.1). `saveState()` matches docks by `objectName()`,
        which is why `BevPanel`/`LayersPanel` set one."""
        path = layout_path(self._project)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bytes(self.saveState()))

    def restore_layout(self) -> bool:
        path = layout_path(self._project)
        if not path.is_file():
            return False
        return self.restoreState(QtCore.QByteArray(path.read_bytes()))

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802 -- Qt override
        self.save_layout()
        super().closeEvent(event)

    def _stop_thread(self) -> None:
        self._thread.quit()
        self._thread.wait()

    def _on_progress(self, done: int, total: int) -> None:
        self.statusBar().showMessage(f"loading... {done}/{total}")

    def _on_loaded(self, session: Session) -> None:
        self._session = session
        self._scene_cache = SceneCache(self._build_scene_for_cache, build_reactive=self._build_reactive_for_cache)
        self._stop_thread()
        self.layers_state.load(layers_state_path(self._project, session.meta.pipeline))
        self.statusBar().showMessage(f"loaded {session.name} -- {len(session)} ticks", 5000)
        self.render_tick(0)

    def _on_layers_changed(self) -> None:
        self.render_tick(self._current_tick)
        if self._session is not None:
            self.layers_state.save(layers_state_path(self._project, self._session.meta.pipeline))

    def _on_cancelled(self) -> None:
        self._stop_thread()
        self.statusBar().showMessage("load cancelled")

    def _on_failed(self, message: str) -> None:
        self._stop_thread()
        self.statusBar().showMessage(f"load failed: {message}")

    def _build_scene_for_cache(self, tick_index: int, layer_selection: frozenset[str], theme: str) -> object:
        del layer_selection, theme  # Scene assembly needs neither -- see build_scene's own docstring
        return build_static_scene(self._session, tick_index, project=self._project)

    def _build_reactive_for_cache(
        self, tick_index: int, layer_selection: frozenset[str], theme: str, interaction: Interaction,
    ) -> tuple:
        del layer_selection, theme
        return build_reactive_layers(self._session, tick_index, project=self._project, interaction=interaction)

    def render_tick(self, tick_index: int, *, interaction: Interaction = Interaction()) -> None:
        """GUI-thread only: reads `_scene_cache`, never re-runs pass 1.
        Scene assembly is cached ignoring layer selection (`build_scene`
        needs neither, `core/runner.py`'s own docstring); the layers panel's
        choice is applied only at rasterising, which is why toggling a layer
        re-renders without re-running pass 1 *or* pass 2a. `interaction`
        defaults to a no-op -- no panel drives cursor/selection yet (that is
        `view/measure.py`/`view/inspector.py`'s job); a provider declaring
        `reacts_to` is already correctly wired to it (`sim_visualization_spec.md`
        §7.5, `SceneCache`'s reactive tier)."""
        if self._session is None or self._scene_cache is None:
            return
        self._current_tick = tick_index
        scene = self._scene_cache.get(tick_index, frozenset(), self.bev.theme, interaction)
        self.layers_panel.sync_from_scene(scene.layers)
        layer_selection = self.layers_state.visible_layer_ids()
        frame = render_scene(scene, self.bev.viewport, self.bev.theme, layer_selection)
        self.bev.show_frame(frame)
