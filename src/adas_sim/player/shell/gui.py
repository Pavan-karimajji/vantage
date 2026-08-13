# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Launches Vantage (`sim view`) -- orchestration only (`GT-9`): construct
`QApplication`, construct `VantageWindow` (`S-D8`'s own shell -- the
workspace toggle, start page and Campaign, hosting `render/viewer.py`'s
`MainWindow` as Bench's content), run the event loop. `cli/view.py`/
`scripts/vantage.py` stay argument-parsing-only (`app/` is the GUI, `cli/`
only ever calls into it, `sim_api_reference.md` §10's own framing).

`recording=None` (`sim view` with no positional argument, or `vantage`
with none) opens onto the start page instead of raising -- `cli/view.py`'s
own parser still requires one today (`session` has no default), so this
path is reachable from `scripts/vantage.py`'s own optional `recording`
argument already, and from any future caller that wants Screen 1 first."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PySide6 import QtWidgets

from adas_sim.player.shell.shell.window import VantageWindow
from adas_sim.player.shell.qt_window import set_high_dpi_policy


def launch(
    recording: Path | None = None, *, project: str = "base",
    workspace_path: Path | None = None,
    preset: str | None = None,
    at_s: float | None = None,
    scenario_path: Path | None = None,
    pipeline_path: Path | None = None,
    pipeline_search: Sequence[Path] = (),
    pipeline_config: Path | None = None,
    config_library_dir: Path | None = None,
) -> int:
    set_high_dpi_policy()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = VantageWindow(
        recording, project=project, workspace_path=workspace_path,
        preset=preset, at_s=at_s, scenario_path=scenario_path,
        pipeline_path=pipeline_path, pipeline_search=pipeline_search, pipeline_config=pipeline_config,
        config_library_dir=config_library_dir,
    )
    window.show()
    return app.exec()
