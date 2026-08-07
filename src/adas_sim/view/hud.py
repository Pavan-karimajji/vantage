# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""HUD text and the stale/invalid banner (S-B3 slice 12,
`sim_visualization_spec.md` §10). Pure formatting, no pixels, no Qt --
`view/` stays headless-testable.

**Scope, and why it stops where it does.** §10 also lists an origin dot,
`+x`/`+y` axis arrows and a distance grid -- `modules/df/sim/layers/
common.py`'s own `frame_layer` already draws exactly this today, as a
component layer, in `modules/df` (a different submodule this slice does
not touch). Whether that responsibility moves into framework-drawn HUD
furniture is a real question with a real answer, but it is a cross-
submodule one -- not decided here, and not silently duplicated either.
§10's ego state line (`v`/`a`/`yaw`/`ay`) needs *some* signal address for
each, and the framework has no calibration of its own to guess one from
(`R-SIM-1`) -- `HudInfo.ego_state` and `stale_ports`' `max_age_s` are
therefore both **caller-supplied**, empty by default, so a HUD with
nothing configured shows exactly what the framework itself knows (scale,
time, tick, project/scenario/pipeline/build id) and nothing invented.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from adas_sim.core.tick import Tick


@dataclass(frozen=True, slots=True)
class HudInfo:
    scale_px_per_m: float
    t_s: float
    tick_index: int
    head_tick: int
    project: str
    scenario: str
    pipeline: str
    build_id: str
    #: `ST-C5-2`, `R-SIM-3a`: which tier the viewer's `ProjectModel` actually
    #: resolved from -- `"embedded"` / `"library"` / `"checkout"` /
    #: `"explicit"` -- so two readers agreeing is never a coincidence.
    #: `None` means "no `ProjectModel` supplied" (a caller that predates
    #: this field, e.g. `render/capture.py`'s frame-only path), distinct
    #: from a resolved model that always states its own origin.
    bundle_origin: str | None = None
    #: `{"vx": ..., "ax": ..., "yaw_rate": ..., "ay": ...}` (`R-COORD-2`'s
    #: own frozen ego-state vocabulary -- no `vy`, `ay` is a passthrough).
    #: `None` (not an empty dict) means "not configured", distinct from a
    #: configured-but-currently-unavailable state.
    ego_state: Mapping[str, float] | None = None


def format_hud_lines(info: HudInfo) -> tuple[str, ...]:
    """§10's furniture this module can build without a component's own
    calibration: scale, `t = .. · tick ..`, the compact project line, and
    -- only if `info.ego_state` was actually supplied -- the ego state
    line."""
    project_line = f"{info.project} · {info.scenario} · {info.pipeline} · {info.build_id}"
    if info.bundle_origin is not None:
        project_line += f" · cfg:{info.bundle_origin}"
    lines = [
        f"scale {info.scale_px_per_m:.1f} px/m",
        f"t = {info.t_s:.2f}s · tick {info.tick_index}/{info.head_tick}",
        project_line,
    ]
    if info.ego_state:
        parts = []
        if "vx" in info.ego_state:
            parts.append(f"v {info.ego_state['vx'] * 3.6:.0f} km/h")
        if "ax" in info.ego_state:
            parts.append(f"a {info.ego_state['ax']:.1f} m/s²")
        if "yaw_rate" in info.ego_state:
            parts.append(f"yaw {math.degrees(info.ego_state['yaw_rate']):+.1f} °/s")
        if "ay" in info.ego_state:
            parts.append(f"ay {info.ego_state['ay']:.2f} m/s²")
        if parts:
            lines.append(" · ".join(parts))
    return tuple(lines)


def stale_ports(tick: Tick, max_age_s: Mapping[str, float] | None = None) -> tuple[str, ...]:
    """`UT-B3-5`: a port is stale when `valid == 0` (always checkable --
    every `PortValue` carries it) **or** its `age_s` exceeds a declared
    maximum -- only for ports named in `max_age_s`, since that maximum is
    a component's own `<FN>_MAX_AGE_OBJECTS_S`-style calibration, never a
    framework constant."""
    max_age_s = max_age_s or {}
    stale = []
    for name, port in tick.ports.items():
        if not port.valid:
            stale.append(name)
        elif name in max_age_s and port.age_s > max_age_s[name]:
            stale.append(name)
    return tuple(stale)


def format_stale_banner(stale: tuple[str, ...]) -> str | None:
    if not stale:
        return None
    return "STALE: " + ", ".join(stale)


def format_stimulus_only_banner(has_simulated_output: bool) -> str | None:
    """`AR-57`: the "why is a component's own result missing"
    answer that needs no `Pipeline` -- `sim_player.md` §6 describes only the
    case where *"the recording carries stage outputs"*; this is the
    sentence for the other case, which is every legacy recording in this
    repo. `None` (no banner) when `has_simulated_output` is true -- shown
    only when abnormal, never folded into `format_hud_lines`'s always-true
    baseline (`L-3`)."""
    if has_simulated_output:
        return None
    # Plain ASCII, not an em-dash: this string is rasterized as pixels
    # (`render_scene`), not printed as prose -- matching `format_stale_
    # banner`'s own convention, never a glyph a rendering font might lack.
    return "STIMULUS-ONLY: no port here was ever a stage's own computed output -- resim through a pipeline to see one"
