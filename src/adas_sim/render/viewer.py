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
**Slice 7b wires `Transport` (§5) into `TransportBar`**, a fixed toolbar,
not a dock (§11.1 lists the scrub bar alongside "the menu and the keymap",
not the panels a user rearranges). `Transport` itself (`view/transport.py`)
was already built and fully tested in `S-B2`; this slice is the Qt binding
-- play/pause/step/speed/loop/goto, `Space`/`←`/`→`/`Shift+→`/`L`, and a
`QTimer` whose interval is recomputed every tick from that tick's own
`dt_ns / speed` (ticks need not be equally spaced). `head_tick` is pinned
to the session's last tick at load (the whole recording is already in
memory, so nothing is ever actually "advanced" -- `_advance_for_transport`
exists only to satisfy `Transport`'s constructor and is provably
unreachable); `Transport.__init__` starts `cursor` at `head_tick`, which is
right for a live SUT ("head" is "where execution is now") but wrong for
opening a recording for review, so `_on_loaded` calls `goto(0)` before
binding. **Slice 8 adds `TimelineStrip`** (§7.3), synced with the same
`Transport`: `Session.signal()` (Slice 6) is resolved once per lane-add and
cached (`_signal_series_cache`) -- an O(ticks) pass on every render would
make the strip the render loop's own bottleneck -- and `render/timeline.py`
rasterises with zero-margin per-lane axes (`fig.add_axes`, the same trick
`render/bev.py`'s single axes uses) so click-to-seek's pixel-to-tick
inverse is exact, not approximate. `[`/`]` jump to the nearest state-lane
transition or bookmark. **Slice 9 applies `view/workspace.Workspace`**
(§13b): `MainWindow` takes an optional `workspace_path`, resolved to a
component's `workspace.yaml` or `default_workspace()` (bev + timeline) if
missing -- a malformed file still raises, only a missing one falls back.
Only `tabs[0]` reaches this single-arrangement shell (`bev`'s `viewpoint`
against `DEFAULT_PRESETS`, `timeline`'s `signals` as signal lanes,
uniformly -- the schema does not declare state vs. signal, and guessing
from a resolved value's type would silently misclassify a protobuf enum);
`Workspace.tabs[1:]` parse and validate but nothing applies them yet, a
gap `view/workspace.py`'s own docstring names rather than hides. `View >
Reset Layout` restores `_default_layout_state`, captured once before any
user-saved state is overlaid, byte for byte. **Slice 10 adds `PlotPanel`**
(§7.4) -- unlike `TimelineStrip` (one, fixed), a user opens *several*
(`Plots` menu, `_on_add_plot`), each its own `PlotState`
(`timeseries`/`xy`/`state`/`distribution`). `timeseries`/`state` reuse
`render/timeline.render_timeline` directly (one rendering path, not two,
for lanes that look identical whether they live in the strip or a plot)
and so inherit its exact click-to-seek; `xy`/`distribution` get their own
`render/plots.py` functions and a plain, non-interactive label -- their
axes are scaled to the data, not a fixed range, so the same exact inverse
does not carry over. `_signal_series_cache` (renamed from
`_timeline_series_cache`) is shared by the strip and every plot panel, so
the same address requested by both never resolves twice. **Slice 11 adds
§8's measurement tools, all onto `BevPanel` -- no new dock.** Ruler/range-
rings/annotations are ordinary `Prim`s (`view/measure.MeasureState.
overlay_prims()`) drawn last by the same `render_scene`/`_draw_prim` every
layer provider's own prims go through, never a second canvas-overlay path.
`M` toggles `_measure_mode`, in which dragging the BEV measures instead of
panning (`_ClickableImageLabel` grew `drag_extent_changed` -- press-to-here,
not the incremental `dragged` pan already uses, since panning and ruling
need different arithmetic from the same gesture); `Shift`+click drops an
annotation. Both snap to `render/bev.anchor_points_m` (every selectable
prim's bbox corners + centre) within a fixed **pixel** threshold, not a
metre one -- a metre threshold would snap wildly differently at different
zoom levels. **Cursor readout is deliberately not a `Prim`**: a
`_ClickableImageLabel.hovered` signal (needs `setMouseTracking`) updates a
plain status-bar `QLabel` with no re-render at all -- a full `render_scene`
(a matplotlib figure) on every pixel of mouse travel would make the BEV
laggy, the same class of cost `S-B3`'s playback timer already has to
respect per tick. **Slice 12 adds §10's HUD text and stale banner**, drawn
in **screen space** (`ax.transAxes`) inside `render_scene` itself -- fixed
top-right/top-centre regardless of pan/zoom, which a `Prim` (world-space)
cannot do, so this is a third drawing tier alongside the scene's own
prims and `overlay_prims`, not more of either. Scale/time/tick/project are
always shown (the framework knows them itself); the ego-state line and the
stale-port banner are **caller-supplied** (`__init__`'s `ego_state_signals`/
`max_age_s`, both empty by default) -- the framework has no component
calibration of its own to guess a velocity's address or a max-age-seconds
value from (`R-SIM-1`, `view/hud.py`'s own docstring). **Not built here:**
the origin dot/axis arrows/distance grid §10 also lists -- `modules/df`'s
own `frame_layer` already draws these today, as a component layer in a
different submodule; whether that responsibility moves into framework HUD
furniture is a real, cross-submodule question this slice does not decide
or silently duplicate. **Slice 13 gives `MainWindow` its `cli/` surface**:
`preset`/`initial_at_s` constructor parameters (`sim view <session>
[--preset] [--at]`, `sim_api_reference.md` §10) -- a command-line preset
wins over the workspace's own `tabs[0]` viewpoint (Slice 9), applied last,
after the first real render so it always has a `_current_tick` to
re-render at; `initial_at_s` resolves through `Session.seek_ns` the same
way any other seek does, replacing the `goto(0)` default. `cli/view.py`
and `app/gui.py` (construct `QApplication`, construct this class, run the
event loop) are the only files that ever construct a `MainWindow` outside
a test. None of this changes the module's shape
(`sim_visualization_spec.md` §11.1's own "a new panel type registers
itself... the shell does not change").
"""

from __future__ import annotations

import dataclasses
import functools
from collections.abc import Callable
from pathlib import Path

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from adas_sim.check.expect import ExpectationResult, evaluate_scenario
from adas_sim.contracts.scenario import Scenario, load_scenario
from adas_sim.core.history import Interaction
from adas_sim.core.runner import (
    LoadCancelled, SceneCache, build_reactive_layers, build_session_from_recording, build_static_scene,
)
from adas_sim.core.session import Session
from adas_sim.core.signals import resolve_tick
from adas_sim.render.bev import anchor_points_m, hit_test, render_scene, scene_bounds_m
from adas_sim.render.plots import render_distribution, render_xy
from adas_sim.render.theme import Theme
from adas_sim.render.timeline import px_to_tick, render_timeline
from adas_sim.scene.types import Layer, Scene
from adas_sim.view.inspector import InspectorState, copy_as_text
from adas_sim.view.layers import LayerTreeState
from adas_sim.view.hud import HudInfo, format_hud_lines, format_stale_banner, stale_ports
from adas_sim.view.measure import MeasureState, snap_point
from adas_sim.view.plots import PlotState
from adas_sim.view.timeline import TimelineState, event_markers
from adas_sim.view.transport import Transport
from adas_sim.view.viewport import DEFAULT_PRESETS, Viewport
from adas_sim.view.workspace import default_workspace, load_workspace

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
    point" reasoning stays correct). `drag_extent_changed` fires the same
    moments, but **from the press point**, not the last step -- pan wants
    an increment to chain; the ruler (§8, `MainWindow._measure_mode`) wants
    the whole drag's start and current end, which is a different pair of
    numbers from the same gesture, not derivable from the incremental one
    without accumulating it back up. `hovered` fires on every move
    regardless of button state (`setMouseTracking`), for the cursor
    readout -- deliberately **not** a full re-render (§8's own reasoning,
    see `view/measure.py`'s docstring on why it stays a plain `QLabel`)."""

    clicked = QtCore.Signal(float, float, QtCore.Qt.KeyboardModifiers)
    dragged = QtCore.Signal(float, float, float, float)  # from_x, from_y, to_x, to_y (incremental)
    drag_extent_changed = QtCore.Signal(float, float, float, float)  # press_x, press_y, to_x, to_y
    zoomed = QtCore.Signal(float, float, float)  # factor, cursor_x, cursor_y
    hovered = QtCore.Signal(float, float)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._press_pos: QtCore.QPointF | None = None
        self._press_modifiers = QtCore.Qt.KeyboardModifier.NoModifier
        self._last_pos: QtCore.QPointF | None = None
        self._dragging = False
        self.setMouseTracking(True)

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
        pos = self._pixmap_relative(event.position())
        if self._last_pos is not None and event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            delta = ((pos.x() - self._press_pos.x()) ** 2 + (pos.y() - self._press_pos.y()) ** 2) ** 0.5
            if self._dragging or delta > _DRAG_THRESHOLD_PX:
                self._dragging = True
                self.dragged.emit(self._last_pos.x(), self._last_pos.y(), pos.x(), pos.y())
                self.drag_extent_changed.emit(self._press_pos.x(), self._press_pos.y(), pos.x(), pos.y())
                self._last_pos = pos
        else:
            self.hovered.emit(pos.x(), pos.y())
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
    drag_extent_changed = QtCore.Signal(float, float, float, float)
    zoomed = QtCore.Signal(float, float, float)
    hovered = QtCore.Signal(float, float)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("BEV", parent)
        self.setObjectName("dock.bev")  # stable id `saveState()`/`restoreState()` match on
        self._label = _ClickableImageLabel()
        self._label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._label.clicked.connect(self.clicked)
        self._label.dragged.connect(self.dragged)
        self._label.drag_extent_changed.connect(self.drag_extent_changed)
        self._label.zoomed.connect(self.zoomed)
        self._label.hovered.connect(self.hovered)
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


#: `0.1x` .. `8x` (`sim_visualization_spec.md` §5's own table); "as fast as
#: it renders" is what `_MAX_SPEED` already means once the render loop, not
#: the timer interval, is the bottleneck -- no separate mode needed for it.
_SPEEDS = (0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0)


class TransportBar(QtWidgets.QToolBar):
    """The scrub bar (`sim_visualization_spec.md` §5) -- framework chrome,
    not a peer dock: §11.1 lists "the scrub bar, the timeline strip, the
    menu and the keymap" separately from the docks a user rearranges, so
    this is a fixed, non-floatable, non-closable toolbar rather than a
    `QDockWidget`.

    Owns no `Transport` of its own -- `bind()` attaches one once a session
    has loaded (nothing is scrubbable before that); every action here reads
    and mutates the bound `Transport` directly and emits `changed`, which
    is `MainWindow`'s cue to re-render and re-sync (`GT-9`: this class
    arranges and dispatches, `view/transport.Transport` already holds every
    decision -- head/review-mode, clamping, resume-eligibility)."""

    changed = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("Transport", parent)
        self.setObjectName("toolbar.transport")
        self.setMovable(False)
        self.setFloatable(False)
        self._transport: Transport | None = None
        self._updating = False

        style = self.style()
        self._play_action = self.addAction(
            style.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPlay), "Play/pause")
        self._play_action.triggered.connect(self.toggle_play_pause)
        self.addAction(
            style.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaSkipBackward), "Step back",
        ).triggered.connect(lambda: self.step(-1))
        self.addAction(
            style.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaSkipForward), "Step forward",
        ).triggered.connect(lambda: self.step(1))

        self._slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self._slider.setMinimum(0)
        self._slider.valueChanged.connect(self._on_slider_moved)
        self.addWidget(self._slider)

        self._tick_label = QtWidgets.QLabel("tick 0/0")
        self.addWidget(self._tick_label)

        self._speed_box = QtWidgets.QComboBox()
        for speed in _SPEEDS:
            self._speed_box.addItem(f"{speed:g}x", speed)
        self._speed_box.setCurrentIndex(_SPEEDS.index(1.0))
        self._speed_box.currentIndexChanged.connect(self._on_speed_changed)
        self.addWidget(self._speed_box)

        self.addAction("Loop start").triggered.connect(self._on_set_loop_start)
        self.addAction("Loop end").triggered.connect(self._on_set_loop_end)
        self._loop_action = self.addAction("Loop")
        self._loop_action.setCheckable(True)

    def bind(self, transport: Transport) -> None:
        self._transport = transport
        self.sync()

    @property
    def loop_active(self) -> bool:
        return self._loop_action.isChecked()

    def sync(self) -> None:
        """Reflects the bound `Transport`'s current state. Blocks the
        slider's own signal while setting it, so a programmatic sync can
        never recurse into `_on_slider_moved` (which would re-`goto()` and
        re-emit `changed`)."""
        if self._transport is None:
            return
        self._updating = True
        self._slider.setMaximum(max(0, self._transport.head_tick))
        self._slider.setValue(self._transport.cursor)
        self._updating = False
        self._tick_label.setText(f"tick {self._transport.cursor}/{self._transport.head_tick}")
        icon = QtWidgets.QStyle.StandardPixmap.SP_MediaPause if self._transport.playing \
            else QtWidgets.QStyle.StandardPixmap.SP_MediaPlay
        self._play_action.setIcon(self.style().standardIcon(icon))

    def toggle_play_pause(self) -> None:
        if self._transport is None:
            return
        self._transport.pause() if self._transport.playing else self._transport.play()
        self.sync()
        self.changed.emit()

    def step(self, n: int) -> None:
        if self._transport is None:
            return
        self._transport.step_forward(n) if n > 0 else self._transport.step_back(-n)
        self.sync()
        self.changed.emit()

    def toggle_loop(self) -> None:
        self._loop_action.setChecked(not self._loop_action.isChecked())

    def _on_slider_moved(self, value: int) -> None:
        if self._updating or self._transport is None:
            return
        self._transport.goto(value)
        self.sync()
        self.changed.emit()

    def _on_speed_changed(self, index: int) -> None:
        if self._transport is not None:
            self._transport.speed = self._speed_box.itemData(index)

    def _on_set_loop_start(self) -> None:
        if self._transport is None:
            return
        end = self._transport.loop_marks[1] if self._transport.loop_marks else self._transport.cursor
        self._transport.loop_marks = (self._transport.cursor, max(end, self._transport.cursor))

    def _on_set_loop_end(self) -> None:
        if self._transport is None:
            return
        start = self._transport.loop_marks[0] if self._transport.loop_marks else self._transport.cursor
        self._transport.loop_marks = (min(start, self._transport.cursor), self._transport.cursor)


#: Fixed, not the widget's real size -- same simplification `BevPanel.viewport`
#: already makes (`Viewport.size_px` is not yet synced to a live resize either,
#: Slice 7a's own documented gap); a later slice fixes both together.
_TIMELINE_SIZE_PX = (900, 160)


class TimelineStrip(QtWidgets.QDockWidget):
    """The synced signal strip (`sim_visualization_spec.md` §7.3), always
    under the BEV. Reuses `_ClickableImageLabel` for click-to-seek (its
    `dragged`/`zoomed` signals are simply not connected to anything here --
    a strip is seek-only, no pan/zoom of its own). Resolution, lane
    bookkeeping and event-marker detection all live in `view/timeline.py`/
    `core/signals.py`; this class only rasterises (`render/timeline.py`)
    and dispatches a click to a tick index (`GT-9`)."""

    seek_requested = QtCore.Signal(int)

    def __init__(self, state: TimelineState, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("Timeline", parent)
        self.setObjectName("dock.timeline")
        self.state = state
        self.size_px = _TIMELINE_SIZE_PX
        self._head_tick = 0  # set by MainWindow before every render, from Transport.head_tick
        self._label = _ClickableImageLabel()
        self._label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._label.clicked.connect(self._on_clicked)
        self.setWidget(self._label)

    def show_frame(self, frame: np.ndarray) -> None:
        frame = np.ascontiguousarray(frame)
        height, width, _channels = frame.shape
        image = QtGui.QImage(frame.data, width, height, width * 3, QtGui.QImage.Format.Format_RGB888)
        self._label.setPixmap(QtGui.QPixmap.fromImage(image))

    def pixmap(self) -> QtGui.QPixmap:
        return self._label.pixmap()

    def _on_clicked(self, x: float, y: float, modifiers: QtCore.Qt.KeyboardModifiers) -> None:
        del y, modifiers
        self.seek_requested.emit(px_to_tick(x, self.size_px, self._head_tick))


#: Fixed, same simplification `_TIMELINE_SIZE_PX` already makes.
_PLOT_SIZE_PX = (500, 300)


def _numeric_series(series: tuple) -> tuple:
    """`xy`/`distribution` (`render/plots.py`) plot real numbers -- a
    resolved value that isn't one (raw bytes with no schema, a protobuf
    sub-message with no field path given) is dropped rather than handed to
    matplotlib, which would not crash but would draw silent garbage.
    `bool` is excluded even though it is technically `int` (`True`/`False`
    are not points on a numeric axis)."""
    return tuple((t, v) for t, v in series if isinstance(v, (int, float)) and not isinstance(v, bool))


class PlotPanel(QtWidgets.QDockWidget):
    """One plot panel (`sim_visualization_spec.md` §7.4) -- unlike the one
    fixed `TimelineStrip`, a user opens **several** of these
    (`MainWindow._on_add_plot`), each with its own `PlotState`.
    `timeseries`/`state` reuse `_ClickableImageLabel` for click-to-seek,
    the same exact pixel-to-tick inverse `TimelineStrip` has (`§7.3`'s
    lane drawing, shared via `render/timeline.render_timeline`); `xy`/
    `distribution` use a plain, non-interactive `QLabel` -- their axes are
    scaled to the data, not click-seekable (`render/plots.py`'s own
    docstring)."""

    seek_requested = QtCore.Signal(int)

    def __init__(self, state: PlotState, panel_id: int, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(f"Plot: {state.kind} #{panel_id}", parent)
        self.setObjectName(f"dock.plot.{panel_id}")
        self.state = state
        self.size_px = _PLOT_SIZE_PX
        self._head_tick = 0
        if state.kind in ("timeseries", "state"):
            label = _ClickableImageLabel()
            label.clicked.connect(self._on_clicked)
            self._label = label
        else:
            self._label = QtWidgets.QLabel()
        self._label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setWidget(self._label)

    def show_frame(self, frame: np.ndarray) -> None:
        frame = np.ascontiguousarray(frame)
        height, width, _channels = frame.shape
        image = QtGui.QImage(frame.data, width, height, width * 3, QtGui.QImage.Format.Format_RGB888)
        self._label.setPixmap(QtGui.QPixmap.fromImage(image))

    def pixmap(self) -> QtGui.QPixmap:
        return self._label.pixmap()

    def _on_clicked(self, x: float, y: float, modifiers: QtCore.Qt.KeyboardModifiers) -> None:
        del y, modifiers
        self.seek_requested.emit(px_to_tick(x, self.size_px, self._head_tick))


def _index_expectation_windows(
    scenario: Scenario | None, session: Session,
) -> dict[str, tuple[ExpectationResult, ...]]:
    """`scenario`'s own `expect:` block, evaluated once against
    `session.ticks` (`evaluate_scenario` -- the same call `sim check` makes,
    `R-SIM-8`'s "one evaluator, five consumers" extended to the viewer) and
    indexed by signal address for `_rerender_timeline`'s per-lane lookup.
    `{}` when no `--scenario` was given -- the overlay is then simply
    absent, never a guessed pass (`NR-SIM-4`)."""
    if scenario is None:
        return {}
    windows: dict[str, list[ExpectationResult]] = {}
    for result in evaluate_scenario(scenario, session.ticks):
        if result.window_s is not None:
            windows.setdefault(result.signal, []).append(result)
    return {signal: tuple(results) for signal, results in windows.items()}


class MainWindow(QtWidgets.QMainWindow):
    """Vantage's window (`sim_player.md` names the application). A
    **dockable peer-panel grid** (`sim_visualization_spec.md` §11.1) -- today
    just the BEV panel; layers/inspector/timeline/plots/pipeline dock in
    alongside it as later slices land."""

    def __init__(self, recording: Path, *, project: str = "base",
                 workspace_path: Path | None = None,
                 ego_state_signals: dict[str, str] | None = None,
                 max_age_s: dict[str, float] | None = None,
                 preset: str | None = None,
                 initial_at_s: float | None = None,
                 scenario_path: Path | None = None,
                 parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Vantage")
        self._project = project
        #: `sim view <session> [--preset] [--at]` (`sim_api_reference.md`
        #: §10) -- applied once, in `_on_loaded`, after the workspace's own
        #: `tabs[0]` viewpoint (a command-line preset is a more specific
        #: request than the shipped default, so it wins).
        self._initial_preset = preset
        self._initial_at_s = initial_at_s
        # `--scenario` (`sim_visualization_spec.md` SS7.3's expectation
        # windows): explicit, never guessed -- a recording's own run
        # manifest carries only the scenario's NAME (`RunManifest.scenario`),
        # not a path back to the file. Loaded eagerly (a malformed file is
        # an authoring bug, not the same failure mode as `--scenario` simply
        # not given, same distinction `workspace_path` draws below);
        # evaluated against `session.ticks` lazily in `_on_loaded`, once,
        # since the scenario alone has nothing to evaluate against yet.
        self._scenario: Scenario | None = (
            load_scenario(scenario_path) if scenario_path is not None else None
        )
        #: signal address -> every `ExpectationResult` naming it with a
        #: drawable `window_s` (`check/expect.py`) -- several expectations
        #: can share one signal (`sim_mergein_vlat025.yaml`'s own `EXP-1`/
        #: `EXP-2` both address `left.warning`), so this is a list per
        #: address, not a single result. Populated once in `_on_loaded`,
        #: read (never re-evaluated) by `_rerender_timeline`.
        self._expectation_windows: dict[str, tuple[ExpectationResult, ...]] = {}
        # §10's ego-state line and stale-port max-age both need a value the
        # framework does not have on its own (R-SIM-1) -- a signal address
        # per HUD field, and a calibration seconds-value per port. Both
        # caller-supplied, both empty (HUD line/banner simply absent) by
        # default (`view/hud.py`'s own docstring).
        self._ego_state_signals = ego_state_signals or {}
        self._max_age_s = max_age_s or {}
        # §13b: "a missing workspace is not an error" -- the caller decides
        # what "missing" means by handing (or not handing) a path; a
        # malformed file, unlike a missing one, still raises (a workspace.yaml
        # authoring bug is not the same failure mode as none existing).
        self.workspace = load_workspace(workspace_path) if workspace_path is not None \
            and workspace_path.is_file() else default_workspace()
        self._session: Session | None = None
        self._scene_cache: SceneCache | None = None
        self._current_tick = 0
        self._current_scene: Scene | None = None
        #: pick_ids (`sim_visualization_spec.md` §7.1) -- persists across
        #: ticks by construction: nothing here is tick-indexed.
        self._selection: frozenset[str] = frozenset()
        self.transport: Transport | None = None
        self._playback_timer = QtCore.QTimer(self)
        self._playback_timer.timeout.connect(self._on_playback_tick)
        self.measure_state = MeasureState()
        #: `M` toggles this (§8): while on, dragging the BEV measures
        #: instead of panning -- the two are mutually exclusive on one
        #: mouse gesture, never simultaneous.
        self._measure_mode = False

        self.bev = BevPanel(self)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.bev)
        self.bev.clicked.connect(self._on_bev_clicked)
        self.bev.dragged.connect(self._on_bev_dragged)
        self.bev.drag_extent_changed.connect(self._on_bev_drag_extent_changed)
        self.bev.zoomed.connect(self._on_bev_zoomed)
        self.bev.hovered.connect(self._on_bev_hovered)
        self._apply_workspace_viewpoint()

        self._cursor_readout_label = QtWidgets.QLabel("")
        self.statusBar().addPermanentWidget(self._cursor_readout_label)

        self.layers_state = LayerTreeState()
        self.layers_panel = LayersPanel(self.layers_state, self)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.layers_panel)
        self.layers_panel.changed.connect(self._on_layers_changed)

        self.inspector_state = InspectorState()
        self.inspector_panel = InspectorPanel(self.inspector_state, self)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.inspector_panel)

        self.timeline_state = TimelineState()
        #: address -> resolved (tick_index, value) series -- resolved once
        #: per lane-add, never per render (`Session.signal` is an O(ticks)
        #: pass; re-resolving on every tick, e.g. during playback, would
        #: make the strip/a plot panel the render loop's actual bottleneck).
        #: Shared between `TimelineStrip` and every `PlotPanel` -- the same
        #: address requested by both never resolves twice (`NR-SIM-8`: one
        #: resolver, five consumers, extended to "one cache").
        self._signal_series_cache: dict[str, tuple] = {}
        self.timeline_strip = TimelineStrip(self.timeline_state, self)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self.timeline_strip)
        self.timeline_strip.seek_requested.connect(self._on_timeline_seek)

        self.plot_panels: list[PlotPanel] = []

        self._clear_selection_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Esc"), self)
        self._clear_selection_shortcut.activated.connect(self._on_clear_selection)

        self.transport_bar = TransportBar(self)
        self.addToolBar(QtCore.Qt.ToolBarArea.BottomToolBarArea, self.transport_bar)
        self.transport_bar.changed.connect(self._on_transport_changed)

        self._shortcuts: list[QtGui.QShortcut] = []
        self._add_shortcut("F", self._on_fit_to_content)
        self._add_shortcut("0", self._on_reset_viewport)
        self._add_shortcut("R", self._on_cycle_follow_mode)
        for digit, preset_name in enumerate(sorted(DEFAULT_PRESETS), start=1):
            self._add_shortcut(str(digit), functools.partial(self._on_jump_to_preset, preset_name))
        self._add_shortcut("Space", self.transport_bar.toggle_play_pause)
        self._add_shortcut("Right", functools.partial(self.transport_bar.step, 1))
        self._add_shortcut("Left", functools.partial(self.transport_bar.step, -1))
        self._add_shortcut("Shift+Right", functools.partial(self.transport_bar.step, 10))
        self._add_shortcut("L", self.transport_bar.toggle_loop)
        self._add_shortcut("]", functools.partial(self._on_jump_to_event, 1))
        self._add_shortcut("[", functools.partial(self._on_jump_to_event, -1))
        self._add_shortcut("M", self._on_toggle_measure_mode)

        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self.bev.toggleViewAction())
        view_menu.addAction(self.layers_panel.toggleViewAction())
        view_menu.addAction(self.inspector_panel.toggleViewAction())
        view_menu.addAction(self.timeline_strip.toggleViewAction())

        timeline_menu = self.menuBar().addMenu("&Timeline")
        timeline_menu.addAction("Add signal lane...").triggered.connect(
            functools.partial(self._on_add_timeline_lane, is_state=False))
        timeline_menu.addAction("Add state lane...").triggered.connect(
            functools.partial(self._on_add_timeline_lane, is_state=True))
        timeline_menu.addAction("Add bookmark at cursor").triggered.connect(self._on_add_bookmark)

        plots_menu = self.menuBar().addMenu("&Plots")
        for kind in ("timeseries", "xy", "state", "distribution"):
            plots_menu.addAction(f"Add {kind} plot...").triggered.connect(
                functools.partial(self._on_add_plot, kind))

        measure_menu = self.menuBar().addMenu("&Measure")
        self._measure_mode_action = measure_menu.addAction("Ruler Mode (drag to measure)")
        self._measure_mode_action.setCheckable(True)
        self._measure_mode_action.toggled.connect(self._on_set_measure_mode)
        measure_menu.addAction("Set Range Ring Radii...").triggered.connect(self._on_set_range_ring_radii)
        self._range_rings_action = measure_menu.addAction("Show Range Rings")
        self._range_rings_action.setCheckable(True)
        self._range_rings_action.toggled.connect(self._on_toggle_range_rings)

        view_menu.addSeparator()
        view_menu.addAction("Reset Layout").triggered.connect(self._on_reset_layout)

        # `UT-B3-12`'s "shipped default": captured once, right here, before
        # any user-saved state is overlaid -- "Reset Layout" restores
        # exactly this, byte for byte, never a re-derivation that could drift.
        self._default_layout_state = bytes(self.saveState())
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
        self._expectation_windows = _index_expectation_windows(self._scenario, session)
        # head_tick pinned to the last tick: the whole recording is already
        # loaded (pass 1 already ran), so there is nothing left to "execute"
        # -- `_advance_for_transport` exists only to satisfy Transport's
        # contract and is provably never called (see its own docstring).
        # `Transport.__init__` starts `cursor` at `head_tick` (right, for a
        # live SUT: "head" is "where execution is now") -- explicitly
        # `goto(0)` so a freshly opened recording starts at its beginning,
        # matching `render_tick(0)` below, not its end.
        self.transport = Transport(session, self._advance_for_transport, head_tick=len(session) - 1)
        start_tick = session.seek_ns(int(self._initial_at_s * 1e9)) if self._initial_at_s is not None else 0
        self.transport.goto(start_tick)
        self.transport_bar.bind(self.transport)
        self._signal_series_cache.clear()  # stale values from a previous session, if any
        self.timeline_strip._head_tick = self.transport.head_tick
        self._apply_workspace_timeline_signals()
        self.statusBar().showMessage(f"loaded {session.name} -- {len(session)} ticks", 5000)
        self.render_tick(start_tick)
        if self._initial_preset is not None and self._initial_preset in DEFAULT_PRESETS:
            # A command-line --preset is a more specific request than the
            # workspace's own tabs[0] viewpoint (already applied in
            # __init__), so it wins -- applied last, after the first real
            # render established `_current_tick`, and re-renders once more.
            self._on_jump_to_preset(self._initial_preset)

    def _advance_for_transport(self, n: int, on_progress: Callable[[int, int], None], cancel: object) -> int:
        """`Transport`'s stand-in for a real SUT's `exec()` loop
        (`view/transport.py`'s own docstring) -- unreachable here: `goto`/
        `step_forward` only call it for a target beyond `head_tick`, and
        `head_tick` is pinned to `len(session) - 1` in `_on_loaded`, so no
        target can ever exceed it. Kept only because `Transport.__init__`
        requires a callable."""
        del on_progress, cancel
        return min((self.transport.head_tick if self.transport else 0) + n, len(self._session) - 1)

    def _on_transport_changed(self) -> None:
        """`TransportBar.changed` -- a step, a slider drag, or play/pause
        toggling. `TransportBar` already re-synced its own widgets before
        emitting; this only has to render the new cursor and keep the
        playback timer's interval matching the tick it is now sitting on."""
        if self.transport is None:
            return
        self.render_tick(self.transport.cursor)
        self._sync_playback_timer()

    def _sync_playback_timer(self) -> None:
        """Restarted on every tick (not just on play/pause) because ticks
        need not be equally spaced -- the next interval is always this
        tick's own `dt_ns`, divided by the current speed."""
        if self.transport is None or self._session is None:
            self._playback_timer.stop()
            return
        if not self.transport.playing:
            self._playback_timer.stop()
            return
        if self.transport.cursor >= self.transport.head_tick:
            self.transport.pause()  # reached the end -- auto-pause, not a dead "still playing" state
            self.transport_bar.sync()
            self._playback_timer.stop()
            return
        dt_ns = self._session.at(self.transport.cursor).dt_ns or 50_000_000
        interval_ms = max(1, round((dt_ns / 1e6) / max(self.transport.speed, 0.01)))
        self._playback_timer.start(interval_ms)

    def _on_playback_tick(self) -> None:
        if self.transport is None:
            return
        marks = self.transport.loop_marks
        if marks is not None and self.transport_bar.loop_active and self.transport.cursor >= marks[1]:
            self.transport.goto(marks[0])
        else:
            self.transport.step_forward(1)
        self.transport_bar.sync()
        self.render_tick(self.transport.cursor)
        self._sync_playback_timer()

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
        defaults to a no-op, for a caller feeding a provider's declared
        `reacts_to` (Slice 4); its `selection` field is always overridden
        from `self._selection` here, so every call site -- not just the
        click handler -- keeps rendering the current selection without
        having to remember to thread it through by hand. `measure_state.
        overlay_prims()` (§8, ruler/range-rings/annotations) draws last,
        on top -- the cursor readout is deliberately **not** here (a plain
        `QLabel`, `_on_bev_hovered`, updated with no re-render at all)."""
        if self._session is None or self._scene_cache is None:
            return
        self._current_tick = tick_index
        effective_interaction = dataclasses.replace(interaction, selection=self._selection)
        scene = self._scene_cache.get(tick_index, frozenset(), self.bev.theme, effective_interaction)
        self._current_scene = scene  # unfiltered -- hit_test takes layer_selection itself
        self.layers_panel.sync_from_scene(scene.layers)
        layer_selection = self.layers_state.visible_layer_ids()
        hud_lines, stale_banner = self._hud_and_stale_banner(tick_index)
        frame = render_scene(
            scene, self.bev.viewport, self.bev.theme, layer_selection, self._selection,
            self.measure_state.overlay_prims(), hud_lines, stale_banner,
        )
        self.bev.show_frame(frame)
        # The inspector reflects what's actually drawn, same as hit_test --
        # a hidden layer's entity is gone from the panel too, not just the
        # canvas (a filtered *view* of the Scene, not a second Scene).
        visible_scene = dataclasses.replace(
            scene, layers=tuple(layer for layer in scene.layers if layer.id in layer_selection),
        )
        self.inspector_panel.sync(visible_scene, self._selection)
        self._rerender_timeline()
        self._rerender_plots()

    def _hud_and_stale_banner(self, tick_index: int) -> tuple[tuple[str, ...], str | None]:
        """§10: everything the framework itself knows (scale, time, tick,
        project/scenario/pipeline/build id) plus, only if configured
        (`_ego_state_signals`/`_max_age_s`, `__init__`'s own docstring),
        the ego state line and the stale-port banner."""
        tick = self._session.at(tick_index)
        ego_state = None
        if self._ego_state_signals:
            ego_state = {}
            for field_name, address in self._ego_state_signals.items():
                value = resolve_tick(tick, address)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    ego_state[field_name] = value
        build_id = self._session.meta.components[0].build_id if self._session.meta.components else ""
        info = HudInfo(
            scale_px_per_m=self.bev.viewport.scale_px_per_m, t_s=tick.t_s,
            tick_index=tick_index, head_tick=self.transport.head_tick if self.transport else tick_index,
            project=self._project, scenario=self._session.meta.scenario,
            pipeline=self._session.meta.pipeline, build_id=build_id, ego_state=ego_state,
        )
        banner = format_stale_banner(stale_ports(tick, self._max_age_s))
        return format_hud_lines(info), banner

    def _rerender_timeline(self) -> None:
        """Redraws the strip at the current playhead -- cheap: every
        lane's series is already resolved and cached (`_on_add_timeline_lane`),
        so this is rasterising, not re-resolving (§7.3's "synced strip")."""
        if self.transport is None:
            return
        signal_data = {addr: self._signal_series_cache[addr] for addr in self.timeline_state.signal_lanes()
                       if addr in self._signal_series_cache}
        state_data = {addr: self._signal_series_cache[addr] for addr in self.timeline_state.state_lanes()
                      if addr in self._signal_series_cache}
        markers = {addr: event_markers(series) for addr, series in state_data.items()}
        bookmark_ticks = tuple(b.tick_index for b in self.timeline_state.bookmarks())
        # seconds -> ticks is `render/timeline.py`'s one thing it cannot do
        # itself (it draws pixels, not a `Session`, `R-SIM-13`) -- done here,
        # the one place both `self._expectation_windows` (seconds,
        # `check.expect.ExpectationResult.window_s`) and `self._session`
        # (`seek_ns`) are both in scope.
        expectation_windows = {
            addr: tuple(
                (self._session.seek_ns(int(r.window_s[0] * 1e9)), self._session.seek_ns(int(r.window_s[1] * 1e9)), r.passed)
                for r in self._expectation_windows[addr]
            )
            for addr in (*signal_data, *state_data) if addr in self._expectation_windows
        }
        self.timeline_strip._head_tick = self.transport.head_tick
        frame = render_timeline(
            signal_series=signal_data, state_series=state_data, markers=markers,
            bookmark_ticks=bookmark_ticks, current_tick=self.transport.cursor,
            head_tick=self.transport.head_tick, size_px=self.timeline_strip.size_px,
            expectation_windows=expectation_windows,
        )
        self.timeline_strip.show_frame(frame)

    def _on_timeline_seek(self, tick_index: int) -> None:
        if self.transport is None:
            return
        self.transport.goto(tick_index)
        self.transport_bar.sync()
        self.render_tick(tick_index)

    def _on_add_timeline_lane(self, *, is_state: bool) -> None:
        if self._session is None:
            return
        address, ok = QtWidgets.QInputDialog.getText(
            self, "Add state lane" if is_state else "Add signal lane",
            "Signal address (NR-SIM-8: <component>.<port>.<field> / source.* / truth.* / derived.*):",
        )
        if not ok or not address:
            return
        self._signal_series_cache[address] = self._session.signal(address, project=self._project)
        self.timeline_state.add_state_lane(address) if is_state else self.timeline_state.add_signal_lane(address)
        self._rerender_timeline()

    def _on_add_bookmark(self) -> None:
        if self.transport is None:
            return
        self.timeline_state.add_bookmark(self.transport.cursor)
        self._rerender_timeline()

    def _on_jump_to_event(self, direction: int) -> None:
        if self.transport is None:
            return
        all_markers = [
            marker
            for addr in self.timeline_state.state_lanes()
            for marker in event_markers(self._signal_series_cache.get(addr, ()))
        ]
        target = self.timeline_state.jump_to_event(self.transport.cursor, direction, all_markers)
        if target is not None:
            self._on_timeline_seek(target)

    def _ensure_signal_cached(self, address: str) -> None:
        if self._session is not None and address not in self._signal_series_cache:
            self._signal_series_cache[address] = self._session.signal(address, project=self._project)

    def _on_add_plot(self, kind: str) -> None:
        """A user opens **several** plot panels (`§7.4`), unlike the one
        fixed timeline strip -- one dialog collects a comma-separated
        address list, its meaning depending on `kind`
        (`view/plots.PlotState`'s own kind-gating: lanes for `timeseries`/
        `state`, exactly x[,y[,color]] for `xy`, one address for
        `distribution`)."""
        if self._session is None:
            return
        prompts = {
            "timeseries": "Comma-separated signal addresses (one lane each):",
            "state": "Comma-separated state addresses (one lane each):",
            "xy": "x_address,y_address[,color_address]:",
            "distribution": "One signal address:",
        }
        text, ok = QtWidgets.QInputDialog.getText(self, f"Add {kind} plot", prompts[kind])
        if not ok:
            return
        addresses = [a.strip() for a in text.split(",") if a.strip()]
        if not addresses or (kind == "xy" and len(addresses) < 2):
            return
        state = PlotState(kind)
        if kind in ("timeseries", "state"):
            for address in addresses:
                self._ensure_signal_cached(address)
                state.add_lane(address)
        elif kind == "xy":
            for address in addresses[:3]:
                self._ensure_signal_cached(address)
            state.set_xy(addresses[0], addresses[1], addresses[2] if len(addresses) > 2 else None)
        else:  # distribution
            self._ensure_signal_cached(addresses[0])
            state.set_distribution(addresses[0])

        panel = PlotPanel(state, len(self.plot_panels) + 1, self)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, panel)
        panel.seek_requested.connect(self._on_timeline_seek)
        self.plot_panels.append(panel)
        self._rerender_plot(panel)

    def _rerender_plot(self, panel: PlotPanel) -> None:
        if self.transport is None:
            return
        panel._head_tick = self.transport.head_tick
        state = panel.state
        if state.kind in ("timeseries", "state"):
            signal_data: dict[str, tuple] = {}
            state_data: dict[str, tuple] = {}
            target = signal_data if state.kind == "timeseries" else state_data
            for address in state.lanes():
                target[address] = self._signal_series_cache.get(address, ())
            markers = {addr: event_markers(series) for addr, series in state_data.items()}
            frame = render_timeline(
                signal_series=signal_data, state_series=state_data, markers=markers,
                bookmark_ticks=(), current_tick=self.transport.cursor,
                head_tick=self.transport.head_tick, size_px=panel.size_px,
            )
        elif state.kind == "xy":
            x_series = _numeric_series(self._signal_series_cache.get(state.x, ()))
            y_series = _numeric_series(self._signal_series_cache.get(state.y, ()))
            color_series = _numeric_series(self._signal_series_cache[state.color]) if state.color else None
            frame = render_xy(x_series, y_series, color_series, self.transport.cursor, panel.size_px)
        else:  # distribution
            series = self._signal_series_cache.get(state.address, ())
            values = tuple(v for _, v in _numeric_series(series))
            current = dict(_numeric_series(series)).get(self.transport.cursor)
            frame = render_distribution(values, current, panel.size_px)
        panel.show_frame(frame)

    def _rerender_plots(self) -> None:
        for panel in self.plot_panels:
            self._rerender_plot(panel)

    def _on_bev_clicked(self, x: float, y: float, modifiers: QtCore.Qt.KeyboardModifiers) -> None:
        """§7.1: click to select, `Ctrl`+click to toggle membership.
        `Shift`+click drops a persistent annotation instead (§8) -- snapped
        the same way the ruler is, so an annotation on an entity tracks its
        anchor exactly, not a pixel near it. Hit-tests against exactly
        what's currently drawn (`render/bev.hit_test`, the same layer
        selection `render_tick` just rasterised with) -- a hit on a hidden
        layer's prim cannot select it."""
        if self._current_scene is None:
            return
        layer_selection = self.layers_state.visible_layer_ids()
        if modifiers & QtCore.Qt.KeyboardModifier.ShiftModifier:
            self._on_add_annotation(x, y)
            return
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

    def _add_shortcut(self, key: str, slot: Callable[[], None]) -> None:
        shortcut = QtGui.QShortcut(QtGui.QKeySequence(key), self)
        shortcut.activated.connect(slot)
        self._shortcuts.append(shortcut)

    def _on_bev_dragged(self, from_x: float, from_y: float, to_x: float, to_y: float) -> None:
        """§4.4: drag to pan -- **unless** `_measure_mode` is on (§8), in
        which case dragging measures instead (`_on_bev_drag_extent_changed`
        does that; this handler just steps aside so the same gesture is
        never both at once)."""
        if self._measure_mode:
            return
        self.bev.viewport = self.bev.viewport.panned((from_x, from_y), (to_x, to_y))
        self.render_tick(self._current_tick)

    def _on_bev_drag_extent_changed(self, press_x: float, press_y: float, to_x: float, to_y: float) -> None:
        """§8's ruler: only active in `_measure_mode`, using the drag's
        real start (not the incremental step `_on_bev_dragged` gets) so the
        measurement is press-to-here, not step-to-step. Both ends snap to
        the nearest prim anchor within threshold (`view/measure.snap_point`)
        when one is close enough."""
        if not self._measure_mode:
            return
        start_m = self.bev.viewport.to_m(press_x, press_y)
        end_m = self.bev.viewport.to_m(to_x, to_y)
        if self._current_scene is not None:
            anchors = anchor_points_m(self._current_scene, self.layers_state.visible_layer_ids())
            start_m = snap_point(start_m, anchors, self.bev.viewport)
            end_m = snap_point(end_m, anchors, self.bev.viewport)
        self.measure_state.set_ruler(start_m, end_m)
        self.render_tick(self._current_tick)

    def _on_bev_zoomed(self, factor: float, cursor_x: float, cursor_y: float) -> None:
        """§4.4: wheel to zoom **about the cursor**, not the centre --
        `Viewport.zoomed_about_cursor` already carries that invariant."""
        self.bev.viewport = self.bev.viewport.zoomed_about_cursor(factor, (cursor_x, cursor_y))
        self.render_tick(self._current_tick)

    def _on_bev_hovered(self, x: float, y: float) -> None:
        """§8's cursor readout -- a lightweight status-bar `QLabel`, never
        a re-render (`view/measure.py`'s own docstring: a full `render_scene`
        per mouse-move pixel would make the BEV laggy under normal use)."""
        point_m = self.bev.viewport.to_m(x, y)
        self._cursor_readout_label.setText(f"({point_m[0]:.2f}, {point_m[1]:.2f}) m [ego]")

    def _on_toggle_measure_mode(self) -> None:
        self._measure_mode_action.setChecked(not self._measure_mode_action.isChecked())

    def _on_set_measure_mode(self, checked: bool) -> None:
        self._measure_mode = checked
        if not checked:
            self.measure_state.clear_ruler()
            self.render_tick(self._current_tick)

    def _on_set_range_ring_radii(self) -> None:
        text, ok = QtWidgets.QInputDialog.getText(
            self, "Set Range Ring Radii", "Comma-separated radii in metres (from the rear-axle origin):",
        )
        if not ok:
            return
        try:
            radii = tuple(float(r.strip()) for r in text.split(",") if r.strip())
        except ValueError:
            return
        self.measure_state.set_range_ring_radii(radii)
        self.render_tick(self._current_tick)

    def _on_toggle_range_rings(self, checked: bool) -> None:
        del checked  # state read via measure_state.range_rings_visible; the action just mirrors it
        self.measure_state.toggle_range_rings()
        self.render_tick(self._current_tick)

    def _on_add_annotation(self, x: float, y: float) -> None:
        if self._current_scene is None:
            return
        point_m = self.bev.viewport.to_m(x, y)
        anchors = anchor_points_m(self._current_scene, self.layers_state.visible_layer_ids())
        point_m = snap_point(point_m, anchors, self.bev.viewport)
        label, ok = QtWidgets.QInputDialog.getText(self, "Add Annotation", "Label (optional):")
        if not ok:
            return
        self.measure_state.add_annotation(point_m, label)
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
        (`DEFAULT_PRESETS`), positionally assigned in sorted order --
        `DEFAULT_PRESETS`'s own docstring names these "the fallback every
        component starts from". A component's own named presets
        (`modules/<name>/sim/viewpoints.yaml`, §4.3) are not loaded by
        `view/workspace.py` either (Slice 9's own documented gap, see
        `Workspace`'s docstring) -- `_apply_workspace_viewpoint` below can
        only resolve a `viewpoint:` name that happens to also be one of
        these."""
        preset = DEFAULT_PRESETS[preset_name]
        self.bev.viewport = dataclasses.replace(preset, size_px=self.bev.viewport.size_px)
        self.render_tick(self._current_tick)

    def _apply_workspace_viewpoint(self) -> None:
        """`self.workspace.tabs[0]`'s `bev` view, if it names a `viewpoint`
        `DEFAULT_PRESETS` actually has (see `_on_jump_to_preset`'s own
        note on what is and is not resolvable yet). No matching tab, view
        or preset is silently fine -- the BEV already has a working default
        viewport from its own constructor."""
        if not self.workspace.tabs:
            return
        for view in self.workspace.tabs[0].views:
            if view.panel == "bev" and view.viewpoint in DEFAULT_PRESETS:
                preset = DEFAULT_PRESETS[view.viewpoint]
                self.bev.viewport = dataclasses.replace(preset, size_px=self.bev.viewport.size_px)
                return

    def _apply_workspace_timeline_signals(self) -> None:
        """`self.workspace.tabs[0]`'s `timeline` view's `signals`, added as
        signal lanes once a session exists to resolve them against.
        **Uniformly signal lanes, never state lanes** -- `workspace.yaml`'s
        schema (§13b's own example mixes a warning and `derived.ttc` under
        one flat `signals:` list) does not declare which is which, and
        guessing from the resolved value's Python type would silently
        misclassify a protobuf enum (decodes as `int`) as numeric. A state
        lane is one menu action away (`Timeline > Add state lane...`)."""
        if self._session is None or not self.workspace.tabs:
            return
        for view in self.workspace.tabs[0].views:
            if view.panel != "timeline":
                continue
            for address in view.signals:
                if address not in self._signal_series_cache:
                    self._signal_series_cache[address] = self._session.signal(address, project=self._project)
                self.timeline_state.add_signal_lane(address)

    def _on_reset_layout(self) -> None:
        """`UT-B3-12`: returns exactly to the bytes captured in `__init__`
        before any user-saved state was overlaid -- not a re-derivation,
        which could drift from what was actually shipped."""
        self.restoreState(QtCore.QByteArray(self._default_layout_state))
