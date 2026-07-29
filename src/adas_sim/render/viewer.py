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

**Scope of this slice.** Only the window, the threading model and one peer
panel (BEV) exist here. Layer tree, inspector, timeline, signals, plots,
measure and workspace loading are later slices of the same stage; none of
them change this module's shape (`sim_visualization_spec.md` §11.1's own
"a new panel type registers itself... the shell does not change").
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from adas_sim.core.runner import LoadCancelled, SceneCache, build_scene, build_session_from_recording
from adas_sim.core.session import Session
from adas_sim.render.bev import render_scene
from adas_sim.render.theme import Theme
from adas_sim.view.viewport import Viewport


def set_high_dpi_policy() -> None:
    """P-7: set before the `QApplication` object exists, on both platforms."""
    QtGui.QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )


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

        self.bev = BevPanel(self)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.bev)

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

    def _stop_thread(self) -> None:
        self._thread.quit()
        self._thread.wait()

    def _on_progress(self, done: int, total: int) -> None:
        self.statusBar().showMessage(f"loading... {done}/{total}")

    def _on_loaded(self, session: Session) -> None:
        self._session = session
        self._scene_cache = SceneCache(self._build_scene_for_cache)
        self._stop_thread()
        self.statusBar().showMessage(f"loaded {session.name} -- {len(session)} ticks", 5000)
        self.render_tick(0)

    def _on_cancelled(self) -> None:
        self._stop_thread()
        self.statusBar().showMessage("load cancelled")

    def _on_failed(self, message: str) -> None:
        self._stop_thread()
        self.statusBar().showMessage(f"load failed: {message}")

    def _build_scene_for_cache(self, tick_index: int, layer_selection: frozenset[str], theme: str) -> object:
        del layer_selection, theme  # Scene assembly needs neither -- see build_scene's own docstring
        return build_scene(self._session, tick_index, project=self._project)

    def render_tick(self, tick_index: int) -> None:
        """GUI-thread only: reads `_scene_cache`, never re-runs pass 1."""
        if self._session is None or self._scene_cache is None:
            return
        scene = self._scene_cache.get(tick_index, frozenset(), self.bev.theme)
        frame = render_scene(scene, self.bev.viewport, self.bev.theme)
        self.bev.show_frame(frame)
