# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""S-B3 slice 12 `view/hud.py` tests: `UT-B3-5` (docs/
sim_implementation_plan.md) plus HUD line formatting. No Qt (`view/`
stays headless-testable)."""

from __future__ import annotations

from adas_sim.session.tick import Pose2D, PortValue, Tick
from adas_sim.player.panels.hud import (
    HudInfo, format_hud_lines, format_stale_banner, format_stimulus_only_banner, stale_ports,
)

_POSE = Pose2D(x_m=0.0, y_m=0.0, yaw_rad=0.0)


def _info(**overrides) -> HudInfo:
    defaults = dict(
        scale_px_per_m=10.0, t_s=12.35, tick_index=247, head_tick=1200,
        project="base", scenario="fixtures/x.yaml", pipeline="none", build_id="abc123",
    )
    defaults.update(overrides)
    return HudInfo(**defaults)


def test_format_hud_lines_without_ego_state_is_three_lines():
    lines = format_hud_lines(_info())
    assert len(lines) == 3
    assert "12.35" in lines[1] and "247/1200" in lines[1]
    assert "base" in lines[2] and "abc123" in lines[2]


def test_format_hud_lines_with_ego_state_adds_a_fourth_line():
    lines = format_hud_lines(_info(ego_state={"vx": 10.0, "ax": 0.0, "yaw_rate": 0.02, "ay": 0.21}))
    assert len(lines) == 4
    assert "km/h" in lines[3]
    assert "m/s" in lines[3]
    assert "°/s" in lines[3]


def test_format_hud_lines_ego_state_only_includes_supplied_fields():
    lines = format_hud_lines(_info(ego_state={"vx": 10.0}))
    assert len(lines) == 4
    assert "km/h" in lines[3]
    assert "yaw" not in lines[3]


def test_format_hud_lines_ego_state_none_vs_empty_dict_both_add_nothing():
    assert len(format_hud_lines(_info(ego_state=None))) == 3
    assert len(format_hud_lines(_info(ego_state={}))) == 3


def _tick(ports: dict) -> Tick:
    return Tick(index=0, t_ns=0, dt_ns=0, ports=ports, pose=_POSE)


def test_stale_ports_flags_an_invalid_port():
    """UT-B3-5."""
    tick = _tick({"a": PortValue(name="a", message=b"", origin="measured", valid=False)})
    assert stale_ports(tick) == ("a",)


def test_stale_ports_ignores_a_valid_port_with_no_max_age_declared():
    tick = _tick({"a": PortValue(name="a", message=b"", origin="measured", valid=True, hold_age_s=999.0)})
    assert stale_ports(tick) == ()


def test_stale_ports_flags_a_valid_port_exceeding_its_declared_max_age():
    """UT-B3-5: age exceeding the *declared* maximum -- only for a port
    actually named in max_age_s (the framework has no calibration of its
    own, R-SIM-1)."""
    tick = _tick({"a": PortValue(name="a", message=b"", origin="measured", valid=True, hold_age_s=0.5)})
    assert stale_ports(tick, max_age_s={"a": 0.3}) == ("a",)
    assert stale_ports(tick, max_age_s={"a": 1.0}) == ()


def test_stale_ports_exactly_at_the_maximum_is_not_stale():
    tick = _tick({"a": PortValue(name="a", message=b"", origin="measured", valid=True, hold_age_s=0.3)})
    assert stale_ports(tick, max_age_s={"a": 0.3}) == ()


def test_stale_ports_multiple_ports_some_stale_some_not():
    tick = _tick({
        "a": PortValue(name="a", message=b"", origin="measured", valid=False),
        "b": PortValue(name="b", message=b"", origin="measured", valid=True, hold_age_s=0.1),
    })
    assert stale_ports(tick) == ("a",)


def test_format_stale_banner_none_when_nothing_stale():
    assert format_stale_banner(()) is None


def test_format_stale_banner_names_every_stale_port():
    banner = format_stale_banner(("a", "b"))
    assert banner is not None
    assert "a" in banner and "b" in banner


def test_format_stimulus_only_banner_none_when_a_stage_computed_something():
    """`AR-57`: no banner for the ordinary, complete case."""
    assert format_stimulus_only_banner(True) is None


def test_format_stimulus_only_banner_names_the_fix_when_nothing_was_computed():
    banner = format_stimulus_only_banner(False)
    assert banner is not None
    assert "STIMULUS-ONLY" in banner
    assert "resim" in banner.lower()
