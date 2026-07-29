# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-A3 system test: ST-A3-1 (docs/sim_implementation_plan.md) -- the
palette is validated by computation, not taste."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from adas_sim.render.palette_check import check_theme

SIM_ROOT = Path(__file__).resolve().parent.parent.parent


def test_palette_check_cli_exits_zero_for_dark_and_light():
    """ST-A3-1. The CLI itself runs both themes in one invocation; this
    confirms that process exits 0 and reports success for each."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SIM_ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-m", "adas_sim.render.palette_check"],
        cwd=str(SIM_ROOT), env=env,
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    assert "ALL CHECKS PASS" in result.stdout


def test_every_6_8_band_pair_has_a_named_secondary_encoding():
    """ST-A3-1: the acceptance criterion is a named secondary encoding, not
    an assumed one."""
    for theme in ("dark", "light"):
        report, ok = check_theme(theme)
        secondary_rows = [row for row in report if row[0].startswith("Named secondary encoding")]
        assert secondary_rows, f"no secondary-encoding check ran for {theme}"
        for name, passed, detail in secondary_rows:
            assert passed, f"{theme}/{name}: {detail}"
        assert ok
