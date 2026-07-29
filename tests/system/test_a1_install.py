# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-A1 system tests: ST-A1-1, ST-A1-2 (docs/sim_implementation_plan.md).

Both exercise the real toolchain (pip, conan) rather than the package in
isolation, and both skip with a named reason when that toolchain step was not
performed for this checkout, per §3.1's integration-test discipline.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SIM_ROOT = Path(__file__).resolve().parent.parent.parent


def _venv_python() -> Path | None:
    candidate = SIM_ROOT / ".venv" / "Scripts" / "python.exe"
    if not candidate.is_file():
        candidate = SIM_ROOT / ".venv" / "bin" / "python"
    return candidate if candidate.is_file() else None


def test_import_adas_sim_succeeds_from_outside_the_repo(tmp_path):
    """ST-A1-1: `pip install -e modules/sim` then `import adas_sim` from a
    directory outside the repo -- proves the editable install does not
    secretly depend on the current working directory (P-2)."""
    python = _venv_python()
    if python is None:
        pytest.skip("no modules/sim/.venv -- editable install was not performed for this checkout")

    result = subprocess.run(
        [str(python), "-c", "import adas_sim; print(adas_sim.__version__)"],
        cwd=str(tmp_path),
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0.1.0"


def test_conan_editable_add_resolves_adas_sim():
    """ST-A1-2: `conan editable add modules/sim` succeeds and `conan graph info`
    resolves `adas-sim`."""
    conan = shutil.which("conan")
    if conan is None:
        pytest.skip("conan not on PATH")

    add = subprocess.run(
        [conan, "editable", "add", str(SIM_ROOT)],
        capture_output=True, text=True,
    )
    assert add.returncode == 0, add.stderr

    try:
        info = subprocess.run(
            [conan, "graph", "info", "--requires=adas-sim/0.1.0"],
            capture_output=True, text=True,
        )
        assert info.returncode == 0, info.stderr
        assert "adas-sim/0.1.0" in info.stdout
    finally:
        subprocess.run([conan, "editable", "remove", str(SIM_ROOT)], capture_output=True, text=True)
        # Re-add: this module stays registered editable for the rest of the
        # toolchain during normal development (matches df/vdy/mathlib/
        # shared_config, `conan editable list`), the same way this test found it.
        subprocess.run([conan, "editable", "add", str(SIM_ROOT)], capture_output=True, text=True)
