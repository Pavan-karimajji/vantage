# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""The framework's own default layer set: ego body, grid/frame furniture, ego
trail. Every recording needs these regardless of which component produced it,
so they ship here rather than being authored by any one component.

Each reads only `ctx.model` or `ctx.history`/`ctx.frames` -- **never a port**
-- so living here adds no function name to `src/adas_sim` (`R-SIM-1`) and
needs no `requires=` gate.

**Why the object and HUD layers did not move too:** both need real ports that
only a component's own wiring supplies, and a framework-level provider has no
"self" identity to resolve `self.<port>` against (`R-SIM-21`). The HUD's
ego-state readout already has a generic caller-configured path in
`view/hud.py`.

Imported unconditionally by `scene.registry`: "the framework ships a default
layer set" means these are registered before any component plug-in loads, not
merely available to opt into (`R-VAR-2`'s discovery-by-import, applied to the
framework's own contribution rather than only to a component's).
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
    port. `spacing_lateral_m` gives the grid a denser cross-spacing at
    close range without a second kind.

    **`AR-56`: distance labels moved out of this provider entirely.** They
    used to be `text` prims baked at a small, fixed metre offset from the
    origin (`y_m=0.4`/`x_m=0.4`) -- which reads fine in isolation but sits
    directly on the ego box and any near-origin object once actually
    rendered (confirmed real, `sim_audit_log.md` `AR-56`: "`-5` sits on the
    ego box"). Where a label belongs on screen is a function of the
    CURRENT VIEWPORT's visible edges, which this provider is not allowed to
    read (`R-SIM-2`) -- so the renderer now draws them, anchored near the
    frame margin instead of the crosshair, from this grid `Prim`'s own
    `spacing_m`/`spacing_lateral_m`/`extent_m` (`render/bev.py`)."""
    prims = [
        Prim(
            kind="grid", spacing_m=_GRID_SPACING_M, spacing_lateral_m=_LATERAL_LABEL_SPACING_M,
            extent_m=_GRID_EXTENT_M, style="frame.grid", z=0,
        ),
        Prim(kind="circle", cx_m=0.0, cy_m=0.0, r_m=0.15, style="frame.origin", z=1),
        Prim(kind="arrow", x_m=0.0, y_m=0.0, dx_m=1.0, dy_m=0.0, style="frame.axis", z=1),
        Prim(kind="arrow", x_m=0.0, y_m=0.0, dx_m=0.0, dy_m=1.0, style="frame.axis", z=1),
        Prim(kind="text", x_m=1.1, y_m=0.0, text="+x", style="frame.axis", z=1),
        Prim(kind="text", x_m=0.0, y_m=1.1, text="+y", style="frame.axis", z=1),
    ]
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
    function of `ctx.history`, no attribute holds state between calls.

    Two empty cases, deliberately handled differently (`AR-60`,
    same distinction `AR-53` drew for a `requires=` reference): fewer than
    two windowed ticks exist yet is TRANSIENT -- the very first tick or two
    of any recording, before there is enough history to have a trail at
    all -- and stays a silent `()`, the same as a `self.<port>` reference
    resolved but not yet arrived this tick. Every windowed tick's pose
    transforming to the SAME point is not transient: it means this
    recording carries no real ego world-position source at all, which will
    never change as more ticks arrive. That case is named and badged
    (`Layer.unavailable`), never a silent absence a user could mistake for
    "the ego never moved" -- a single dot pretending to be a trail is worse
    than no trail at all, and now the reason says so instead of nothing."""
    points_m = _relative_trail_m(ctx)
    if len(points_m) < 2:
        return ()
    if len(set(points_m)) < 2:
        return (Layer(
            id="sim.trail", group="sim", prims=(),
            unavailable="no ego world-position source in this recording -- every tick's pose "
                        "transforms to the same point, and a single dot pretending to be a "
                        "trail is worse than no trail at all",
            label="Ego trail", level=2,
        ),)
    prim = Prim(kind="polyline", points_m=points_m, style="ego.body", width_px=1.5, z=2)
    return (Layer(id="sim.trail", group="sim", prims=(prim,), label="Ego trail", level=2),)
