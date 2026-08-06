# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D5 system test: `ST-D5-1`, the clean-machine test, as close as this
shell can honestly get to it (`sim_implementation_plan.md`'s own checklist
wording -- "no repo, no Python, no Conan cache and no component
checkout"). **Not the same claim as a real separate clean VM would prove**
-- this machine still HAS Python, Conan and a checkout, just not inside
the directory the frozen build is copied to and run from. What this DOES
prove, for real: the frozen `dist/vantage/` folder produced by `scripts/
freeze.py` needs no `PYTHONPATH`, no venv activation and no sibling
checkout to launch `--version` or open a real recording -- copied to an
isolated `tmp_path` with nothing else in it, `vantage.exe` still runs.

Skips with a named reason if `scripts/freeze.py` has not been run in this
checkout (`dist/vantage/vantage.exe` absent) -- freezing takes minutes and
pulls in PyInstaller, so this is never part of the default `pytest` run
gate, the same "real toolchain, real fixture, skip if absent" precedent
`test_c8_relocatability_installed.py` sets for a real compiled `df_sil`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

_SIM_ROOT = Path(__file__).resolve().parents[2]
_MODULES_ROOT = _SIM_ROOT.parent
_FROZEN_EXE = _SIM_ROOT / "dist" / "vantage" / "vantage.exe"
_TINY = _SIM_ROOT / "tests" / "fixtures" / "tiny.mcap"
_SHARED_CONFIG = _MODULES_ROOT / "shared_config"

pytestmark = pytest.mark.skipif(
    not _FROZEN_EXE.is_file(),
    reason="dist/vantage/vantage.exe absent -- run `python scripts/freeze.py` first (S-D5, minutes, pulls in PyInstaller)",
)


def _isolated_copy(tmp_path: Path, *, with_shared_config: bool = False) -> Path:
    """Copies the frozen folder (never the checkout, never the venv) to a
    directory with nothing else in it -- the one thing a same-machine test
    CAN prove: no relative reach-back to the repo or venv that a same-
    directory run would silently paper over.

    `with_shared_config`: a REAL, separate gap found running this build for
    the first time -- `model/ego.py`'s `MODULES_ROOT = Path(__file__).
    resolve().parents[4]` (R-VAR-4's "checkout" fallback tier, `S-A2`)
    assumes the source tree's own layout, which does not exist once frozen.
    A pure `sim view <recording>` with no `--pipeline`/config bundle has no
    OTHER tier to fall back to (R-SIM-3a's packed bundle is per-component,
    not part of the bare framework), so it needs `shared_config` placed
    exactly where that resolution lands. Real, not this pass's fix --
    tracked in the stage's own Status note rather than silently worked
    around."""
    dest = tmp_path / "vantage"
    shutil.copytree(_FROZEN_EXE.parent, dest)
    shutil.copy(_TINY, tmp_path / "tiny.mcap")
    if with_shared_config:
        shutil.copytree(_SHARED_CONFIG, tmp_path / "shared_config")
    return dest / "vantage.exe"


def test_version_runs_standalone_from_an_isolated_copy(tmp_path):
    exe = _isolated_copy(tmp_path)
    result = subprocess.run([str(exe), "--version"], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0
    assert "vantage " in result.stdout
    assert "unknown" not in result.stdout  # --copy-metadata adas-sim landed for real, not just the honest fallback


def test_opening_a_real_recording_from_an_isolated_copy_does_not_crash_on_load(tmp_path):
    exe = _isolated_copy(tmp_path, with_shared_config=True)
    recording = tmp_path / "tiny.mcap"
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    process = subprocess.Popen(
        [str(exe), str(recording)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    )
    try:
        # A load-time crash (the exact failure mode this test exists to
        # catch -- see app/version.py's own PackageNotFoundError note,
        # found running this exact build for the first time) exits within
        # a second or two, well inside this window; a healthy run sits in
        # its event loop and never exits on its own.
        _stdout, stderr = process.communicate(timeout=5)
        pytest.fail(f"vantage.exe exited early (code {process.returncode}) opening a recording -- stderr:\n{stderr}")
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            _stdout, stderr = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            _stdout, stderr = process.communicate()
        assert "Traceback" not in stderr
