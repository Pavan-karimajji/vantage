# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`LauncherWindow` (`IMP-0149`, `D21`, `SYS-0122`..`SYS-0127`): a thin window over the launcher model, on the standard library's `tkinter` only.

It draws `view.window_state` and holds no logic: each widget command is one call of the launcher model -- `Selection` for a choice,
`write.command_text_for` for *copy command line*, `write.launch_selection` for *start* -- so the copied command line is the one that is
started (`R-SIM-16`). It reads no file, starts no process and compares no mode itself; `scripts/check_window_boundary.py` checks that.
"""
from __future__ import annotations

import tkinter
from pathlib import Path
from tkinter import filedialog, ttk

from adas_sim.launcher.model import Selection, group_control_view
from adas_sim.launcher.view import window_state
from adas_sim.launcher.write import command_text_for, launch_selection


class LauncherWindow:
    """The window over `selection`. `root` is a `tkinter.Tk` or `Toplevel` (made when none is given); `setup_path` is where the run
    setup is written; `deadline_ms` makes the start the batch face."""

    def __init__(self, selection: Selection, *, root: tkinter.Misc | None = None, setup_path: Path | None = None,
                 deadline_ms: int | None = None, engine: Path | None = None) -> None:
        self.selection = selection
        self.root = root if root is not None else tkinter.Tk()
        self.setup_path = Path(setup_path) if setup_path is not None else Path("launcher.run.json")
        self.deadline_ms = deadline_ms
        self.engine = engine
        self.exit_text = tkinter.StringVar(master=self.root, value="")
        self.frame = ttk.Frame(self.root)
        self.frame.pack(fill="both", expand=True)
        self.draw()

    # ---- every action is one call of the launcher model -------------------------------------------------------------
    def choose_mode(self, stage: str, mode: str) -> None:
        self.selection = self.selection.set_mode(stage, mode)
        self.draw()

    def choose_impl(self, stage: str, impl: str) -> None:
        self.selection = self.selection.set_impl(stage, impl)
        self.draw()

    def isolate(self, stage: str) -> None:
        self.selection = self.selection.isolate(stage)
        self.draw()

    def add_recording(self, path: Path) -> None:
        self.selection = self.selection.add_recording(Path(path))
        if self.selection.selected_recording is None:
            self.selection = self.selection.select_recording(Path(path))
        self.draw()

    def group_state(self, stages) -> str:
        return group_control_view(self.selection, stages).state

    def choose_group_mode(self, stages, mode: str) -> None:
        self.selection = self.selection.set_group_mode(stages, mode)
        self.draw()

    def copy_command_line(self) -> str:
        text = command_text_for(self.selection, self.setup_path, deadline_ms=self.deadline_ms, face=self._face(), engine=self.engine)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        return text

    def start(self) -> int:
        code = launch_selection(self.selection, self.setup_path, deadline_ms=self.deadline_ms, face=self._face(), engine=self.engine)
        self.exit_text.set(str(code))
        return code

    def _face(self) -> str:
        return "batch" if self.deadline_ms else "developer"

    # ---- drawing: the state of `view.window_state`, as widgets --------------------------------------------------------
    def draw(self) -> None:
        for child in self.frame.winfo_children():
            child.destroy()
        state = window_state(self.selection)
        for row, stage in enumerate(state.stages):
            ttk.Label(self.frame, text=stage.name).grid(row=row, column=0, sticky="w")
            box = ttk.Combobox(self.frame, values=list(stage.modes), state="readonly", width=10)
            box.set(stage.mode)
            box.bind("<<ComboboxSelected>>", lambda _e, n=stage.name, b=box: self.choose_mode(n, b.get()))
            box.grid(row=row, column=1)
            ttk.Label(self.frame, text=stage.availability.impl or "").grid(row=row, column=2, sticky="w")
            ttk.Label(self.frame, text=stage.availability.reason or "available").grid(row=row, column=3, sticky="w")
            ttk.Button(self.frame, text="isolate", command=lambda n=stage.name: self.isolate(n)).grid(row=row, column=4)
        base = len(state.stages)
        for offset, recording in enumerate(state.recordings):
            ttk.Label(self.frame, text=str(recording)).grid(row=base + offset, column=0, columnspan=4, sticky="w")
        last = base + len(state.recordings)
        ttk.Button(self.frame, text="Add recording", command=self._ask_recording).grid(row=last, column=0)
        ttk.Button(self.frame, text="Copy command line", command=self.copy_command_line).grid(row=last, column=1)
        ttk.Button(self.frame, text="Start", command=self.start).grid(row=last, column=2)
        ttk.Label(self.frame, textvariable=self.exit_text).grid(row=last, column=3)

    def _ask_recording(self) -> None:
        chosen = filedialog.askopenfilename(filetypes=[("recordings", "*.mcap")])
        if chosen:
            self.add_recording(Path(chosen))
