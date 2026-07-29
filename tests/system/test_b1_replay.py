# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B1 system tests: ST-B1-1, ST-B1-2, ST-B1-3 (docs/sim_implementation_plan.md)."""

from __future__ import annotations

import sys
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
from adas_sim.scene.codec import decode_scene  # noqa: E402
from adas_sim.view.viewport import Viewport  # noqa: E402
from make_bsd_golden import RECORDING, SAMPLE_TICKS, build_scene  # noqa: E402

GOLDEN_DIR = SIM_ROOT / "tests" / "fixtures" / "golden"


def _require_recording():
    if not RECORDING.is_file():
        pytest.skip("modules/df/tests/carla_testruns is absent (partial clone)")


def test_replay_matches_the_golden_for_every_sampled_tick():
    """ST-B1-1: the Scene for every (sampled) tick matches the golden."""
    _require_recording()
    session = build_session_from_recording(RECORDING)
    for tick_index in SAMPLE_TICKS:
        index = tick_index if tick_index >= 0 else len(session) + tick_index
        golden_path = GOLDEN_DIR / f"bsd_tick{index}.scene.bin"
        if not golden_path.is_file():
            pytest.skip(f"golden {golden_path} is missing -- run make_bsd_golden.py")
        golden_scene = decode_scene(golden_path.read_bytes())
        fresh_scene = build_scene(session, tick_index)
        assert fresh_scene == golden_scene, f"tick {index} diverged from its golden"


def test_a_different_project_produces_a_different_ego_box_and_zone():
    """ST-B1-2: configuration drives the picture (D3), proven end to end."""
    _require_recording()
    session = build_session_from_recording(RECORDING)
    base_scene = build_scene(session, 0, project="base")
    cus1_scene = build_scene(session, 0, project="cus1")

    def ego_prim(scene):
        return next(p for layer in scene.layers if layer.id == "df.common.ego" for p in layer.prims)

    def zone_prims(scene):
        return [p for layer in scene.layers if layer.id == "bsd.zone" for p in layer.prims]

    assert ego_prim(base_scene).length_m != ego_prim(cus1_scene).length_m
    base_zone_points = [p.points_m for p in zone_prims(base_scene)]
    cus1_zone_points = [p.points_m for p in zone_prims(cus1_scene)]
    assert base_zone_points != cus1_zone_points


def test_headless_render_of_100_ticks_raises_nothing_and_is_non_blank():
    """ST-B1-3."""
    _require_recording()
    session = build_session_from_recording(RECORDING)
    vp = Viewport(size_px=(320, 240), scale_px_per_m=8.0, centre_m=(-2.0, 0.0))
    tick_count = min(100, len(session))
    for i in range(tick_count):
        scene = build_scene(session, i)
        frame = render_scene(scene, vp, "dark")
        assert frame.shape == (240, 320, 3)
        assert frame.std() > 0, f"tick {i}: blank frame"
