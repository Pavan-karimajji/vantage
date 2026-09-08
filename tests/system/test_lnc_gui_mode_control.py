# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`WP-35` -- the launcher's measured/simulated control (`SW-0429`,
`IMP-0433`, `UT-VTG-03`).

The demo's own gesture, at the level this file can assert: choosing a stage
and a mode in `scripts/gui.py` must produce a **real run config written by
`adas_sim.launcher`** and point the Vantage command at it -- never mutate
the authored `pipeline.yaml`, and never let a mode that did not take effect
look like one that did.

The picture itself is not asserted here and cannot be: `vantage_app.exe` has
no snapshot flag, so *"the two pictures agree"* is watched and screenshotted
(the Test Execution Record), while the port values behind it are already
asserted byte-identical elsewhere. What IS mechanised here is everything up
to the window: the selection, the refusal, and the file that runs.

Tkinter is stdlib but needs a display; the whole module skips without one,
the same way the Qt suites skip without PySide6.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SIM_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(SIM_DIR / "scripts"))

tk = pytest.importorskip("tkinter")


@pytest.fixture()
def app(tmp_path, monkeypatch):
    """A real `LauncherApp` on a withdrawn root -- no visible window, but the
    genuine widget tree and the genuine `_refresh` path."""
    import gui

    # Never touch the developer's own gui_config.json (P-7's discipline).
    monkeypatch.setattr(gui, "CONFIG_PATH", tmp_path / "gui_config.json")
    monkeypatch.setattr(gui, "DERIVED_DIR", tmp_path / "derived")
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # no display
        pytest.skip(f"no Tk display: {exc}")
    root.withdraw()
    application = gui.LauncherApp(root)
    yield application
    root.destroy()


DF = SIM_DIR.parent / "df"
PIPELINE = DF / "sim" / "pipelines" / "df_only.yaml"
SEARCH = DF / "build-sil-vs2026" / "src" / "platform" / "df_sil" / "Release"
CONFIG = DF / "src" / "project" / "base" / "default.yaml"
SELF_PRODUCED = SIM_DIR / "logs" / "_step0" / "v_self.mcap"
STIMULUS_ONLY = DF / "tests" / "carla_testruns" / "aeb" / "aeb_closing_ego20mps_lead10mps_30m.mcap"


def _require(*paths: Path) -> None:
    for path in paths:
        if not path.exists():
            pytest.skip(f"not built / not present on this platform: {path}")


def test_no_mode_chosen_passes_the_authored_pipeline_through_untouched(app):
    """The control is inert until used: this screen behaved this way before
    it existed, and must still."""
    _require(PIPELINE, SEARCH)
    app.pipeline.set(str(PIPELINE))
    app.search.set(str(SEARCH))
    app._refresh()

    argv = app.build_argv()
    assert "--pipeline" in argv
    assert argv[argv.index("--pipeline") + 1] == str(PIPELINE)
    assert app._derived_path is None
    # It still reports what the file itself says, so the authored modes are
    # visible without having to open the YAML.
    assert "df=" in app.mode_status.cget("text")


def test_choosing_measured_writes_a_run_config_and_points_the_command_at_it(app):
    _require(PIPELINE, SEARCH, CONFIG, SELF_PRODUCED)
    authored_before = PIPELINE.read_bytes()
    app.pipeline.set(str(PIPELINE))
    app.search.set(str(SEARCH))
    app.config_path.set(str(CONFIG))
    app.recording.set(str(SELF_PRODUCED))
    app.stage.set("df")
    app.mode.set("measured")
    app._refresh()

    derived = app._derived_path
    assert derived is not None, app.mode_status.cget("text")
    assert derived.exists()
    # The authored file is never edited -- the derived one is a build output.
    assert derived != PIPELINE
    assert PIPELINE.read_bytes() == authored_before, "the authored pipeline was modified in place"

    argv = app.build_argv()
    assert argv[argv.index("--pipeline") + 1] == str(derived)

    # And what was written is a real pipeline the headless path can reload,
    # with the one field changed -- `CN-0175`, checked rather than asserted.
    from adas_sim.graph.pipeline import Pipeline

    reloaded = Pipeline.load(derived, search=[SEARCH])
    assert {s.name: s.mode for s in reloaded.stages}["df"] == "measured"


def test_flipping_to_simulate_rewrites_it_and_both_files_survive(app):
    """The demo flips back and forth; each direction must land its own file,
    so the two runs are separately re-runnable afterwards."""
    _require(PIPELINE, SEARCH, CONFIG, SELF_PRODUCED)
    app.pipeline.set(str(PIPELINE))
    app.search.set(str(SEARCH))
    app.config_path.set(str(CONFIG))
    app.recording.set(str(SELF_PRODUCED))
    app.stage.set("df")

    app.mode.set("measured")
    app._refresh()
    measured = app._derived_path
    app.mode.set("simulate")
    app._refresh()
    simulated = app._derived_path

    assert measured is not None and simulated is not None
    assert measured != simulated, "both directions wrote the same file"
    assert measured.exists() and simulated.exists()

    from adas_sim.graph.pipeline import Pipeline

    assert {s.name: s.mode for s in Pipeline.load(measured, search=[SEARCH]).stages}["df"] == "measured"
    assert {s.name: s.mode for s in Pipeline.load(simulated, search=[SEARCH]).stages}["df"] == "simulate"


def test_measured_against_a_recording_that_cannot_drive_it_is_refused_by_name(app):
    """The planted violation (`R-REQ-9`): the cases above must be able to
    fail. A stimulus-only recording carries none of df's outputs, so the
    measured cut is impossible -- and `R-SIM-23` says that is answered
    BEFORE the run, naming the ports, not discovered by failing one."""
    _require(PIPELINE, SEARCH, CONFIG, STIMULUS_ONLY)
    app.pipeline.set(str(PIPELINE))
    app.search.set(str(SEARCH))
    app.config_path.set(str(CONFIG))
    app.recording.set(str(STIMULUS_ONLY))
    app.stage.set("df")
    app.mode.set("measured")
    app._refresh()

    assert app._derived_path is None, "a run config was written for an impossible cut"
    note = app.mode_status.cget("text")
    assert "cannot drive" in note
    assert "aeb.outputs" in note or "bsd.outputs" in note, note
    # Refused, and the command must not silently fall back to the authored
    # pipeline as though the mode had been applied.
    assert app.build_argv()[app.build_argv().index("--pipeline") + 1] == str(PIPELINE)


def test_an_unknown_stage_name_is_reported_not_raised(app):
    _require(PIPELINE, SEARCH)
    app.pipeline.set(str(PIPELINE))
    app.search.set(str(SEARCH))
    app.stage.set("no_such_stage")
    app.mode.set("simulate")
    app._refresh()

    assert app._derived_path is None
    assert "no_such_stage" in app.mode_status.cget("text")
