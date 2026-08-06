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
the file).

**`recording` became genuinely optional at `S-D8`** (`sim_player.md` §2's
own ban on requiring a file before anything shows: "it opens onto either
a recording or a start page with recent files") -- omitting it no longer
errors, it opens Screen 1. `test_omitting_both_version_and_recording_
starts_the_gui_instead_of_erroring` below replaces this file's own
pre-`S-D8` assertion that it errored; `app/gui.launch`'s own in-process
tests (`test_d8_gui_launch_wiring.py`) already prove the start-page path
itself in detail, so this file's job is only "the real subprocess entry
point does not refuse to start," proven by it still running after a
short wait rather than by waiting for an exit code a real GUI event loop
would never produce on its own."""

from __future__ import annotations

import os
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


def test_omitting_both_version_and_recording_starts_the_gui_instead_of_erroring():
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    proc = subprocess.Popen(
        [sys.executable, str(_VANTAGE_PY)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
    )
    try:
        # A real GUI event loop with nothing telling it to close runs
        # forever -- still running after a short wait IS the passing
        # signal (no immediate argparse error, no immediate crash), the
        # inverse of the old contract this test replaces.
        proc.wait(timeout=3)
        stdout, stderr = proc.communicate()
        raise AssertionError(
            f"vantage.py with no recording exited early (rc={proc.returncode}) instead of starting the "
            f"GUI -- stdout={stdout!r} stderr={stderr!r}"
        )
    except subprocess.TimeoutExpired:
        pass  # still running -- the GUI started, exactly as expected
    finally:
        proc.kill()
        proc.wait(timeout=10)
