# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`CommandPalette` -- `Ctrl+K`, listing every action, including those of
closed docks (`S-D8`, `sim_player.md` §3: "This is what lets `L-1` hold
without hiding features. A palette is the single highest-value affordance
for L-1: it removes the pressure to surface everything").

**One search box is not "a form"** (`sim_player.md` §2's ban): that ban is
about a configuration screen presented BEFORE anything is visible
(`StartPage`'s own discipline); a palette is an on-demand, explicitly
triggered (`Ctrl+K`) power affordance over actions that already exist --
the industry-standard shape for exactly this job.

`from_window_actions` is the one real integration point: every `QAction`
already registered on a window's menus/toolbars/docks becomes searchable
with **zero duplication** -- a new menu item is automatically in the
palette the moment it exists, because this reads Qt's own action tree
rather than a second, hand-maintained action list. `L-1`'s ≤12-controls
count is therefore never inflated by the palette itself: an action already
counted once, in a menu, is not counted again here (`sim_player.md` §3's
own reasoning for why the palette is "the single highest-value affordance
for L-1")."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from PySide6 import QtCore, QtGui, QtWidgets


@dataclass(frozen=True, slots=True)
class PaletteAction:
    """One entry -- `text` is already mnemonic-stripped (`&Open` ->
    `Open`), `trigger` is a zero-argument callable, `enabled` mirrors the
    source `QAction.isEnabled()` so a currently-inapplicable action is
    shown greyed rather than hidden (the same "degrade visibly" discipline
    `sim_player.md` §2 states for everything else)."""

    text: str
    trigger: Callable[[], None]
    enabled: bool = True


def _strip_mnemonic(text: str) -> str:
    return text.replace("&", "")


def actions_from_window(window: QtWidgets.QWidget) -> tuple[PaletteAction, ...]:
    """Every `QAction` registered anywhere under `window` (menus, toolbars,
    dock `toggleViewAction()`s) -- including a CLOSED dock's own show/hide
    action, which is exactly `sim_player.md` §3's "listing every action,
    including those of closed docks" claim. A separator or an action with
    no text (Qt uses both) is not a command and is skipped."""
    seen: set[QtGui.QAction] = set()
    actions: list[PaletteAction] = []
    for action in window.findChildren(QtGui.QAction):
        if action in seen or action.isSeparator() or not action.text():
            continue
        seen.add(action)
        actions.append(PaletteAction(text=_strip_mnemonic(action.text()), trigger=action.trigger, enabled=action.isEnabled()))
    return tuple(actions)


class CommandPalette(QtWidgets.QDialog):
    """A search box plus a filtered list -- type-to-filter, `Enter`/double-
    click triggers the highlighted action, `Esc` closes with nothing run
    (Qt's own `QDialog` default). Modal over its parent window, so a
    triggered action's own effect (e.g. opening a dock) is visible the
    moment the palette closes."""

    def __init__(self, actions: Sequence[PaletteAction], parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CommandPalette")
        self.setWindowTitle("Command Palette")
        self._actions = tuple(actions)

        layout = QtWidgets.QVBoxLayout(self)
        self._search = QtWidgets.QLineEdit()
        self._search.setPlaceholderText("Type a command…")
        self._search.textChanged.connect(self._refilter)
        layout.addWidget(self._search)

        self._list = QtWidgets.QListWidget()
        self._list.itemActivated.connect(self._trigger_item)
        layout.addWidget(self._list)

        self._search.returnPressed.connect(self._trigger_first_enabled)
        self._refilter("")
        self._search.setFocus()

    def _refilter(self, text: str) -> None:
        self._list.clear()
        needle = text.casefold()
        for action in self._actions:
            if needle and needle not in action.text.casefold():
                continue
            item = QtWidgets.QListWidgetItem(action.text)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, action)
            if not action.enabled:
                item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled)
            self._list.addItem(item)
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _trigger_item(self, item: QtWidgets.QListWidgetItem) -> None:
        action: PaletteAction = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if action is None or not action.enabled:
            return
        self.accept()
        action.trigger()

    def _trigger_first_enabled(self) -> None:
        item = self._list.currentItem()
        if item is not None:
            self._trigger_item(item)

    @classmethod
    def from_window_actions(cls, window: QtWidgets.QWidget, parent: QtWidgets.QWidget | None = None) -> CommandPalette:
        return cls(actions_from_window(window), parent=parent if parent is not None else window)


def install_shortcut(window: QtWidgets.QWidget) -> QtGui.QShortcut:
    """`Ctrl+K`, bound once per window -- the one line `app/shell/window.py`
    needs to make the palette reachable at all."""
    shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+K"), window)
    shortcut.activated.connect(lambda: CommandPalette.from_window_actions(window).exec())
    return shortcut
