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
`%LOCALAPPDATA%`/`~/.config` path. **Slice 4** activated `Interaction` on
`LayerCtx` (`reacts_to=`, `SceneCache`'s reactive tier) with no panel driving
it yet. **Slice 5 is that panel, for selection:** `BevPanel` click-to-select
(`Ctrl`+click to multi-select, `Esc` to clear) resolves through
`render/bev.hit_test` (already built and tested in `S-B1`, `UT-B1-10`) into
`MainWindow._selection`, which `render_tick` folds into both the `Interaction`
it was already passing to `SceneCache` (Slice 4) and a new `selection=`
argument to `render_scene` (§7.1's styling-plus-halo). The docked
`InspectorPanel` (`view/inspector.py`) shows the resolved entities' declared
`Prim.fields` live, with pin and copy-as-text. Slice 6 built the signal
resolver (`core/signals.py`, not a `view/` file -- `Session.signal()`
needed it, `sim_api_reference.md` §2.3). **Slice 7a wires `Viewport` (§4)
into `BevPanel`:** drag-to-pan and wheel-to-zoom live in
`_ClickableImageLabel` (which now tells a click from a drag by movement
past `_DRAG_THRESHOLD_PX`, deferring `clicked` to release); `F`/`0`/`R`/
`1`-`9` are `MainWindow` shortcuts (fit-to-content, reset, cycle follow
mode, jump to a `DEFAULT_PRESETS` entry) since they need the current Scene
or session, which `BevPanel` itself does not hold. Follow mode is real,
cyclable `Viewport` state with **no rendering effect yet** -- a documented
gap, not an oversight (see `_on_cycle_follow_mode`'s own docstring).
Timeline, plots and measure remain later slices; the scrub bar
(`view/transport.py`'s `Transport`, already built and tested in `S-B2`,
still unwired to any panel) is next. None of this changes the module's
shape (`sim_visualization_spec.md` §11.1's own "a new panel type registers
itself... the shell does not change").
"""

from __future__ import annotations

import dataclasses
import functools
from collections.abc import Callable
from pathlib import Path

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from adas_sim.core.history import Interaction
from adas_sim.core.runner import (
    LoadCancelled, SceneCache, build_reactive_layers, build_session_from_recording, build_static_scene,
)
from adas_sim.core.session import Session
from adas_sim.render.bev import hit_test, render_scene, scene_bounds_m
from adas_sim.render.theme import Theme
from adas_sim.scene.types import Layer, Scene
from adas_sim.view.inspector import InspectorState, copy_as_text
from adas_sim.view.layers import LayerTreeState
from adas_sim.view.viewport import DEFAULT_PRESETS, Viewport

_CHECK_STATES = {
    "on": QtCore.Qt.CheckState.Checked,
    "off": QtCore.Qt.CheckState.Unchecked,
    "mixed": QtCore.Qt.CheckState.PartiallyChecked,
}

#: `R` cycles these three (§4.4) -- `locked:<pick_id>` is entered by
#: locking onto a selection, not by cycling into it (a later slice).
_FOLLOW_MODE_CYCLE = ("ego_forward", "ego_heading", "world")


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


#: A drag shorter than this (pixmap-relative pixels) is a click, not a pan --
#: real mice/trackpads jitter a pixel or two even on an intended click.
_DRAG_THRESHOLD_PX = 3.0


class _ClickableImageLabel(QtWidgets.QLabel):
    """Click-to-select, drag-to-pan and wheel-to-zoom, all in
    **pixmap-relative** pixel coordinates (`sim_visualization_spec.md` §4.4,
    §7.1) -- `AlignCenter` centres the pixmap within the label whenever the
    label is larger, so a raw `event.position()` would be off by that
    offset; this corrects for it once, here, rather than in every caller.

    A click only fires on release, and only if the press never moved past
    `_DRAG_THRESHOLD_PX` -- otherwise it was a pan, not a click, and
    `dragged` fires instead (once per mouse-move step, so the caller can
    apply `Viewport.panned` incrementally and each step's own "invariant
    point" reasoning stays correct)."""

    clicked = QtCore.Signal(float, float, QtCore.Qt.KeyboardModifiers)
    dragged = QtCore.Signal(float, float, float, float)  # from_x, from_y, to_x, to_y
    zoomed = QtCore.Signal(float, float, float)  # factor, cursor_x, cursor_y

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._press_pos: QtCore.QPointF | None = None
        self._press_modifiers = QtCore.Qt.KeyboardModifier.NoModifier
        self._last_pos: QtCore.QPointF | None = None
        self._dragging = False

    def _pixmap_relative(self, event_pos: QtCore.QPointF) -> QtCore.QPointF:
        pixmap = self.pixmap()
        if pixmap is None or pixmap.isNull():
            return event_pos
        offset_x = (self.width() - pixmap.width()) / 2.0
        offset_y = (self.height() - pixmap.height()) / 2.0
        return QtCore.QPointF(event_pos.x() - offset_x, event_pos.y() - offset_y)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802 -- Qt override
        self._press_pos = self._last_pos = self._pixmap_relative(event.position())
        self._press_modifiers = event.modifiers()
        self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802 -- Qt override
        if self._last_pos is not None and event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            pos = self._pixmap_relative(event.position())
            delta = ((pos.x() - self._press_pos.x()) ** 2 + (pos.y() - self._press_pos.y()) ** 2) ** 0.5
            if self._dragging or delta > _DRAG_THRESHOLD_PX:
                self._dragging = True
                self.dragged.emit(self._last_pos.x(), self._last_pos.y(), pos.x(), pos.y())
                self._last_pos = pos
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802 -- Qt override
        if not self._dragging and self._press_pos is not None:
            self.clicked.emit(self._press_pos.x(), self._press_pos.y(), self._press_modifiers)
        self._press_pos = self._last_pos = None
        self._dragging = False
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:  # noqa: N802 -- Qt override
        # 120 units/notch is Qt's own documented constant, not a magic number.
        factor = 1.15 ** (event.angleDelta().y() / 120.0)
        pos = self._pixmap_relative(event.position())
        self.zoomed.emit(factor, pos.x(), pos.y())
        event.accept()


class BevPanel(QtWidgets.QDockWidget):
    """The first peer panel (`sim_visualization_spec.md` §11.1): a raster
    from `render/bev.py` shown in a plain label, with pan/zoom wired
    (Slice 7a). Follow modes and fit/preset keys are `MainWindow`'s job
    (they need the current Scene/session, which this panel does not hold);
    the scrub bar is a later slice."""

    clicked = QtCore.Signal(float, float, QtCore.Qt.KeyboardModifiers)
    dragged = QtCore.Signal(float, float, float, float)
    zoomed = QtCore.Signal(float, float, float)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("BEV", parent)
        self.setObjectName("dock.bev")  # stable id `saveState()`/`restoreState()` match on
        self._label = _ClickableImageLabel()
        self._label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._label.clicked.connect(self.clicked)
        self._label.dragged.connect(self.dragged)
        self._label.zoomed.connect(self.zoomed)
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


class InspectorPanel(QtWidgets.QDockWidget):
    """The docked inspector (`sim_visualization_spec.md` §7.2): one entry
    per selected/pinned entity, expandable to its declared `Prim.fields`.
    Resolution, pin and "drop when gone" all live in `state`
    (`view/inspector.py`); this class only arranges the tree and dispatches
    the pin/copy-as-text context menu (`GT-9`)."""

    def __init__(self, state: InspectorState, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("Inspector", parent)
        self.setObjectName("dock.inspector")  # stable id `saveState()`/`restoreState()` match on
        self.state = state
        self._last_scene: Scene | None = None
        self._last_selection: frozenset[str] = frozenset()

        self._tree = QtWidgets.QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self.setWidget(self._tree)

    def sync(self, scene: Scene, selection: frozenset[str]) -> None:
        self._last_scene = scene
        self._last_selection = selection
        self._rebuild()

    def _rebuild(self) -> None:
        self._tree.clear()
        if self._last_scene is None:
            return
        for entry in self.state.entries(self._last_scene, self._last_selection):
            title = f"{entry.pick_id} [pinned]" if entry.pinned else entry.pick_id
            item = QtWidgets.QTreeWidgetItem([title])
            item.setData(0, QtCore.Qt.ItemDataRole.UserRole, entry.pick_id)
            for name, value in entry.fields:
                item.addChild(QtWidgets.QTreeWidgetItem([f"{name}: {value}"]))
            self._tree.addTopLevelItem(item)
        self._tree.expandAll()

    def _on_context_menu(self, pos: QtCore.QPoint) -> None:
        item = self._tree.itemAt(pos)
        if item is None or item.parent() is not None or self._last_scene is None:
            return
        pick_id = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        menu = QtWidgets.QMenu(self)
        pin_action = menu.addAction("Unpin" if self.state.is_pinned(pick_id) else "Pin")
        copy_action = menu.addAction("Copy as text")
        chosen = menu.exec(self._tree.viewport().mapToGlobal(pos))
        if chosen is pin_action:
            self.state.toggle_pin(pick_id)
            self._rebuild()
        elif chosen is copy_action:
            entry = next(e for e in self.state.entries(self._last_scene, self._last_selection)
                         if e.pick_id == pick_id)
            QtWidgets.QApplication.clipboard().setText(copy_as_text(entry))


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
        self._current_scene: Scene | None = None
        #: pick_ids (`sim_visualization_spec.md` §7.1) -- persists across
        #: ticks by construction: nothing here is tick-indexed.
        self._selection: frozenset[str] = frozenset()

        self.bev = BevPanel(self)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.bev)
        self.bev.clicked.connect(self._on_bev_clicked)
        self.bev.dragged.connect(self._on_bev_dragged)
        self.bev.zoomed.connect(self._on_bev_zoomed)

        self.layers_state = LayerTreeState()
        self.layers_panel = LayersPanel(self.layers_state, self)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.layers_panel)
        self.layers_panel.changed.connect(self._on_layers_changed)

        self.inspector_state = InspectorState()
        self.inspector_panel = InspectorPanel(self.inspector_state, self)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.inspector_panel)

        self._clear_selection_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Esc"), self)
        self._clear_selection_shortcut.activated.connect(self._on_clear_selection)

        self._viewport_shortcuts: list[QtGui.QShortcut] = []
        self._add_viewport_shortcut("F", self._on_fit_to_content)
        self._add_viewport_shortcut("0", self._on_reset_viewport)
        self._add_viewport_shortcut("R", self._on_cycle_follow_mode)
        for digit, preset_name in enumerate(sorted(DEFAULT_PRESETS), start=1):
            self._add_viewport_shortcut(str(digit), functools.partial(self._on_jump_to_preset, preset_name))

        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self.bev.toggleViewAction())
        view_menu.addAction(self.layers_panel.toggleViewAction())
        view_menu.addAction(self.inspector_panel.toggleViewAction())

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
        defaults to a no-op, for a caller feeding `cursor`/`modifiers`/
        `toggles` (`view/measure.py`, later); its `selection` field is always
        overridden from `self._selection` here, so every call site -- not
        just the click handler -- keeps rendering the current selection
        without having to remember to thread it through by hand."""
        if self._session is None or self._scene_cache is None:
            return
        self._current_tick = tick_index
        effective_interaction = dataclasses.replace(interaction, selection=self._selection)
        scene = self._scene_cache.get(tick_index, frozenset(), self.bev.theme, effective_interaction)
        self._current_scene = scene  # unfiltered -- hit_test takes layer_selection itself
        self.layers_panel.sync_from_scene(scene.layers)
        layer_selection = self.layers_state.visible_layer_ids()
        frame = render_scene(scene, self.bev.viewport, self.bev.theme, layer_selection, self._selection)
        self.bev.show_frame(frame)
        # The inspector reflects what's actually drawn, same as hit_test --
        # a hidden layer's entity is gone from the panel too, not just the
        # canvas (a filtered *view* of the Scene, not a second Scene).
        visible_scene = dataclasses.replace(
            scene, layers=tuple(layer for layer in scene.layers if layer.id in layer_selection),
        )
        self.inspector_panel.sync(visible_scene, self._selection)

    def _on_bev_clicked(self, x: float, y: float, modifiers: QtCore.Qt.KeyboardModifiers) -> None:
        """§7.1: click to select, `Ctrl`+click to toggle membership. Hit-tests
        against exactly what's currently drawn (`render/bev.hit_test`, the
        same layer selection `render_tick` just rasterised with) -- a hit on
        a hidden layer's prim cannot select it."""
        if self._current_scene is None:
            return
        layer_selection = self.layers_state.visible_layer_ids()
        pick_id = hit_test(self._current_scene, self.bev.viewport, (x, y), layer_selection)
        if modifiers & QtCore.Qt.KeyboardModifier.ControlModifier:
            if pick_id is None:
                return
            selection = set(self._selection)
            selection.symmetric_difference_update({pick_id})
            self._selection = frozenset(selection)
        else:
            self._selection = frozenset({pick_id}) if pick_id is not None else frozenset()
        self.render_tick(self._current_tick)

    def _on_clear_selection(self) -> None:
        if not self._selection:
            return
        self._selection = frozenset()
        self.render_tick(self._current_tick)

    def _add_viewport_shortcut(self, key: str, slot: Callable[[], None]) -> None:
        shortcut = QtGui.QShortcut(QtGui.QKeySequence(key), self)
        shortcut.activated.connect(slot)
        self._viewport_shortcuts.append(shortcut)

    def _on_bev_dragged(self, from_x: float, from_y: float, to_x: float, to_y: float) -> None:
        """§4.4: drag to pan. `_ClickableImageLabel` already tells apart a
        drag from a click; every emission here is a real pan step."""
        self.bev.viewport = self.bev.viewport.panned((from_x, from_y), (to_x, to_y))
        self.render_tick(self._current_tick)

    def _on_bev_zoomed(self, factor: float, cursor_x: float, cursor_y: float) -> None:
        """§4.4: wheel to zoom **about the cursor**, not the centre --
        `Viewport.zoomed_about_cursor` already carries that invariant."""
        self.bev.viewport = self.bev.viewport.zoomed_about_cursor(factor, (cursor_x, cursor_y))
        self.render_tick(self._current_tick)

    def _on_fit_to_content(self) -> None:
        """`F` (§4.4): fits the currently visible layers' union bounds.
        Nothing to fit (no session loaded, or every visible layer is empty
        this tick) is a silent no-op, not an error -- fitting is a
        convenience, not a claim about the scene."""
        if self._current_scene is None:
            return
        layer_selection = self.layers_state.visible_layer_ids()
        bounds = scene_bounds_m(self._current_scene, layer_selection)
        if bounds is None:
            return
        self.bev.viewport = self.bev.viewport.fitted_to(bounds)
        self.render_tick(self._current_tick)

    def _on_reset_viewport(self) -> None:
        """`0` (§4.4): back to the framework default, keeping only the
        widget-derived `size_px` (that is the dock's actual size, not a
        setting to reset)."""
        self.bev.viewport = Viewport(size_px=self.bev.viewport.size_px)
        self.render_tick(self._current_tick)

    def _on_cycle_follow_mode(self) -> None:
        """`R` (§4.4): cycles `Viewport.follow` through the three
        non-`locked:` modes. **Stores the mode; does not yet change what's
        drawn** -- every mode renders identically until `render/bev.py`
        gains a frame-aware transform pass (today it draws every prim's
        metres directly in viewport space, regardless of `Prim.frame`), a
        gap this slice found but does not close. Kept anyway, same as
        `Interaction` was in Slice 4 before anything reacted to it: real,
        tested state ahead of its consumer, not a fake control."""
        current = self.bev.viewport.follow
        index = _FOLLOW_MODE_CYCLE.index(current) if current in _FOLLOW_MODE_CYCLE else -1
        next_mode = _FOLLOW_MODE_CYCLE[(index + 1) % len(_FOLLOW_MODE_CYCLE)]
        self.bev.viewport = dataclasses.replace(self.bev.viewport, follow=next_mode)
        self.statusBar().showMessage(f"follow: {next_mode}", 2000)

    def _on_jump_to_preset(self, preset_name: str) -> None:
        """`1`…`9` (§4.4): the framework's own generic presets
        (`DEFAULT_PRESETS`), positionally assigned in sorted order. A
        component's own named presets (`viewpoints.yaml`) are `view/
        workspace.py`'s job -- this is the fallback every component starts
        from, same framing as `DEFAULT_PRESETS`'s own docstring."""
        preset = DEFAULT_PRESETS[preset_name]
        self.bev.viewport = dataclasses.replace(preset, size_px=self.bev.viewport.size_px)
        self.render_tick(self._current_tick)
