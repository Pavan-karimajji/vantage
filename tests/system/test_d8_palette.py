# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`S-D8` `CommandPalette` tests (`docs/sim_implementation_plan.md`,
`sim_player.md` §3): every `QAction` on a window becomes searchable with
no duplication, filtering is type-to-filter, and activating an entry
triggers its action and nothing else."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402

from adas_sim.player.shell.shell.palette import CommandPalette, PaletteAction, actions_from_window, install_shortcut  # noqa: E402


def _app() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _window_with_actions() -> QtWidgets.QMainWindow:
    window = QtWidgets.QMainWindow()
    menu = window.menuBar().addMenu("&File")
    menu.addAction("&Open Recording…")
    menu.addSeparator()
    menu.addAction("Save &Run Manifest…")
    dock = QtWidgets.QDockWidget("Layers", window)
    window.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, dock)
    window.menuBar().addMenu("&View").addAction(dock.toggleViewAction())
    return window


def test_actions_from_window_strips_mnemonics_and_skips_separators():
    _app()
    window = _window_with_actions()
    actions = actions_from_window(window)
    texts = [a.text for a in actions]
    assert "Open Recording…" in texts
    assert "Save Run Manifest…" in texts
    assert not any(t == "" for t in texts)


def test_actions_from_window_includes_a_closed_docks_toggle_action():
    """`sim_player.md` §3: "listing every action, including those of
    closed docks"."""
    _app()
    window = _window_with_actions()
    dock = window.findChildren(QtWidgets.QDockWidget)[0]
    dock.hide()
    texts = [a.text for a in actions_from_window(window)]
    assert "Layers" in texts


def test_palette_filters_case_insensitively():
    _app()
    actions = (
        PaletteAction(text="Open Recording", trigger=lambda: None),
        PaletteAction(text="Save Run Manifest", trigger=lambda: None),
    )
    palette = CommandPalette(actions)
    palette._search.setText("open")
    assert palette._list.count() == 1
    assert palette._list.item(0).text() == "Open Recording"


def test_palette_empty_search_shows_every_action():
    _app()
    actions = (
        PaletteAction(text="Open Recording", trigger=lambda: None),
        PaletteAction(text="Save Run Manifest", trigger=lambda: None),
    )
    palette = CommandPalette(actions)
    assert palette._list.count() == 2


def test_activating_an_item_triggers_its_action_and_closes():
    _app()
    calls = []
    actions = (PaletteAction(text="Do Thing", trigger=lambda: calls.append("done")),)
    palette = CommandPalette(actions)
    palette.show()
    palette._trigger_item(palette._list.item(0))
    assert calls == ["done"]
    assert palette.result() == QtWidgets.QDialog.DialogCode.Accepted


def test_a_disabled_action_does_not_trigger():
    _app()
    calls = []
    actions = (PaletteAction(text="Cannot Do This", trigger=lambda: calls.append("done"), enabled=False),)
    palette = CommandPalette(actions)
    palette._trigger_item(palette._list.item(0))
    assert calls == []


def test_install_shortcut_binds_ctrl_k():
    _app()
    window = QtWidgets.QMainWindow()
    shortcut = install_shortcut(window)
    assert shortcut.key() == QtGui.QKeySequence("Ctrl+K")
