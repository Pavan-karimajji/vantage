# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`S-D8` `ConsolePanel` tests (`docs/sim_implementation_plan.md`,
`sim_player.md` §4): `session`/`pipeline`/`scene` are bound and reachable,
`update_namespace` keeps the SAME interpreter live across a rebind, and a
bad statement is reported in the transcript rather than crashing the
window."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
from PySide6 import QtWidgets  # noqa: E402

from adas_sim.player.shell.panels.console import ConsolePanel  # noqa: E402


def _app() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_banner_names_every_bound_value():
    _app()
    panel = ConsolePanel({"session": "the-session", "pipeline": "the-pipeline"})
    assert "session" in panel._transcript.toPlainText()
    assert "pipeline" in panel._transcript.toPlainText()


def test_banner_with_nothing_bound_says_so():
    _app()
    panel = ConsolePanel()
    assert "nothing yet" in panel._transcript.toPlainText()


def test_a_bound_value_is_reachable_by_expression():
    _app()
    panel = ConsolePanel({"session": "the-session"})
    panel._input.setText("session")
    panel._on_return()
    assert "the-session" in panel._transcript.toPlainText()


def test_arithmetic_prints_like_a_real_repl():
    _app()
    panel = ConsolePanel()
    panel._input.setText("2 + 2")
    panel._on_return()
    assert "4" in panel._transcript.toPlainText()


def test_input_line_clears_after_return():
    _app()
    panel = ConsolePanel()
    panel._input.setText("1")
    panel._on_return()
    assert panel._input.text() == ""


def test_a_raising_statement_is_reported_not_crashed():
    _app()
    panel = ConsolePanel()
    panel._input.setText("1 / 0")
    panel._on_return()  # must not raise
    assert "ZeroDivisionError" in panel._transcript.toPlainText()


def test_update_namespace_rebinds_a_value_in_place():
    _app()
    panel = ConsolePanel({"session": "old"})
    panel.update_namespace(session="new")
    panel._input.setText("session")
    panel._on_return()
    assert "new" in panel._transcript.toPlainText()
    assert panel.namespace["session"] == "new"


def test_empty_input_does_nothing():
    _app()
    panel = ConsolePanel()
    before = panel._transcript.toPlainText()
    panel._input.setText("   ")
    panel._on_return()
    assert panel._transcript.toPlainText() == before
