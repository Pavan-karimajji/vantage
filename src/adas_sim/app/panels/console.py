# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`ConsolePanel` -- the Python console dock (`S-D8`, `sim_player.md` §4:
"`adas_sim` already loaded, `session`, `pipeline` and `scene` bound. This
is `R-SIM-16`'s 'library first' made reachable without leaving the window,
and it is the pressure valve that stops someone forking the tool for one
experiment").

**Bench-only** (`app/shell/workspace.py`'s `allow_console`): `app/shell/
window.py` is the one place that decides whether this dock even exists in
the current workspace -- this widget itself carries no workspace concept
(`UT-D8-9`).

Built on `code.InteractiveInterpreter` (stdlib, no `qtconsole`/`IPython`
dependency this project does not otherwise carry) -- one statement per
`Enter`, output captured from both `stdout` and `stderr` into the
transcript. Deliberately not a full multi-line-aware REPL: the pressure
valve this exists to be is "check one thing without leaving the window,"
not a second IDE."""

from __future__ import annotations

import code
import contextlib
import io
from collections.abc import Mapping

from PySide6 import QtWidgets


class ConsolePanel(QtWidgets.QWidget):
    """`namespace` is the caller's own dict, kept live: `update_namespace`
    mutates it in place, so a value the interpreter's own code later reads
    (`session`, reassigned after a new recording opens) is always current,
    not a stale copy taken at construction."""

    def __init__(self, namespace: Mapping[str, object] | None = None, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ConsolePanel")
        self._namespace: dict[str, object] = dict(namespace or {})
        self._interpreter = code.InteractiveInterpreter(self._namespace)

        layout = QtWidgets.QVBoxLayout(self)
        self._transcript = QtWidgets.QPlainTextEdit()
        self._transcript.setReadOnly(True)
        self._transcript.setObjectName("consoleTranscript")
        layout.addWidget(self._transcript)

        self._input = QtWidgets.QLineEdit()
        self._input.setObjectName("consoleInput")
        self._input.setPlaceholderText(">>> ")
        self._input.returnPressed.connect(self._on_return)
        layout.addWidget(self._input)

        self._write_banner()

    def _write_banner(self) -> None:
        bound = ", ".join(sorted(self._namespace)) or "(nothing yet)"
        self._append(f"Python console -- bound: {bound}")

    def _append(self, text: str) -> None:
        self._transcript.appendPlainText(text)

    def update_namespace(self, **values: object) -> None:
        """`app/shell/window.py` calls this whenever `session`/`pipeline`/
        `scene` change (a new recording opens, a run completes) -- never a
        new `ConsolePanel`, so the transcript survives across them."""
        self._namespace.update(values)

    @property
    def namespace(self) -> Mapping[str, object]:
        return self._namespace

    def _on_return(self) -> None:
        source = self._input.text()
        self._input.clear()
        if not source.strip():
            return
        self._append(f">>> {source}")
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            try:
                self._interpreter.runsource(source)
            except Exception as exc:  # noqa: BLE001 -- a console must never crash the window over a bad statement
                output.write(f"{type(exc).__name__}: {exc}\n")
        text = output.getvalue()
        if text:
            self._append(text.rstrip("\n"))
