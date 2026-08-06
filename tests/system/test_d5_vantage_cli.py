# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-D5 system test: `scripts/vantage.py --version` (`UT-D5-2`) works with
no `recording` argument -- the real CLI wiring, not just `app.version`'s
own pure function (`tests/unit/test_d5_version.py`'s job). Subprocess,
same reasoning `tests/system/test_d6_probe.py`'s own compiled-fixture
tests give for exercising the real entry point rather than importing
`main()` in-process (`scripts/vantage.py` mutates `sys.path` at import
time, which a same-process import would leak into every other test in
the file)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_VANTAGE_PY = Path(__file__).resolve().parents[2] / "scripts" / "vantage.py"


def test_version_exits_zero_with_no_recording_argument():
    result = subprocess.run(
        [sys.executable, str(_VANTAGE_PY), "--version"], capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0
    assert "vantage " in result.stdout
    assert "abi_version" in result.stdout


def test_omitting_both_version_and_recording_errors_naming_the_missing_argument():
    result = subprocess.run(
        [sys.executable, str(_VANTAGE_PY)], capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0
    assert "recording" in result.stderr
