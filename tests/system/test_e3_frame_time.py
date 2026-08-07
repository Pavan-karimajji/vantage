# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""`GT-13` (`sim_implementation_plan.md` §2, `NR-SIM-5`): "the viewer stays
responsive on a long run" needed a real frame-time number and had none --
`NR-SIM-5`'s own text says pass 2 (Scene build + render, on the UI thread)
"is cheap because Scenes are cached and providers are pure", a claim never
previously measured. **The numbers go in this document, whatever they
are** -- this test exists to produce a fact, not to pass, the same "timed,
not asserted" discipline `ST-B2-2`/`ST-D7-7` already set.

Reuses `ST-B1-3`'s own real recording and real `df` layer providers
(`tests/fixtures/make_bsd_golden.py`'s `RECORDING`/`build_scene` --
`df/sim/layers/*.py` imported by that module's own import, so this is a
real Scene with real geometry, never an empty one that would render
trivially fast and mean nothing) -- the same 100-tick budget `ST-B1-3`
already exercises, timed instead of merely asserted non-blank.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

SIM_ROOT = Path(__file__).resolve().parent.parent.parent
MODULES_ROOT = SIM_ROOT.parent
DF_ROOT = MODULES_ROOT / "df"
FIXTURES_DIR = SIM_ROOT / "tests" / "fixtures"
for _p in (DF_ROOT, FIXTURES_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from adas_sim.core.runner import build_session_from_recording  # noqa: E402
from adas_sim.render.bev import render_scene  # noqa: E402
from adas_sim.view.viewport import Viewport  # noqa: E402
from make_bsd_golden import RECORDING, build_scene  # noqa: E402


def _require_recording():
    if not RECORDING.is_file():
        pytest.skip("modules/df/tests/carla_testruns is absent (partial clone)")


def test_gt13_frame_time_over_100_real_ticks(capsys):
    """`GT-13`'s `NR-SIM-5` number: `build_scene` + `render_scene`,
    per-tick and total, over a real recording's real geometry."""
    _require_recording()
    session = build_session_from_recording(RECORDING)
    vp = Viewport(size_px=(320, 240), scale_px_per_m=8.0, centre_m=(-2.0, 0.0))
    tick_count = min(100, len(session))

    start = time.perf_counter()
    for i in range(tick_count):
        scene = build_scene(session, i)
        frame = render_scene(scene, vp, "dark")
        assert frame.shape == (240, 320, 3)
    elapsed_s = time.perf_counter() - start

    with capsys.disabled():
        print(f"\nGT-13/NR-SIM-5: {tick_count} ticks, {RECORDING.name}")
        print(f"  total {elapsed_s:.3f}s, {elapsed_s / tick_count * 1000:.2f}ms/tick "
              f"({tick_count / elapsed_s:.1f} fps equivalent)")
