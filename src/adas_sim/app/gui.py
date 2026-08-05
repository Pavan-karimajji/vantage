# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Launches Vantage (`sim view`) -- orchestration only (`GT-9`): construct
`QApplication`, construct `MainWindow`, run the event loop. Every decision
`MainWindow` makes lives in `render/viewer.py`; this module exists so
`cli/view.py` stays argument-parsing-only too (`app/` is the GUI, `cli/`
only ever calls into it, `sim_api_reference.md` §10's own framing)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PySide6 import QtWidgets

from adas_sim.render.viewer import MainWindow, set_high_dpi_policy


def launch(
    recording: Path, *, project: str = "base",
    workspace_path: Path | None = None,
    preset: str | None = None,
    at_s: float | None = None,
    scenario_path: Path | None = None,
    pipeline_path: Path | None = None,
    pipeline_search: Sequence[Path] = (),
    pipeline_config: Path | None = None,
) -> int:
    set_high_dpi_policy()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MainWindow(
        recording, project=project, workspace_path=workspace_path,
        preset=preset, initial_at_s=at_s, scenario_path=scenario_path,
        pipeline_path=pipeline_path, pipeline_search=pipeline_search, pipeline_config=pipeline_config,
    )
    window.show()
    return app.exec()
