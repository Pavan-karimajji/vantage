# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""PT-45 (python_tool_envs_plan.md PR-7, D10): vantage.bat runs Vantage from
sim's own environment .venv-sim-win32, after sim's setup `--check-only`
says it is ready -- never modules/sim/.venv, never a global `py -3`.

The REAL vantage.bat is copied into a temp folder beside a stub setup.bat
(exit code and output chosen per test) and, where the env is "present", a
real throwaway venv whose scripts/gui.py only prints the interpreter that
ran it. Windows-only (vantage.bat is a .bat launcher)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="vantage.bat is Windows-only")

SIM = Path(__file__).resolve().parents[2]
REFUSAL = ("Reason: sim:sim's environment .venv-sim-win32 does not exist.",
           "Fix:    create it with setup, then retry.",
           'Run:    cd /d "C:\\adas\\modules\\sim" && setup.bat --python-env sim:sim')


def _tree(tmp_path: Path, setup_rc: int) -> Path:
    root = tmp_path / "sim dir"  # a space on purpose: the quoting lesson
    (root / "scripts").mkdir(parents=True)
    shutil.copy(SIM / "vantage.bat", root / "vantage.bat")
    lines = ["@echo off", "echo --- Python tool environments ---"]
    if setup_rc:
        lines += [f"echo {line.replace('&', '^&')}" for line in REFUSAL]
    else:
        lines.append("echo sim:sim  Python 3.12  already satisfied")
    lines.append(f"exit /b {setup_rc}")
    (root / "setup.bat").write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    (root / "scripts" / "gui.py").write_text(
        "import sys; print('GUI-STARTED-BY', sys.executable)\n", encoding="utf-8")
    return root


def _run(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["cmd.exe", "/c", str(root / "vantage.bat")],
                          capture_output=True, text=True, timeout=120)


def test_env_not_ready_is_refused_with_setups_run_line_and_nothing_starts(tmp_path):
    root = _tree(tmp_path, setup_rc=1)
    proc = _run(root)
    assert proc.returncode == 1
    for line in REFUSAL:
        assert line in proc.stdout
    assert "Vantage not started" in proc.stdout
    assert "GUI-STARTED-BY" not in proc.stdout


def test_env_ready_runs_the_launcher_from_venv_sim_win32(tmp_path):
    root = _tree(tmp_path, setup_rc=0)
    subprocess.run([sys.executable, "-m", "venv", "--without-pip",
                    str(root / ".venv-sim-win32")], check=True)
    proc = _run(root)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    started = [l for l in proc.stdout.splitlines() if l.startswith("GUI-STARTED-BY ")]
    assert started, proc.stdout
    exe = Path(started[0].split(" ", 1)[1])
    assert exe.parent == root / ".venv-sim-win32" / "Scripts"


def test_env_ready_but_python_missing_is_refused(tmp_path):
    root = _tree(tmp_path, setup_rc=0)
    proc = _run(root)
    assert proc.returncode == 1
    assert "Run:    cd /d" in proc.stdout
    assert "GUI-STARTED-BY" not in proc.stdout
