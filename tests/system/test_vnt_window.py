# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`SYT-WIN-01`..`03` and `ANL-08` (`VANTAGE_Test_Spec.md` sections 12 and 19): the launcher window. `F-WINDOW` is `LauncherWindow` built
on a withdrawn `tkinter` root over an `F-LAUNCH` selection, driven by calling the widgets' commands (`copy_command_line`, `start`,
`add_recording`, `isolate`, `choose_mode`, `choose_group_mode`). The tests need a display; where `tkinter` cannot open one the test ends
with a printed reason (`R-TEST-3`). On the machine of this session -- native Windows -- they run.

Where the spec leaves a step open it is chosen so the case can fail:
- *start* is run with the engine's process start replaced by a recorder (`F-SPY`) to read the command line it starts, and for real
  to compare outputs; the copied text is run in a shell with `subprocess.run(text, shell=True)`;
- the two lab recordings of `SYT-WIN-01.c2` are the case's recording and a copy of it, and the check is on the setup's `sources[]`
  and on the files the window created, not on a run of the pair;
- `ANL-08.c3`'s planted import is a third-party package name in a copy of `window.py`, read by `check_no_graphical_toolkit.py --root`.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import adas_sim.engine.bridge as bridge
from adas_sim.launcher.window import LauncherWindow
from tests.support.engine_runs import Recording, compare_recordings, engine_exe
from tests.support.lab_cases import edit_recording, lab_case
from tests.support.launch_runs import pipeline_file
from adas_sim.launcher.model import Selection

tkinter = pytest.importorskip("tkinter")


@pytest.fixture(scope="module")
def _tk():
    """One `tkinter` root for the module: a second `Tk()` in one process is not reliable on every Tcl build, and the tests need only a
    fresh frame each."""
    try:
        tk = tkinter.Tk()
    except tkinter.TclError as exc:  # no display: the reason is printed, never silent (R-TEST-3)
        print(f"no display for the launcher window tests: {exc}", file=sys.stderr)
        pytest.skip(f"no display for the launcher window tests: {exc}")
    tk.withdraw()
    yield tk
    tk.destroy()


@pytest.fixture
def root(_tk):
    yield _tk
    for child in _tk.winfo_children():
        child.destroy()


def _window(root, tmp_path, case, **kwargs):
    path, search = pipeline_file(case, tmp_path)
    return LauncherWindow(Selection.from_spec(path, search=search), root=root, setup_path=tmp_path / "w.run.json", engine=engine_exe(), **kwargs)


def test_syt_win_01_copy_command_line_is_start(root, tmp_path, monkeypatch):  # SYT-WIN-01
    """`SYT-WIN-01`, `SYS-0123` and `SYS-0126` Accept. `.c1`: the copied text equals the started command and the two real runs are equal
    outputs on every port. FAIL: a different command line, or a difference. `.c2`: one setup names both recordings in `sources[]` and
    is the only file the window created. FAIL: another file, or a recording missing."""
    case = lab_case("running_example", "cut_c")
    window = _window(root, tmp_path, case)
    copied = window.copy_command_line()
    assert root.clipboard_get() == copied, "SYT-WIN-01.c1: the clipboard does not hold the copied text"

    seen: list[list[str]] = []
    real = bridge._run_subprocess

    def record(cmd, *, timeout_s=0):
        seen.append(list(cmd))
        return real(cmd, timeout_s=timeout_s)

    monkeypatch.setattr(bridge, "_run_subprocess", record)
    outputs = {}
    out = tmp_path / "w.run.out.mcap"
    assert subprocess.run(copied, shell=True, capture_output=True, text=True, cwd=tmp_path).returncode == 0
    shutil.copyfile(out, tmp_path / "copied.mcap")
    assert window.start() == 0
    assert subprocess.list2cmdline(seen[0]) == copied, f"SYT-WIN-01.c1: start ran {seen[0]}, the copy was {copied!r}"
    shutil.copyfile(out, tmp_path / "started.mcap")
    differences = compare_recordings(Recording(tmp_path / "copied.mcap"), Recording(tmp_path / "started.mcap"))
    assert not differences, f"SYT-WIN-01.c1: the copied command and start differ on {differences[:3]}"

    second = tmp_path / "second.mcap"
    shutil.copyfile(case.recording, second)
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    window2 = _window(root, fresh, case)
    window2.add_recording(second)
    window2.copy_command_line()
    setup = json.loads((fresh / "w.run.json").read_text(encoding="utf-8"))
    assert sorted(Path(s["path"]).name for s in setup["sources"]) == sorted([case.recording.name, "second.mcap"]), \
        f"SYT-WIN-01.c2: sources are {[s['path'] for s in setup['sources']]}"
    made = {p.name for p in fresh.iterdir()} - {"lab.yaml", case.recording.name}
    assert made == {"w.run.json"}, f"SYT-WIN-01.c2: the window created {made}"


