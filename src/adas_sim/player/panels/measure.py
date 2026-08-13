# Copyright (c) <ORG>. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: SIM
# @author Pavan Karimajji

"""Ruler, range rings and persistent annotations (S-B3 slice 11,
`sim_visualization_spec.md` §8). Pure state + geometry, no pixels, no Qt --
`view/` stays headless-testable.

**Composed as ordinary `Prim`s, not a second rendering path.** `MeasureState.
overlay_prims()` returns `Prim`s in the same closed catalogue every layer
provider uses (`scene/types.py`), drawn by `render/bev.render_scene`'s
existing `_draw_prim` -- "the renderer hit-tests the prims it actually
drew" (§7.1) extends here to "the renderer draws the measurement it
actually computed", one path rather than a parallel canvas-overlay
mechanism. **Cursor readout is deliberately not a `Prim`** -- a live
mouse-move at BEV frame rate would mean a full `render_scene` (a
matplotlib figure, not cheap, `render/bev.py`'s own cost) on every pixel
of mouse travel; `render/viewer.py` shows it as a lightweight `QLabel`
instead, updated on hover with no re-render at all.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from adas_sim.scene.types import Prim
from adas_sim.player.panels.viewport import Viewport


@dataclass(frozen=True, slots=True)
class RulerMeasurement:
    """`UT-B3-4`. `bearing_rad` is `atan2(dy, dx)`: 0 at dead ahead (+x),
    positive turning left (+y) -- `R-COORD-1`'s own convention, extended
    with a rotation direction that agrees with a right-handed frame."""

    start_m: tuple[float, float]
    end_m: tuple[float, float]
    distance_m: float
    dx_m: float
    dy_m: float
    bearing_rad: float


def measure(start_m: tuple[float, float], end_m: tuple[float, float]) -> RulerMeasurement:
    dx = end_m[0] - start_m[0]
    dy = end_m[1] - start_m[1]
    return RulerMeasurement(
        start_m=start_m, end_m=end_m, distance_m=math.hypot(dx, dy), dx_m=dx, dy_m=dy,
        bearing_rad=math.atan2(dy, dx),
    )


def snap_point(
    point_m: tuple[float, float], anchors_m: tuple[tuple[float, float], ...],
    viewport: Viewport, *, threshold_px: float = 10.0,
) -> tuple[float, float]:
    """`UT-B3-4`: the nearest anchor **within `threshold_px`** (measured in
    screen pixels, via `viewport.to_px` -- snap distance is a screen
    concept, constant regardless of zoom, not a metre radius that would
    snap wildly at a wide-out zoom), else `point_m` unchanged."""
    if not anchors_m:
        return point_m
    px = viewport.to_px(*point_m)
    best: tuple[float, float] | None = None
    best_dist_px = threshold_px
    for anchor in anchors_m:
        apx = viewport.to_px(*anchor)
        dist_px = math.hypot(apx[0] - px[0], apx[1] - px[1])
        if dist_px <= best_dist_px:
            best_dist_px = dist_px
            best = anchor
    return best if best is not None else point_m


@dataclass(frozen=True, slots=True)
class Annotation:
    point_m: tuple[float, float]
    label: str = ""


def ruler_prims(measurement: RulerMeasurement) -> tuple[Prim, ...]:
    mid = ((measurement.start_m[0] + measurement.end_m[0]) / 2.0,
           (measurement.start_m[1] + measurement.end_m[1]) / 2.0)
    label = (f"{measurement.distance_m:.2f}m  dx={measurement.dx_m:.2f}  "
             f"dy={measurement.dy_m:.2f}  brg={math.degrees(measurement.bearing_rad):.0f}deg")
    return (
        Prim(kind="polyline", points_m=(measurement.start_m, measurement.end_m), style="measure.ruler", z=100),
        Prim(kind="text", x_m=mid[0], y_m=mid[1], text=label, style="measure.ruler", z=101),
    )


def range_ring_prims(radii_m: tuple[float, ...]) -> tuple[Prim, ...]:
    """§8: "toggleable set at declared radii from the rear-axle origin" --
    the origin is `(0, 0)` in the ego frame by construction (`R-COORD-1`)."""
    return tuple(Prim(kind="circle", cx_m=0.0, cy_m=0.0, r_m=r, style="sensor.range_ring", z=90)
                 for r in radii_m if r > 0)


def annotation_prims(annotations: tuple[Annotation, ...]) -> tuple[Prim, ...]:
    prims: list[Prim] = []
    for annotation in annotations:
        prims.append(Prim(kind="points", points_m=(annotation.point_m,), marker="x",
                           style="measure.annotation", z=95))
        if annotation.label:
            prims.append(Prim(kind="text", x_m=annotation.point_m[0], y_m=annotation.point_m[1],
                               text=annotation.label, style="measure.annotation", z=96))
    return tuple(prims)


class MeasureState:
    """Ruler (one at a time, replaced by the next drag), range ring radii
    (toggleable as a set), and persistent annotations (kept until removed
    -- "kept in the session", §8, unlike the ruler which is transient)."""

    def __init__(self) -> None:
        self._ruler: RulerMeasurement | None = None
        self._range_ring_radii: tuple[float, ...] = ()
        self._range_rings_visible = False
        self._annotations: list[Annotation] = []

    def set_ruler(self, start_m: tuple[float, float], end_m: tuple[float, float]) -> RulerMeasurement:
        self._ruler = measure(start_m, end_m)
        return self._ruler

    def clear_ruler(self) -> None:
        self._ruler = None

    def ruler(self) -> RulerMeasurement | None:
        return self._ruler

    def set_range_ring_radii(self, radii_m: tuple[float, ...]) -> None:
        self._range_ring_radii = tuple(sorted(radii_m))

    def toggle_range_rings(self) -> None:
        self._range_rings_visible = not self._range_rings_visible

    @property
    def range_rings_visible(self) -> bool:
        return self._range_rings_visible

    def add_annotation(self, point_m: tuple[float, float], label: str = "") -> None:
        self._annotations.append(Annotation(point_m=point_m, label=label))

    def remove_annotation(self, index: int) -> None:
        if 0 <= index < len(self._annotations):
            del self._annotations[index]

    def annotations(self) -> tuple[Annotation, ...]:
        return tuple(self._annotations)

    def overlay_prims(self) -> tuple[Prim, ...]:
        prims: list[Prim] = []
        if self._ruler is not None:
            prims.extend(ruler_prims(self._ruler))
        if self._range_rings_visible:
            prims.extend(range_ring_prims(self._range_ring_radii))
        prims.extend(annotation_prims(self.annotations()))
        return tuple(prims)

    def __repr__(self) -> str:
        return (f"<MeasureState ruler={'set' if self._ruler else None} "
                f"range_rings_visible={self._range_rings_visible} annotations={len(self._annotations)}>")
