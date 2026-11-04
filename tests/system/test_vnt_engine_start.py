# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: VANTAGE
# @author Pavan Karimajji

"""`SYT-LCH-02` and `ANL-07` (`VANTAGE_Test_Spec.md` sections 11 and 19): the engine is started from one function with its options,
and from one place. `F-SPY` is the process start of `engine/bridge.py` replaced by a recorder; the real runs go through
`tests/support/lab_cases.py::edit_setup`, so the parallel runner's per-worker names hold.

Where the spec leaves a step open it is chosen so the case can fail:
- "the developer command line is the setup path (and `--threads`, `--wait-for-attach` when asked)" is checked with and without both
  options; "the batch one adds exactly `--supervise` and the deadline" is the difference of the two lists, nothing else;
- the real pair runs `running_example` `cut_c` directly and under `--supervise --attempt-timeout-ms 120000` and compares every topic
  with the lab's comparator, the engine-run recordings being the outputs.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import adas_sim.engine.bridge as bridge
from adas_sim.diagnostics.errors import AuthoringError
from adas_sim.engine.bridge import run_engine
from tests.support.engine_runs import Recording, case_change, compare_recordings, engine_exe
from tests.support.lab_cases import edit_setup, lab_case


@pytest.fixture
def spy(monkeypatch):
    """`F-SPY` for the engine: every command line `run_engine` would start, none started."""
    started: list[list[str]] = []

    def record(cmd, *, timeout_s=0):
        started.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(bridge, "_run_subprocess", record)
    return started


def test_syt_lch_02_c1_a_supervised_start_needs_its_deadline(spy, tmp_path):  # SYT-LCH-02.c1
    """`SYT-LCH-02.c1`, `SYS-0109` Accept: with supervision and no deadline an error naming `attempt_timeout_ms` and no process; with a
    deadline `--attempt-timeout-ms` equal to it. FAIL: a process started without a deadline, or another value."""
    setup = tmp_path / "s.run.json"
    setup.write_text("{}", encoding="utf-8")
    with pytest.raises(AuthoringError, match="attempt_timeout_ms"):
        run_engine(setup, supervise=True, simengine_path=Path("simengine"))
    assert spy == [], f"SYT-LCH-02.c1: a process was started without a deadline: {spy}"
    run_engine(setup, supervise=True, attempt_timeout_ms=4321, simengine_path=Path("simengine"))
    assert spy[-1][spy[-1].index("--attempt-timeout-ms") + 1] == "4321", f"SYT-LCH-02.c1: {spy[-1]}"


def test_syt_lch_02_c2_the_two_faces_differ_by_exactly_the_supervisor_options(spy, tmp_path):  # SYT-LCH-02.c2
    """`SYT-LCH-02.c2`, `SYS-0110` Accept: the developer command line is the setup path (and `--threads`, `--wait-for-attach` when
    asked); the batch one adds exactly `--supervise` and the deadline. FAIL: any other option."""
    setup = tmp_path / "s.run.json"
    engine = Path("simengine")
    run_engine(setup, simengine_path=engine)
    run_engine(setup, threads=3, wait_for_attach=True, simengine_path=engine)
    run_engine(setup, supervise=True, attempt_timeout_ms=900, simengine_path=engine)
    run_engine(setup, supervise=True, attempt_timeout_ms=900, restart_on_crash=2, simengine_path=engine)
    plain, asked, batch, restarting = spy
    assert plain == ["simengine", str(setup)], f"SYT-LCH-02.c2: the developer command is {plain}"
    assert asked == ["simengine", str(setup), "--threads", "3", "--wait-for-attach"], f"SYT-LCH-02.c2: {asked}"
    assert batch == plain + ["--supervise", "--attempt-timeout-ms", "900"], f"SYT-LCH-02.c2: the batch command is {batch}"
    assert restarting == batch + ["--restart-on-crash", "2"], f"SYT-LCH-02.c2: {restarting}"
    for command in spy:
        assert "--config" not in command and "--timeout-ms" not in command, f"SYT-LCH-02.c2: a removed option in {command}"


def test_syt_lch_02_c3_the_two_faces_give_equal_outputs(tmp_path):  # SYT-LCH-02.c3
    """`SYT-LCH-02.c3`: the developer run and the batch run of `cut_c` are equal outputs on every port. FAIL: a difference."""
    case = lab_case("running_example", "cut_c")
    recordings = {}
    for face, kwargs in (("developer", {}), ("batch", {"supervise": True, "attempt_timeout_ms": 120000})):
        out = tmp_path / f"{face}.mcap"
        setup = edit_setup(case, tmp_path, case_change(face, None), name=face, outputs=out)
        result = run_engine(setup, simengine_path=engine_exe(), output_path=out, **kwargs)
        assert result.ok, f"SYT-LCH-02.c3: the {face} run exited {result.exit_code}: {result.stderr[-300:]}"
        recordings[face] = Recording(out)
    differences = compare_recordings(recordings["developer"], recordings["batch"])
    assert not differences, f"SYT-LCH-02.c3: the faces differ on {differences[:3]}"


def test_anl_07_one_place_starts_the_engine_from_a_file_just_written():  # ANL-07
    """`ANL-07`, `SYS-0107` and `SYS-0108` Accept. `.c1`: `check_one_engine_start.py` finds nothing. FAIL: any finding. `.c2`: a planted
    start from a `Selection` argument is reported with file and line. FAIL: the copy passes. `.c3`: a planted second process start
    naming `simengine` is reported with file and line. FAIL: the copy passes."""
    script = Path(__file__).resolve().parents[2] / "scripts" / "check_one_engine_start.py"
    clean = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert clean.returncode == 0, f"ANL-07.c1: {clean.stdout}"
    planted = subprocess.run([sys.executable, str(script), "--selftest"], capture_output=True, text=True)
    assert planted.returncode == 0 and planted.stdout.count("reported") == 2, f"ANL-07.c2/.c3: {planted.stdout}{planted.stderr}"