def test_syt_win_02_the_window_shows_what_the_model_answers(root, tmp_path):  # SYT-WIN-02
    """`SYT-WIN-02`, `SYS-0124` and `SYS-0125` Accept. `.c1`: without `C`'s outputs the choices for `C` are `simulate` and `off`; with them
    `measured` too. FAIL: `measured` offered without outputs. `.c2`: the libraries, modes and cuts shown equal the model's answers."""
    from adas_sim.launcher.availability import check_all
    from adas_sim.launcher.cuts import cuts_for_recording, topic_index
    from adas_sim.launcher.view import window_state

    case = lab_case("running_example", "cut_c")
    window = _window(root, tmp_path, case)
    state = window.state() if hasattr(window, "state") else window_state(window.selection)
    shown = {s.name: s.modes for s in state.stages}
    assert "measured" in shown["C"], f"SYT-WIN-02.c1: the choices for C are {shown['C']}"
    without = edit_recording(case, tmp_path / "no_c_out.mcap", lambda ms: [m for m in ms if m[0] != "C.out"], drop_topics=["C.out"])
    window.add_recording(without)
    window.selection = window.selection.select_recording(without)
    narrowed = {s.name: s.modes for s in window_state(window.selection).stages}
    assert narrowed["C"] == ("simulate", "off") and "measured" in narrowed["A"], f"SYT-WIN-02.c1: {narrowed}"

    current = window_state(window.selection)
    assert [(s.name, s.availability) for s in current.stages] == [(i.stage, i) for i in check_all(window.selection)], "SYT-WIN-02.c2: libraries"
    for recording in window.selection.recordings:
        assert current.cuts[recording] == tuple(
            f for f in __import__("adas_sim.launcher.cuts", fromlist=["stage_facts"]).stage_facts(window.selection, topic_index(recording))), \
            "SYT-WIN-02.c2: cuts"
        assert [c.feasible for c in cuts_for_recording(window.selection, topic_index(recording))] == [f.outputs for f in current.cuts[recording]]


def test_syt_win_03_isolate_and_the_mixed_group(root, tmp_path):  # SYT-WIN-03
    """`SYT-WIN-03`, `SYS-0194` and `SYS-0195` Accept. `.c1`: isolate on `B` leaves `B` `simulate` and every other stage with recorded
    outputs `measured`; a stage without outputs is not set `measured`. FAIL: another stage `simulate`, or `measured` without outputs.
    `.c2`: a mixed group shows mixed and choosing it is refused; both `simulate` shows `simulate`. FAIL: the mixed state chosen."""
    case = lab_case("running_example", "cut_c")
    window = _window(root, tmp_path, case)
    window.isolate("B")
    modes = {s.name: s.mode for s in window.selection.working_pipeline.stages}
    assert modes == {"A": "measured", "B": "simulate", "C": "measured", "D": "measured", "E": "measured"}, f"SYT-WIN-03.c1: {modes}"
    without = edit_recording(case, tmp_path / "no_a_out.mcap", lambda ms: [m for m in ms if m[0] != "A.out"], drop_topics=["A.out"])
    window.add_recording(without)
    window.selection = window.selection.select_recording(without)
    window.isolate("B")
    modes = {s.name: s.mode for s in window.selection.working_pipeline.stages}
    assert modes["A"] == "simulate" and modes["B"] == "simulate" and modes["C"] == "measured", f"SYT-WIN-03.c1: A has no outputs: {modes}"

    window.choose_group_mode(["A", "B"], "simulate")
    assert window.group_state(["A", "B"]) == "simulate"
    window.choose_mode("B", "measured")
    assert window.group_state(["A", "B"]) == "mixed", "SYT-WIN-03.c2: a group in two modes is not mixed"
    with pytest.raises(ValueError):
        window.choose_group_mode(["A", "B"], "mixed")


def test_anl_08_the_window_holds_no_logic_and_one_toolkit():  # ANL-08
    """`ANL-08`, `SYS-0122` and `SYS-0127` Accept. `.c1`: `check_window_boundary.py` and `check_no_graphical_toolkit.py` find nothing.
    `.c2`: each planted file access, process start or mode comparison is reported with file and line. `.c3`: a planted third-party
    import is reported with file and line."""
    root_dir = Path(__file__).resolve().parents[2]
    scripts = root_dir / "scripts"
    for name in ("check_window_boundary.py", "check_no_graphical_toolkit.py"):
        clean = subprocess.run([sys.executable, str(scripts / name)], capture_output=True, text=True)
        assert clean.returncode == 0, f"ANL-08.c1: {name}: {clean.stdout}"
    planted = subprocess.run([sys.executable, str(scripts / "check_window_boundary.py"), "--selftest"], capture_output=True, text=True)
    assert planted.returncode == 0 and planted.stdout.count("reported") == 3, f"ANL-08.c2: {planted.stdout}{planted.stderr}"
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "src" / "adas_sim" / "launcher"
        target.mkdir(parents=True)
        text = (root_dir / "src" / "adas_sim" / "launcher" / "window.py").read_text(encoding="utf-8")
        marker = "import tkinter\n"
        (target / "window.py").write_text(text.replace(marker, marker + "import PySide6\n", 1), encoding="utf-8")
        line = text.replace(marker, marker + "import PySide6\n", 1).splitlines().index("import PySide6") + 1
        found = subprocess.run([sys.executable, str(scripts / "check_no_graphical_toolkit.py"), "--root", tmp], capture_output=True, text=True)
    assert found.returncode == 1 and f"window.py:{line}:" in found.stdout and "PySide6" in found.stdout, f"ANL-08.c3: {found.stdout}"
