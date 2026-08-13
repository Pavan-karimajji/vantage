# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 threading tests: UT-B3-15, UT-B3-16 (docs/sim_implementation_plan.md).
`_SessionLoadWorker` (render/viewer.py) is exercised on a real `QThread`,
offscreen -- P-7's own discipline for testing Qt with no display."""

from __future__ import annotations

import os
import threading
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
from PySide6 import QtCore  # noqa: E402

from adas_sim.player.shell.qt_window import _SessionLoadWorker, set_high_dpi_policy  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
TINY_MCAP = FIXTURES_DIR / "tiny.mcap"


@pytest.fixture(scope="module")
def qapp():
    set_high_dpi_policy()
    return QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])


def test_pass1_runs_on_a_worker_thread(qapp):
    """UT-B3-15: asserted on thread identity, not elapsed time -- every
    progress callback fires on a thread other than the one this test runs on."""
    main_ident = threading.get_ident()
    seen_idents: list[int] = []
    result: dict[str, object] = {}

    worker = _SessionLoadWorker(TINY_MCAP)
    thread = QtCore.QThread()
    worker.moveToThread(thread)

    worker.progress.connect(lambda done, total: seen_idents.append(threading.get_ident()))

    def _on_loaded(session):
        result["session"] = session
        thread.quit()

    worker.loaded.connect(_on_loaded)
    thread.started.connect(worker.run)

    loop = QtCore.QEventLoop()
    thread.finished.connect(loop.quit)
    thread.start()
    loop.exec()
    thread.wait()

    assert result.get("session") is not None
    assert len(result["session"]) == 20
    assert seen_idents, "no progress reported"
    assert all(ident != main_ident for ident in seen_idents), "pass 1 ran on the GUI thread"


def test_cancelling_mid_load_leaves_no_session_reachable(qapp):
    """UT-B3-16: a half-built session rendered as if complete is a silent
    wrong picture, so cancelling must leave nothing reachable at all."""
    worker = _SessionLoadWorker(TINY_MCAP)
    thread = QtCore.QThread()
    worker.moveToThread(thread)
    result = {"loaded": False, "cancelled": False}

    def _cancel_partway(done, _total):
        if done >= 5:
            worker.request_cancel()

    def _on_loaded(session):
        result["loaded"] = True
        thread.quit()

    def _on_cancelled():
        result["cancelled"] = True
        thread.quit()

    worker.progress.connect(_cancel_partway)
    worker.loaded.connect(_on_loaded)
    worker.cancelled.connect(_on_cancelled)
    thread.started.connect(worker.run)

    loop = QtCore.QEventLoop()
    thread.finished.connect(loop.quit)
    thread.start()
    loop.exec()
    thread.wait()

    assert result["cancelled"] is True
    assert result["loaded"] is False
