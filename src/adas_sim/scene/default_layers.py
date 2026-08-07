# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The framework's own default layer set (`AR-52`, 2026-08-07): ego body,
grid/frame furniture, ego trail -- every recording needs these regardless of
which component produced it, so they are shipped here, not authored by any
one component. **Not a rename of `df`'s old `sim/layers/common.py`
providers**: each of the three below reads only `ctx.model` (`ProjectModel`,
already framework-level, `R-SIM-1`) or `ctx.history`/`ctx.frames` (a
coordinate-frame transform of `Tick.pose`, likewise framework-level) --
never a port, so moving them here adds no function's name to `src/adas_sim`
and needs no `requires=` gate.

**Why `objects`/`hud` did not move too.** `df.common.objects` needs
`source.gen_object_list` and `df.common.hud` needs `source.veh_dyn` -- real
port dependencies only a component's own wiring supplies (`R-SIM-21`: a
framework-level provider has no "self" component identity to resolve
`self.<port>` against). The HUD's ego-state readout already has a generic,
caller-configured path with no component-specific default
(`view/hud.py`'s own `HudInfo.ego_state`/`format_hud_lines`, documented
there since S-B3) -- `df.common.hud`'s BEV-drawn duplicate of the same
numbers stays `df`'s own layer, unmoved.

This module is imported unconditionally by `scene.registry` (bottom of that
file) -- "the framework ships a default layer set" means these three are
registered before any component's plug-in is ever loaded, not merely
available for one to opt into (`R-VAR-2`'s "discovery by import" applied to
the framework's own contribution, not just a component's).
"""

from __future__ import annotations

from adas_sim.core.history import LayerCtx
from adas_sim.scene.registry import layer_provider
from adas_sim.scene.types import Layer, Prim

_GRID_SPACING_M = 10.0
_GRID_EXTENT_M = 100.0
#: Lateral (+y) labels are denser than longitudinal (+x) ones -- there just
#: isn't much to see off to the side at close-in scale, not highway scale, so
#: 10m steps read as too coarse there even though they're fine dead ahead.
_LATERAL_LABEL_SPACING_M = 5.0

#: Ego-trail window: the last N ticks, matching a few seconds at typical
#: replay rates -- long enough to read as a trail, short enough to stay cheap.
_TRAIL_WINDOW_TICKS = 60


@layer_provider("sim.frame", group="sim")
def frame_layer(ctx: LayerCtx) -> tuple[Layer, ...]:
    """Grid + origin/axis furniture -- needs only the project model, no
    port. Distance labels (`frame.grid_label`, sim_visualization_spec.md
    §3.2) give the grid actual coordinate references. Bare numbers, no unit
    suffix repeated at every tick -- the axis is metres throughout,
    stated once, not on every label."""
    prims = [
        Prim(kind="grid", spacing_m=_GRID_SPACING_M, extent_m=_GRID_EXTENT_M, style="frame.grid", z=0),
        Prim(kind="circle", cx_m=0.0, cy_m=0.0, r_m=0.15, style="frame.origin", z=1),
        Prim(kind="arrow", x_m=0.0, y_m=0.0, dx_m=1.0, dy_m=0.0, style="frame.axis", z=1),
        Prim(kind="arrow", x_m=0.0, y_m=0.0, dx_m=0.0, dy_m=1.0, style="frame.axis", z=1),
        Prim(kind="text", x_m=1.1, y_m=0.0, text="+x", style="frame.axis", z=1),
        Prim(kind="text", x_m=0.0, y_m=1.1, text="+y", style="frame.axis", z=1),
    ]
    x_steps = int(_GRID_EXTENT_M / _GRID_SPACING_M)
    for i in range(1, x_steps + 1):
        d = i * _GRID_SPACING_M
        prims.append(Prim(kind="text", x_m=d, y_m=0.4, text=f"{d:.0f}", style="frame.grid_label", z=1))
        prims.append(Prim(kind="text", x_m=-d, y_m=0.4, text=f"{-d:.0f}", style="frame.grid_label", z=1))
    y_steps = int(_GRID_EXTENT_M / _LATERAL_LABEL_SPACING_M)
    for i in range(1, y_steps + 1):
        d = i * _LATERAL_LABEL_SPACING_M
        prims.append(Prim(kind="text", x_m=0.4, y_m=d, text=f"{d:.0f}", style="frame.grid_label", z=1))
        prims.append(Prim(kind="text", x_m=0.4, y_m=-d, text=f"{-d:.0f}", style="frame.grid_label", z=1))
    return (Layer(id="sim.frame", group="sim", prims=tuple(prims), label="Frame", level=1),)


@layer_provider("sim.ego", group="sim")
def ego_layer(ctx: LayerCtx) -> tuple[Layer, ...]:
    """The real, asymmetric ego body (`EgoModel`) -- never the cosmetic
    symmetric box (`UT-B1-4`: changing the project changes this box)."""
    ego = ctx.model.ego()
    cx_m = (ego.x_front_m + ego.x_rear_m) / 2.0
    length_m = ego.x_front_m - ego.x_rear_m
    prim = Prim(
        kind="box", cx_m=cx_m, cy_m=0.0, length_m=length_m, width_m=2.0 * ego.half_width_m,
        yaw_rad=0.0, style="ego.body", pick_id="ego", z=8,
    )
    return (Layer(id="sim.ego", group="sim", prims=(prim,), label="Ego", level=1),)


def _relative_trail_m(ctx: LayerCtx) -> tuple[tuple[float, float], ...]:
    """The last `_TRAIL_WINDOW_TICKS` ego positions, each **transformed**
    from `Tick.pose` (real ego-in-world data, wherever it came from -- a
    world model's ground truth, a VDY-style pose port) into the *current*
    tick's ego frame via `ctx.frames.to_ego`. A coordinate-frame transform of
    already-known data, never an estimate.

    **This function used to dead-reckon vx/yaw_rate over time instead** --
    caught in review as exactly the kind of thing a visualization layer must
    never do: an estimate of information the SUT/world model did not
    directly provide, built on an assumption (no side-slip, simple heading
    integration) that could be wrong. `R-SIM-7`'s "reconstruct from
    calibration" allowance does not cover this at all -- calibration is
    fixed and deterministic; integrating a noisy time-varying signal is an
    algorithm, which belongs in a real component, not here. If `Tick.pose`
    has no real source, every tick's pose is the coordinate origin, and the
    transformed points are correctly identical -- an honestly flat trail,
    not a fabricated curve.
    """
    ticks = ctx.history.last(_TRAIL_WINDOW_TICKS)
    if len(ticks) < 2:
        return ()
    return tuple(ctx.frames.to_ego(t.pose.x_m, t.pose.y_m) for t in ticks)


@layer_provider("sim.trail", group="sim")
def trail_layer(ctx: LayerCtx) -> tuple[Layer, ...]:
    """The ego's own recent path -- a temporal layer (`UT-B1-12`): pure
    function of `ctx.history`, no attribute holds state between calls. Draws
    nothing when every windowed tick's pose transforms to the same point
    (no real ego-position source for this recording) -- a single dot
    pretending to be a trail is worse than no trail at all."""
    points_m = _relative_trail_m(ctx)
    if len(points_m) < 2 or len(set(points_m)) < 2:
        return ()
    prim = Prim(kind="polyline", points_m=points_m, style="ego.body", width_px=1.5, z=2)
    return (Layer(id="sim.trail", group="sim", prims=(prim,), label="Ego trail", level=2),)
